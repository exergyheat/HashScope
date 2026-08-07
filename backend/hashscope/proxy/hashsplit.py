"""Hashsplit helpers: dual-upstream fee routing utilities."""

from __future__ import annotations

import json
from typing import Any, Optional


def derive_fee_user(customer_user: str, explicit_fee_user: Optional[str]) -> str:
    """
    Resolve the fee-leg worker name.

    Prefer explicit config. Otherwise, if the customer worker ends with
    ``.proxy_test``, rewrite to ``.proxy_test_2``; else append ``_fee``.
    """
    if explicit_fee_user:
        return explicit_fee_user
    if customer_user.endswith(".proxy_test"):
        return customer_user[: -len(".proxy_test")] + ".proxy_test_2"
    return f"{customer_user}_fee"


def rewrite_authorize_user(line: bytes, fee_user: str, fee_password: str) -> bytes:
    """
    Rewrite a mining.authorize line to use fee credentials.

    Passes non-authorize / unparseable lines through unchanged.
    """
    try:
        text = line.decode("utf-8", errors="replace").strip()
        msg = json.loads(text)
    except (UnicodeError, json.JSONDecodeError):
        return line

    if msg.get("method") != "mining.authorize":
        return line

    params = msg.get("params")
    if not isinstance(params, list) or len(params) < 1:
        msg["params"] = [fee_user, fee_password]
    else:
        params = list(params)
        params[0] = fee_user
        if len(params) < 2:
            params.append(fee_password)
        else:
            params[1] = fee_password
        msg["params"] = params

    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def extract_submit_job_id(msg: dict[str, Any]) -> Optional[str]:
    """mining.submit params: [worker, job_id, extranonce2, ntime, nonce, ...]."""
    if msg.get("method") != "mining.submit":
        return None
    params = msg.get("params")
    if not isinstance(params, list) or len(params) < 2:
        return None
    job_id = params[1]
    return str(job_id) if job_id is not None else None


def extract_notify_job_id(msg: dict[str, Any]) -> Optional[str]:
    """mining.notify params: [job_id, ...]."""
    if msg.get("method") != "mining.notify":
        return None
    params = msg.get("params")
    if not isinstance(params, list) or len(params) < 1:
        return None
    job_id = params[0]
    return str(job_id) if job_id is not None else None


# Prefixes so dual upstreams never collide on job_id inside the miner.
JOB_PREFIX_CUSTOMER = "c."
JOB_PREFIX_FEE = "f."


def namespace_job_id(leg: str, raw_job_id: str) -> str:
    """Tag a pool job id with the leg that issued it."""
    if leg == "fee":
        return f"{JOB_PREFIX_FEE}{raw_job_id}"
    return f"{JOB_PREFIX_CUSTOMER}{raw_job_id}"


def denamespace_job_id(namespaced: str) -> tuple[Optional[str], str]:
    """
    Reverse namespace_job_id.

    Returns (leg, raw_job_id). If no known prefix, leg is None.
    """
    if namespaced.startswith(JOB_PREFIX_FEE):
        return "fee", namespaced[len(JOB_PREFIX_FEE) :]
    if namespaced.startswith(JOB_PREFIX_CUSTOMER):
        return "customer", namespaced[len(JOB_PREFIX_CUSTOMER) :]
    return None, namespaced


def rewrite_notify_job_id(line: bytes, leg: str) -> bytes:
    """Rewrite mining.notify job_id with a leg prefix before sending to miner."""
    try:
        msg = json.loads(line.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return line
    if msg.get("method") != "mining.notify":
        return line
    params = msg.get("params")
    if not isinstance(params, list) or not params:
        return line
    raw = str(params[0])
    params = list(params)
    params[0] = namespace_job_id(leg, raw)
    msg["params"] = params
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def rewrite_submit_for_leg(
    line: bytes,
    leg: str,
    fee_user: Optional[str],
    customer_user: Optional[str] = None,
) -> bytes:
    """
    Strip namespaced job_id back to pool raw id and set worker for the leg.
    """
    try:
        msg = json.loads(line.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return line
    if msg.get("method") != "mining.submit":
        return line
    params = msg.get("params")
    if not isinstance(params, list) or len(params) < 2:
        return line
    params = list(params)
    detected_leg, raw_job = denamespace_job_id(str(params[1]))
    # Prefer leg from job id prefix when present
    use_leg = detected_leg or leg
    params[1] = raw_job
    if use_leg == "fee" and fee_user:
        params[0] = fee_user
    elif use_leg == "customer" and customer_user:
        params[0] = customer_user
    msg["params"] = params
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def extract_subscribe_extranonce(result: Any) -> tuple[Optional[str], Optional[int]]:
    """
    Parse mining.subscribe result for extranonce1 and extranonce2_size.

    Typical result: [subscriptions, extranonce1, extranonce2_size]
    """
    if not isinstance(result, list) or len(result) < 3:
        return None, None
    extranonce1 = result[1]
    extranonce2_size = result[2]
    en1 = str(extranonce1) if extranonce1 is not None else None
    try:
        en2 = int(extranonce2_size) if extranonce2_size is not None else None
    except (TypeError, ValueError):
        en2 = None
    return en1, en2


def build_set_extranonce(extranonce1: str, extranonce2_size: int) -> bytes:
    """Build a mining.set_extranonce notification for leg switches."""
    msg = {
        "method": "mining.set_extranonce",
        "params": [extranonce1, extranonce2_size],
    }
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def build_set_difficulty(difficulty: float | int) -> bytes:
    """Build a mining.set_difficulty notification."""
    msg = {
        "method": "mining.set_difficulty",
        "params": [difficulty],
    }
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
