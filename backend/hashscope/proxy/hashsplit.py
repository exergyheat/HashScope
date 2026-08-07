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
