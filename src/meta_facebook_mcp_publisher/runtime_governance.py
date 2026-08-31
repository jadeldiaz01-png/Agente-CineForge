from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

_SECRET_KEYS = re.compile(r"(token|secret|password|authorization|api[_-]?key|private[_-]?key)", re.I)
_HIGH_RISK_EXTERNAL_ACTIONS = frozenset({"publish", "send_message", "upload", "delete", "purchase", "payment"})


@dataclass(frozen=True)
class RuntimeBudget:
    max_tool_calls: int = 12
    max_external_actions: int = 1
    max_retry_attempts: int = 2
    max_wall_seconds: float = 120.0

    def __post_init__(self) -> None:
        if min(self.max_tool_calls, self.max_external_actions, self.max_retry_attempts) < 0:
            raise ValueError("budget values cannot be negative")
        if self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be positive")


@dataclass
class RuntimeLedger:
    budget: RuntimeBudget = field(default_factory=RuntimeBudget)
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    external_actions: int = 0
    retries: int = 0

    def _check_time(self) -> None:
        if time.monotonic() - self.started_at > self.budget.max_wall_seconds:
            raise RuntimeError("RUNTIME_BUDGET_WALL_TIME_EXCEEDED")

    def consume_tool(self, *, external: bool = False, retry: bool = False) -> None:
        self._check_time()
        if self.tool_calls >= self.budget.max_tool_calls:
            raise RuntimeError("RUNTIME_BUDGET_TOOL_CALLS_EXCEEDED")
        if external and self.external_actions >= self.budget.max_external_actions:
            raise RuntimeError("RUNTIME_BUDGET_EXTERNAL_ACTIONS_EXCEEDED")
        if retry and self.retries >= self.budget.max_retry_attempts:
            raise RuntimeError("RUNTIME_BUDGET_RETRIES_EXCEEDED")
        self.tool_calls += 1
        if external:
            self.external_actions += 1
        if retry:
            self.retries += 1


def authorize_tool_call(
    tool_name: str,
    *,
    human_approved: bool,
    policy_allowed: bool,
    requested_scopes: set[str] | frozenset[str],
    granted_scopes: set[str] | frozenset[str],
) -> tuple[bool, tuple[str, ...]]:
    """Deterministic tool authorization; model output never overrides this decision."""
    failures: list[str] = []
    normalized = tool_name.strip().lower()
    if not normalized:
        failures.append("TOOL_NAME_PRESENT")
    if not policy_allowed:
        failures.append("POLICY_ALLOWED")
    if not set(requested_scopes).issubset(set(granted_scopes)):
        failures.append("LEAST_PRIVILEGE_SCOPE_ALLOWED")
    if normalized in _HIGH_RISK_EXTERNAL_ACTIONS and not human_approved:
        failures.append("HUMAN_APPROVED")
    return not failures, tuple(failures)


def redact_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in attributes.items():
        if _SECRET_KEYS.search(key):
            safe[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 2048:
            safe[key] = value[:2048] + "…"
        else:
            safe[key] = value
    return safe


def telemetry_event(
    name: str,
    *,
    trace_id: str,
    span_id: str,
    attributes: Mapping[str, Any] | None = None,
) -> str:
    """Return privacy-safe structured telemetry using OTel-style GenAI attribute names."""
    if not trace_id or not span_id:
        raise ValueError("trace_id and span_id are required")
    event = {
        "event.name": name,
        "trace_id": trace_id,
        "span_id": span_id,
        "timestamp_unix_ms": int(time.time() * 1000),
        "attributes": redact_attributes(attributes or {}),
    }
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def evidence_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
