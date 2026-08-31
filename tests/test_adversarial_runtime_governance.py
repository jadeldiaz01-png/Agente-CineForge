import json

import pytest

from meta_facebook_mcp_publisher.runtime_governance import (
    RuntimeBudget,
    RuntimeLedger,
    authorize_tool_call,
    evidence_digest,
    telemetry_event,
)


def test_external_publish_cannot_be_authorized_by_model_without_human_gate():
    allowed, failures = authorize_tool_call(
        "publish",
        human_approved=False,
        policy_allowed=True,
        requested_scopes={"media:write"},
        granted_scopes={"media:write"},
    )
    assert allowed is False
    assert "HUMAN_APPROVED" in failures


def test_scope_escalation_is_fail_closed():
    allowed, failures = authorize_tool_call(
        "publish",
        human_approved=True,
        policy_allowed=True,
        requested_scopes={"media:write", "account:admin"},
        granted_scopes={"media:write"},
    )
    assert allowed is False
    assert "LEAST_PRIVILEGE_SCOPE_ALLOWED" in failures


def test_policy_denial_cannot_be_overridden():
    allowed, failures = authorize_tool_call(
        "upload",
        human_approved=True,
        policy_allowed=False,
        requested_scopes={"media:write"},
        granted_scopes={"media:write"},
    )
    assert allowed is False
    assert "POLICY_ALLOWED" in failures


def test_runtime_budget_stops_tool_loop():
    ledger = RuntimeLedger(RuntimeBudget(max_tool_calls=2, max_external_actions=1, max_retry_attempts=1))
    ledger.consume_tool()
    ledger.consume_tool(external=True)
    with pytest.raises(RuntimeError, match="TOOL_CALLS_EXCEEDED"):
        ledger.consume_tool()


def test_runtime_budget_stops_duplicate_external_side_effect():
    ledger = RuntimeLedger(RuntimeBudget(max_tool_calls=3, max_external_actions=1, max_retry_attempts=1))
    ledger.consume_tool(external=True)
    with pytest.raises(RuntimeError, match="EXTERNAL_ACTIONS_EXCEEDED"):
        ledger.consume_tool(external=True)


def test_telemetry_redacts_secrets_and_keeps_traceability():
    raw = telemetry_event(
        "gen_ai.tool.call",
        trace_id="trace-1",
        span_id="span-1",
        attributes={"tool.name": "publish", "access_token": "do-not-leak", "gen_ai.usage.input_tokens": 42},
    )
    event = json.loads(raw)
    assert event["trace_id"] == "trace-1"
    assert event["attributes"]["access_token"] == "[REDACTED]"
    assert "do-not-leak" not in raw


def test_evidence_digest_is_deterministic():
    assert evidence_digest(b"evidence") == evidence_digest(b"evidence")
    assert evidence_digest(b"evidence") != evidence_digest(b"different")
