"""Tests for hashsplit helpers."""

import json

from hashscope.proxy.hashsplit import (
    derive_fee_user,
    extract_notify_job_id,
    extract_submit_job_id,
    extract_subscribe_extranonce,
    rewrite_authorize_user,
)


def test_derive_fee_user_proxy_test_suffix():
    user = "npub16k7w40qkxkfgg2mqhk8wqwl9glx5s9ltvgk8tyhrlfza4qf3qcfqpj6e47.proxy_test"
    assert derive_fee_user(user, None).endswith(".proxy_test_2")
    assert derive_fee_user(user, None) == user.replace(".proxy_test", ".proxy_test_2")


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


def test_extract_submit_job_id():
    msg = {
        "method": "mining.submit",
        "params": ["w", "job123", "en2", "ntime", "nonce"],
    }
    assert extract_submit_job_id(msg) == "job123"


def test_extract_notify_job_id():
    msg = {"method": "mining.notify", "params": ["jobABC", "prev", "c1", "c2"]}
    assert extract_notify_job_id(msg) == "jobABC"


def test_extract_subscribe_extranonce():
    result = [[["mining.notify", "x"]], "deadbeef", 8]
    en1, en2 = extract_subscribe_extranonce(result)
    assert en1 == "deadbeef"
    assert en2 == 8
