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


async def test_offers_price_is_integer_not_float(migrated_engine):
    """CLAUDE.md 5번: 가격은 원화 정수. float 금지."""
    cols = await _columns(migrated_engine, "offers")
    assert cols["price_krw"]["type"].python_type is int


async def test_offers_has_freshness_columns(migrated_engine):
    """스펙 §6: 사용자에게 신선도를 보여주려면 이 칼럼들이 필요하다."""
    cols = await _columns(migrated_engine, "offers")
    for name in ("freshness", "cache_age_days", "observed_at", "verified", "verify_run_id"):
        assert name in cols, f"offers.{name} 누락"


async def test_offers_unique_uses_run_id_not_collected_at(migrated_engine):
    """A1 검토 발견 사항: collected_at 을 unique 에 넣으면 행마다 now() 라
    튜플이 항상 달라져서 중복을 전혀 못 막는다. run_id 를 써야 한다."""
    async with migrated_engine.connect() as conn:
        constraints = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("offers"))
    cols = {tuple(sorted(c["column_names"])) for c in constraints}
    assert ("external_id", "run_id", "source", "watch_id") in cols, cols


async def test_snapshots_have_coverage_columns(migrated_engine):
    """coverage_pct 가 없으면 커버리지 하락을 가격 상승으로 오독한다 (스펙 §6)."""
    cols = await _columns(migrated_engine, "price_snapshots")
    for name in ("coverage_pct", "live_pct", "credits_used"):
        assert name in cols, f"price_snapshots.{name} 누락"


async def _insert_watch_run_offer(conn, *, watch_title: str, external_id: str):
    """watches + watch_runs + offers 각 1행을 넣고 (watch_id, run_id, offer_id) 를 반환한다.
    두 캐스케이드 테스트가 같은 셋업을 공유하므로 헬퍼로 뺐다."""
    watch_id = await conn.scalar(
        text("""
        INSERT INTO watches (id, kind, title, params, rules, interval_min, status)
        VALUES (gen_random_uuid(), 'flight', :title, '{}'::jsonb, '[]'::jsonb, 360, 'active')
        RETURNING id
    """),
        {"title": watch_title},
    )
    run_id = await conn.scalar(
        text("""
        INSERT INTO watch_runs (id, watch_id, status)
        VALUES (gen_random_uuid(), :watch_id, 'ok')
        RETURNING id
    """),
        {"watch_id": watch_id},
    )
    offer_id = await conn.scalar(
        text("""
        INSERT INTO offers (id, watch_id, run_id, source, external_id, kind,
                             price_krw, freshness)
        VALUES (gen_random_uuid(), :watch_id, :run_id, 'test-source', :external_id, 'flight',
                100000, 'live')
        RETURNING id
    """),
        {"watch_id": watch_id, "run_id": run_id, "external_id": external_id},
    )
    return watch_id, run_id, offer_id


async def test_offers_cascade_delete_via_watch_run_deletion(migrated_engine):
    """offers.run_id 경로 단독 검증.

    offers 는 watches 로 가는 FK 를 두 개 갖는다(run_id 경유, watch_id 직접).
    DELETE FROM watches 를 쓰면 watch_id 경로만으로 offers 가 지워져 run_id 의
    ondelete 설정이 검사조차 안 된다(NOT DEFERRABLE 제약은 문장 단위 검사).
    그래서 여기서는 watch_runs 만 지워 run_id 경로를 고립시킨다.
    """
    async with migrated_engine.connect() as conn:
        trans = await conn.begin()
        try:
            _watch_id, run_id, offer_id = await _insert_watch_run_offer(
                conn, watch_title="offers-run-cascade-test", external_id="ext-run"
            )

            await conn.execute(text("DELETE FROM watch_runs WHERE id = :id"), {"id": run_id})

            remaining_offers = await conn.scalar(
                text("SELECT count(*) FROM offers WHERE id = :id"), {"id": offer_id}
            )
        finally:
            await trans.rollback()
    assert remaining_offers == 0


async def test_offers_cascade_delete_via_watch_deletion(migrated_engine):
    """offers.watch_id 경로 + watch_runs 연쇄 검증.

    watches 를 지우면 watch_id 직접 FK 로 offers 가 즉시 사라지고, watch_runs 도
    함께 CASCADE 로 사라진다(그 아래 걸린 offers.run_id 는 이 경로에서 검사되지 않음 —
    run_id 경로는 test_offers_cascade_delete_via_watch_run_deletion 이 별도로 잠근다).
    """
    async with migrated_engine.connect() as conn:
        trans = await conn.begin()
        try:
            watch_id, run_id, offer_id = await _insert_watch_run_offer(
                conn, watch_title="offers-watch-cascade-test", external_id="ext-watch"
            )

            await conn.execute(text("DELETE FROM watches WHERE id = :id"), {"id": watch_id})

            remaining_runs = await conn.scalar(
                text("SELECT count(*) FROM watch_runs WHERE id = :id"), {"id": run_id}
            )
            remaining_offers = await conn.scalar(
                text("SELECT count(*) FROM offers WHERE id = :id"), {"id": offer_id}
            )
        finally:
            await trans.rollback()
    assert remaining_runs == 0
    assert remaining_offers == 0
