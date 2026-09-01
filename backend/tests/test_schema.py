"""마이그레이션이 만든 실제 스키마를 검증한다.
모델 정의가 아니라 DB에 실제로 뭐가 생겼는지를 본다.
"""

from sqlalchemy import inspect, text


async def _columns(engine, table: str) -> dict[str, dict]:
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: inspect(c).get_columns(table))
    return {c["name"]: c for c in cols}


async def test_watches_table_exists_with_required_columns(migrated_engine):
    cols = await _columns(migrated_engine, "watches")
    for name in (
        "id",
        "kind",
        "title",
        "params",
        "rules",
        "interval_min",
        "status",
        "last_run_at",
        "next_run_at",
        "last_sampled_at",
        "created_at",
        "updated_at",
        "destination",
    ):
        assert name in cols, f"watches.{name} 누락"


async def test_all_timestamp_columns_are_timezone_aware(migrated_engine):
    """CLAUDE.md 4번: DB 시각은 전부 timestamptz.
    timestamp without time zone 이 하나라도 있으면 실패한다."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND data_type LIKE 'timestamp%'
              AND data_type <> 'timestamp with time zone'
        """)
            )
        ).fetchall()
    assert rows == [], f"timestamptz 가 아닌 시각 칼럼: {rows}"


async def test_watches_destination_is_generated_from_params(migrated_engine):
    """생성 칼럼이 실제로 동작하는지 확인. Phase 2 추천이 이걸 인덱스로 쓴다.

    세션 스코프 DB를 재사용하므로 삽입한 행을 커밋하지 않고 롤백한다.
    """
    async with migrated_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(
                text("""
                INSERT INTO watches (id, kind, title, params, rules, interval_min, status)
                VALUES (gen_random_uuid(), 'flight', '테스트',
                        '{"destination": "FUK"}'::jsonb, '[]'::jsonb, 360, 'active')
            """)
            )
            dest = await conn.scalar(text("SELECT destination FROM watches WHERE title = '테스트'"))
        finally:
            await trans.rollback()
    assert dest == "FUK"


async def test_watch_runs_cascade_deletes_with_watch(migrated_engine):
    """watches 행을 지우면 그걸 참조하는 watch_runs 행도 CASCADE로 함께 사라진다.
    Task 4~6이 같은 ondelete="CASCADE" FK 패턴을 쌓으므로 여기서 한 번 잠가둔다.
    """
    async with migrated_engine.connect() as conn:
        trans = await conn.begin()
        try:
            watch_id = await conn.scalar(
                text("""
                INSERT INTO watches (id, kind, title, params, rules, interval_min, status)
                VALUES (gen_random_uuid(), 'flight', 'cascade-test',
                        '{}'::jsonb, '[]'::jsonb, 360, 'active')
                RETURNING id
            """)
            )
            run_id = await conn.scalar(
                text("""
                INSERT INTO watch_runs (id, watch_id, status)
                VALUES (gen_random_uuid(), :watch_id, 'ok')
                RETURNING id
            """),
                {"watch_id": watch_id},
            )

            await conn.execute(text("DELETE FROM watches WHERE id = :id"), {"id": watch_id})

            remaining = await conn.scalar(
                text("SELECT count(*) FROM watch_runs WHERE id = :id"), {"id": run_id}
            )
        finally:
            await trans.rollback()
    assert remaining == 0


async def test_watches_status_next_run_index_column_order(migrated_engine):
    """ix_watches_status_next_run 이 (status, next_run_at) 순서로 존재하는지 확인.
    이후 autogenerate가 인덱스를 흘리거나 칼럼 순서를 바꿔도 이게 잡는다."""
    async with migrated_engine.connect() as conn:
        indexdef = await conn.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_watches_status_next_run'")
        )
    assert indexdef is not None, "ix_watches_status_next_run 인덱스가 없다"
    assert "(status, next_run_at)" in indexdef, f"칼럼 순서가 다르다: {indexdef}"
