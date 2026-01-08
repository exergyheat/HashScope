"""Agent statistics tracking."""

import time
from typing import Optional
from collections import deque


class AgentStats:
    """Track agent statistics for telemetry."""

    def __init__(self):
        """Initialize stats."""
        self.share_events_received_total = 0
        self.submits_attempted_total = 0
        self.submits_accepted_total = 0
        self.submits_rejected_total = 0
        self.last_submit_latency_ms: Optional[float] = None
        self._last_submit_start: Optional[float] = None

        # Track submit timestamps for rate calculation (last 60 seconds)
        self._submit_timestamps: deque = deque(maxlen=10000)  # Limit to prevent memory issues

    def record_share_event_received(self):
        """Record that a share event was received."""
        self.share_events_received_total += 1

    def record_submit_attempted(self):
        """Record that a submit was attempted."""
        self.submits_attempted_total += 1
        now = time.time()
        self._last_submit_start = now
        self._submit_timestamps.append(now)

    def record_submit_accepted(self):
        """Record that a submit was accepted."""
        self.submits_accepted_total += 1
        if self._last_submit_start:
            self.last_submit_latency_ms = (time.time() - self._last_submit_start) * 1000

    def record_submit_rejected(self):
        """Record that a submit was rejected."""
        self.submits_rejected_total += 1
        if self._last_submit_start:
            self.last_submit_latency_ms = (time.time() - self._last_submit_start) * 1000

    def get_submit_rate_per_second(self, window_seconds: int = 60) -> float:
        """
        Calculate submit rate over the specified time window.

        Args:
            window_seconds: Time window in seconds (default 60)

        Returns:
            Submits per second over the window
        """
        if not self._submit_timestamps:
            return 0.0

        now = time.time()
        cutoff = now - window_seconds

        # Count submits within the window
        recent_submits = sum(1 for ts in self._submit_timestamps if ts >= cutoff)

        # Calculate rate
        if recent_submits == 0:
            return 0.0

        # Get actual time span (in case we have less than window_seconds of data)
        oldest_in_window = min(ts for ts in self._submit_timestamps if ts >= cutoff)
        actual_duration = now - oldest_in_window

        if actual_duration <= 0:
            return 0.0

        return recent_submits / actual_duration

    def to_dict(self) -> dict:
        """Convert stats to dict."""
        return {
            "share_events_received_total": self.share_events_received_total,
            "submits_attempted_total": self.submits_attempted_total,
            "submits_accepted_total": self.submits_accepted_total,
            "submits_rejected_total": self.submits_rejected_total,
            "last_submit_latency_ms": self.last_submit_latency_ms,
            "submits_per_second_1min": round(self.get_submit_rate_per_second(60), 2),
            "submits_per_second_10sec": round(self.get_submit_rate_per_second(10), 2),
        }

