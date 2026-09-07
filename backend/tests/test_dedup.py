"""dedup 키 생성 + cooldown 체크 테스트."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.engine.dedup import make_dedup_key


def test_make_dedup_key_is_deterministic():
    wid = uuid4()
    k1 = make_dedup_key(wid, "r1", 237000, date(2026, 10, 15))
    k2 = make_dedup_key(wid, "r1", 237000, date(2026, 10, 15))
    assert k1 == k2


def test_make_dedup_key_buckets_price():
    wid = uuid4()
    # 237,000 과 239,999 는 같은 5천원 버킷 (237000//5000 == 239999//5000 == 47)
    k1 = make_dedup_key(wid, "r1", 237000, None)
    k2 = make_dedup_key(wid, "r1", 239999, None)
    assert k1 == k2


def test_make_dedup_key_different_bucket():
    wid = uuid4()
    k1 = make_dedup_key(wid, "r1", 237000, None)
    k2 = make_dedup_key(wid, "r1", 245000, None)  # 다른 버킷
    assert k1 != k2


def test_make_dedup_key_different_rule():
    wid = uuid4()
    k1 = make_dedup_key(wid, "r1", 237000, None)
    k2 = make_dedup_key(wid, "r2", 237000, None)
    assert k1 != k2


@pytest.mark.asyncio
async def test_is_suppressed_false_when_no_prior(db_session):
    from app.engine.dedup import is_suppressed

    result = await is_suppressed("nonexistent-key", "good", 12, db_session)
    assert result is False


@pytest.mark.asyncio
async def test_is_suppressed_true_within_cooldown(db_session, migrated_engine):
    from app.engine.dedup import is_suppressed
    from app.models.alert import Alert
    from app.models.watch import Watch

    # Watch 생성
    watch = Watch(
        kind="flight",
        title="test",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": "2026-10-01",
            "depart_to": "2026-10-31",
        },
        rules=[],
    )
    db_session.add(watch)
    await db_session.flush()

    key = "test-dedup-key-cooldown"
    alert = Alert(
        watch_id=watch.id,
        rule_id="r1",
        severity="good",
        title="t",
        body="b",
        dedup_key=key,
    )
    db_session.add(alert)
    await db_session.commit()

    result = await is_suppressed(key, "good", 12, db_session)
    assert result is True


@pytest.mark.asyncio
async def test_is_suppressed_false_when_severity_upgraded(db_session, migrated_engine):
    from app.engine.dedup import is_suppressed
    from app.models.alert import Alert
    from app.models.watch import Watch

    watch = Watch(
        kind="flight",
        title="test2",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": "2026-10-01",
            "depart_to": "2026-10-31",
        },
        rules=[],
    )
    db_session.add(watch)
    await db_session.flush()

    key = "test-dedup-key-upgrade"
    alert = Alert(
        watch_id=watch.id,
        rule_id="r1",
        severity="good",  # 기존은 good
        title="t",
        body="b",
        dedup_key=key,
    )
    db_session.add(alert)
    await db_session.commit()

    # severity가 great로 올라가면 suppress 안 함
    result = await is_suppressed(key, "great", 12, db_session)
    assert result is False
