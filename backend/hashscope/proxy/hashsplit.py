"""Hashsplit helpers: same-pool share-band worker routing (DATUM-style)."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Optional, Sequence


def derive_fee_user(customer_user: str, explicit_fee_user: Optional[str]) -> str:
    """Resolve fee worker name; explicit config wins."""
    if explicit_fee_user:
        return explicit_fee_user
    if customer_user.endswith(".proxy_test_A"):
        return customer_user[: -len(".proxy_test_A")] + ".proxy_test_B"
    if customer_user.endswith(".proxy_test"):
        return customer_user[: -len(".proxy_test")] + ".proxy_test_B"
    if customer_user.endswith("_A"):
        return customer_user[:-2] + "_B"
    return f"{customer_user}_fee"


def rewrite_authorize_user(line: bytes, user: str, password: str) -> bytes:
    """Rewrite mining.authorize to the given worker credentials."""
    try:
        text = line.decode("utf-8", errors="replace").strip()
        msg = json.loads(text)
    except (UnicodeError, json.JSONDecodeError):
        return line

    if msg.get("method") != "mining.authorize":
        return line

    params = msg.get("params")
    if not isinstance(params, list) or len(params) < 1:
        msg["params"] = [user, password]
    else:
        params = list(params)
        params[0] = user
        if len(params) < 2:
            params.append(password)
        else:
            params[1] = password
        msg["params"] = params

    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def rewrite_submit_worker(line: bytes, worker: str) -> bytes:
    """Rewrite mining.submit worker (params[0]) only."""
    try:
        msg = json.loads(line.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return line
    if msg.get("method") != "mining.submit":
        return line
    params = msg.get("params")
    if not isinstance(params, list) or not params:
        return line
    params = list(params)
    params[0] = worker
    msg["params"] = params
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def share_rnd_from_submit(params: Sequence[Any]) -> int:
    """
    DATUM-style 16-bit selector from share fields.

    We don't assemble a full block header (MITM proxy). Use a stable hash of
    the submit identity fields so each share maps deterministically into 0..65535.
    params: [worker, job_id, extranonce2, ntime, nonce, ...]
    """
    parts = []
    for i in (1, 2, 3, 4):  # job_id, en2, ntime, nonce
        if i < len(params) and params[i] is not None:
            parts.append(str(params[i]))
        else:
            parts.append("")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "little")


def build_worker_bands(
    workers: Sequence[tuple[str, float]],
) -> list[tuple[str, int]]:
    """
    Build cumulative max ranges on 0..0xFFFF from (worker, weight) pairs.

    Weights are relative; need not sum to 1. Returns list of (worker, max_inclusive).
    """
    total = sum(max(0.0, w) for _, w in workers)
    if total <= 0 or not workers:
        return []
    bands: list[tuple[str, int]] = []
    cum = 0.0
    for i, (user, weight) in enumerate(workers):
        cum += max(0.0, weight)
        if i == len(workers) - 1:
            mx = 0xFFFF
        else:
            mx = min(0xFFFF, max(0, int(math.ceil(cum / total * 0x10000) - 1)))
        bands.append((user, mx))
    return bands


def pick_worker_for_rnd(share_rnd: int, bands: Sequence[tuple[str, int]]) -> Optional[str]:
    """Pick worker whose cumulative max is the first >= share_rnd."""
    rnd = share_rnd & 0xFFFF
    for user, mx in bands:
        if rnd <= mx:
            return user
    return bands[-1][0] if bands else None
