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
    """생성 칼럼이 실제로 동작하는지 확인. Phase 2 추천이 이걸 인덱스로 쓴다."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text("""
            INSERT INTO watches (id, kind, title, params, rules, interval_min, status)
            VALUES (gen_random_uuid(), 'flight', '테스트',
                    '{"destination": "FUK"}'::jsonb, '[]'::jsonb, 360, 'active')
        """)
        )
        dest = await conn.scalar(text("SELECT destination FROM watches WHERE title = '테스트'"))
    assert dest == "FUK"
