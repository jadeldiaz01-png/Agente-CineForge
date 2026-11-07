from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import pytest

from meta_facebook_mcp_publisher.publish_ledger import (
    PublishReservationDenied, reserve_publish_attempt,
)


def reserve(p: Path, key="key-1", caption="same caption") -> str:
    return reserve_publish_attempt(p, key, "youtube", "channel-1", "a"*64, caption)


def test_first_lease_creates_durable_record(tmp_path):
    p = tmp_path / "ledger.sqlite3"
    receipt=reserve(p)
    assert len(receipt)==64
    with sqlite3.connect(p) as con:
        assert con.execute("SELECT status FROM publish_attempts").fetchone()[0]=="RESERVED_UNRECONCILED"


def test_same_key_rejected_after_reopening(tmp_path):
    p=tmp_path/"ledger.sqlite3"
    reserve(p)
    with pytest.raises(PublishReservationDenied,match="DUPLICATE"):
        reserve(p)


def test_new_key_same_intent_rejected(tmp_path):
    p=tmp_path/"ledger.sqlite3"
    reserve(p)
    with pytest.raises(PublishReservationDenied,match="DUPLICATE"):
        reserve(p,key="different-run")


def test_changed_caption_distinct_intent(tmp_path):
    p=tmp_path/"ledger.sqlite3"
    reserve(p)
    assert reserve(p,key="new",caption="materially new approved caption")


def test_concurrent_duplicate_only_one_wins(tmp_path):
    p=tmp_path/"ledger.sqlite3"
    def run(k):
        try:
            reserve(p,key=k)
            return True
        except PublishReservationDenied:
            return False
    with ThreadPoolExecutor(max_workers=6) as ex:
        results=list(ex.map(run, [f"run-{i}" for i in range(6)]))
    assert sum(results)==1


def test_missing_parent_cannot_claim(tmp_path):
    with pytest.raises(PublishReservationDenied,match="PATH"):
        reserve(tmp_path/"nonexistent"/"db.sqlite3")


def test_invalid_key_cannot_claim(tmp_path):
    with pytest.raises(PublishReservationDenied,match="KEY"):
        reserve(tmp_path/"db.sqlite3",key="")
