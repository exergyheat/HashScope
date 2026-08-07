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


def test_namespace_roundtrip():
    from hashscope.proxy.hashsplit import (
        denamespace_job_id,
        namespace_job_id,
        rewrite_notify_job_id,
        rewrite_submit_for_leg,
    )

    assert namespace_job_id("customer", "abc") == "c.abc"
    assert namespace_job_id("fee", "abc") == "f.abc"
    assert denamespace_job_id("c.abc") == ("customer", "abc")
    assert denamespace_job_id("f.abc") == ("fee", "abc")

    notify = b'{"method":"mining.notify","params":["job1","x"]}\n'
    out = rewrite_notify_job_id(notify, "fee")
    assert json.loads(out)["params"][0] == "f.job1"

    submit = b'{"id":9,"method":"mining.submit","params":["w","f.job1","e2","t","n"]}\n'
    out2 = rewrite_submit_for_leg(submit, "fee", "fee.worker")
    msg = json.loads(out2)
    assert msg["params"][0] == "fee.worker"
    assert msg["params"][1] == "job1"

    submit_c = b'{"id":10,"method":"mining.submit","params":["w","c.job2","e2","t","n"]}\n'
    out3 = rewrite_submit_for_leg(
        submit_c, "customer", "fee.worker", customer_user="cust.worker"
    )
    msg3 = json.loads(out3)
    assert msg3["params"][0] == "cust.worker"
    assert msg3["params"][1] == "job2"
