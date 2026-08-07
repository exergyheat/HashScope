"""Tests for hashsplit helpers (same-pool share-band routing)."""

import json

from hashscope.proxy.hashsplit import (
    build_worker_bands,
    derive_fee_user,
    pick_worker_for_rnd,
    rewrite_authorize_user,
    rewrite_submit_worker,
    share_rnd_from_submit,
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


def test_rewrite_submit_worker():
    line = b'{"id":9,"method":"mining.submit","params":["w","job1","e2","t","n"]}\n'
    out = rewrite_submit_worker(line, "fee.worker")
    msg = json.loads(out.decode())
    assert msg["params"][0] == "fee.worker"
    assert msg["params"][1] == "job1"


def test_share_rnd_deterministic():
    params = ["w", "job1", "en2", "ntime", "nonce"]
    a = share_rnd_from_submit(params)
    b = share_rnd_from_submit(params)
    assert a == b
    assert 0 <= a <= 0xFFFF
    # different nonce → different rnd (almost surely)
    params2 = ["w", "job1", "en2", "ntime", "nonce2"]
    assert share_rnd_from_submit(params2) != a


def test_build_worker_bands_50_50():
    bands = build_worker_bands([("A", 50.0), ("B", 50.0)])
    assert len(bands) == 2
    assert bands[0][0] == "A"
    assert bands[0][1] == 0x7FFF  # ceil(0.5 * 0x10000) - 1
    assert bands[1] == ("B", 0xFFFF)


def test_build_worker_bands_90_10():
    bands = build_worker_bands([("cust", 90.0), ("fee", 10.0)])
    assert bands[0][0] == "cust"
    # 90% of 65536 → max ~0xE665
    assert bands[0][1] == int(__import__("math").ceil(0.9 * 0x10000) - 1)
    assert bands[1] == ("fee", 0xFFFF)


def test_pick_worker_for_rnd():
    bands = build_worker_bands([("A", 50.0), ("B", 50.0)])
    assert pick_worker_for_rnd(0, bands) == "A"
    assert pick_worker_for_rnd(0x7FFF, bands) == "A"
    assert pick_worker_for_rnd(0x8000, bands) == "B"
    assert pick_worker_for_rnd(0xFFFF, bands) == "B"


def test_pick_n_workers():
    bands = build_worker_bands([("a", 1), ("b", 1), ("c", 1), ("d", 1)])
    assert len(bands) == 4
    assert bands[-1][1] == 0xFFFF
    seen = {pick_worker_for_rnd(r, bands) for r in (0, 0x4000, 0x8000, 0xC000)}
    assert seen == {"a", "b", "c", "d"}
