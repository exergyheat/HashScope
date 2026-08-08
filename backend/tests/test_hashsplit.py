"""Tests for hashsplit helpers (dual-upstream job-band leg routing)."""

import json

from hashscope.proxy.hashsplit import (
    build_set_difficulty,
    build_set_extranonce,
    build_worker_bands,
    denamespace_job_id,
    derive_fee_user,
    extract_notify_job_id,
    extract_submit_job_id,
    extract_subscribe_extranonce,
    namespace_job_id,
    pick_worker_for_rnd,
    rewrite_authorize_user,
    rewrite_notify_job_id,
    rewrite_submit_for_leg,
)


def test_derive_fee_user_proxy_test_suffix():
    user = "npub16k7w40qkxkfgg2mqhk8wqwl9glx5s9ltvgk8tyhrlfza4qf3qcfqpj6e47.proxy_test"
    assert derive_fee_user(user, None).endswith(".proxy_test_B")
    assert derive_fee_user(user, None) == user.replace(".proxy_test", ".proxy_test_B")


def test_derive_fee_user_proxy_test_a():
    user = "acct.proxy_test_A"
    assert derive_fee_user(user, None) == "acct.proxy_test_B"


def test_derive_fee_user_explicit():
    assert derive_fee_user("a.b", "fee.worker") == "fee.worker"


def test_derive_fee_user_fallback_suffix():
    assert derive_fee_user("rig01", None) == "rig01_fee"


def test_rewrite_authorize_user():
    line = b'{"id":3,"method":"mining.authorize","params":["worker.a","x"]}\n'
    out = rewrite_authorize_user(line, "worker.b", "y")
    msg = json.loads(out.decode())
    assert msg["method"] == "mining.authorize"
    assert msg["params"] == ["worker.b", "y"]
    assert msg["id"] == 3


def test_extract_notify_job_id():
    msg = {"method": "mining.notify", "params": ["job1", "extra"]}
    assert extract_notify_job_id(msg) == "job1"
    assert extract_notify_job_id({"method": "mining.submit", "params": ["job1"]}) is None


def test_extract_submit_job_id():
    msg = {"method": "mining.submit", "params": ["w", "job1", "en2", "t", "n"]}
    assert extract_submit_job_id(msg) == "job1"
    assert extract_submit_job_id({"method": "mining.notify", "params": ["job1"]}) is None


def test_namespace_roundtrip():
    assert namespace_job_id("fee", "job1") == "f.job1"
    assert namespace_job_id("customer", "job1") == "c.job1"
    assert denamespace_job_id("f.job1") == ("fee", "job1")
    assert denamespace_job_id("c.job1") == ("customer", "job1")
    assert denamespace_job_id("job1") == (None, "job1")


def test_rewrite_notify_job_id():
    line = b'{"method":"mining.notify","params":["job1","extra"]}\n'
    out = rewrite_notify_job_id(line, "fee")
    msg = json.loads(out.decode())
    assert msg["params"][0] == "f.job1"
    assert msg["params"][1] == "extra"


def test_rewrite_submit_for_leg_uses_job_prefix():
    line = b'{"id":9,"method":"mining.submit","params":["w","f.job1","e2","t","n"]}\n'
    out = rewrite_submit_for_leg(line, "customer", "fee.worker")
    msg = json.loads(out.decode())
    # prefix says fee, so worker is rewritten to fee_user despite leg arg
    assert msg["params"][0] == "fee.worker"
    assert msg["params"][1] == "job1"


def test_rewrite_submit_for_leg_customer_no_rewrite():
    line = b'{"id":9,"method":"mining.submit","params":["w","c.job1","e2","t","n"]}\n'
    out = rewrite_submit_for_leg(line, "fee", "fee.worker")
    msg = json.loads(out.decode())
    assert msg["params"][0] == "w"
    assert msg["params"][1] == "job1"


def test_extract_subscribe_extranonce():
    result = [[["mining.set_difficulty", "sub1"], ["mining.notify", "sub1"]], "ab12", 4]
    en1, en2 = extract_subscribe_extranonce(result)
    assert en1 == "ab12"
    assert en2 == 4
    assert extract_subscribe_extranonce(["too short"]) == (None, None)


def test_build_set_extranonce():
    out = build_set_extranonce("ab12", 4)
    msg = json.loads(out.decode())
    assert msg["method"] == "mining.set_extranonce"
    assert msg["params"] == ["ab12", 4]


def test_build_set_difficulty():
    out = build_set_difficulty(1024)
    msg = json.loads(out.decode())
    assert msg["method"] == "mining.set_difficulty"
    assert msg["params"] == [1024]


def test_build_worker_bands_50_50():
    bands = build_worker_bands([("customer", 50.0), ("fee", 50.0)])
    assert len(bands) == 2
    assert bands[0][0] == "customer"
    assert bands[0][1] == 0x7FFF  # ceil(0.5 * 0x10000) - 1
    assert bands[1] == ("fee", 0xFFFF)


def test_build_worker_bands_90_10():
    bands = build_worker_bands([("customer", 90.0), ("fee", 10.0)])
    assert bands[0][0] == "customer"
    # 90% of 65536 → max ~0xE665
    assert bands[0][1] == int(__import__("math").ceil(0.9 * 0x10000) - 1)
    assert bands[1] == ("fee", 0xFFFF)


def test_pick_worker_for_rnd():
    bands = build_worker_bands([("customer", 50.0), ("fee", 50.0)])
    assert pick_worker_for_rnd(0, bands) == "customer"
    assert pick_worker_for_rnd(0x7FFF, bands) == "customer"
    assert pick_worker_for_rnd(0x8000, bands) == "fee"
    assert pick_worker_for_rnd(0xFFFF, bands) == "fee"


def test_pick_n_workers():
    bands = build_worker_bands([("a", 1), ("b", 1), ("c", 1), ("d", 1)])
    assert len(bands) == 4
    assert bands[-1][1] == 0xFFFF
    seen = {pick_worker_for_rnd(r, bands) for r in (0, 0x4000, 0x8000, 0xC000)}
    assert seen == {"a", "b", "c", "d"}
