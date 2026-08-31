# CineForge production operations contract

## Scope

This runbook covers Social Trend Intelligence and the governed social-video publisher. It does not authorize live publication. Platform credentials, account permissions, posting audits and a human publish approval remain external production gates.

## SLI/SLO targets

| SLI | Target | Window |
| --- | ---: | --- |
| governed request validation success | >= 99.9% | rolling 30d |
| policy-gate evaluation availability | >= 99.95% | rolling 30d |
| dry-run orchestration success | >= 99.0% | rolling 7d |
| trend scoring p95 latency excluding external APIs | <= 2s | rolling 7d |
| duplicate external side effects | 0 | always |
| external publishes without HUMAN_APPROVED | 0 | always |
| secret values emitted in structured telemetry | 0 | always |

The system must fail closed when policy, approval, idempotency, account authorization, public-posting audit or rate-limit evidence is missing.

## Error budget

A 99.9% monthly validation SLO permits approximately 43 minutes of unavailable validation per 30 days. Security invariants have a zero-error budget: unauthorized publication, duplicate side effects and secret disclosure trigger an immediate production freeze regardless of availability budget.

## Alerts

Page/incident-worthy conditions:

- any attempted publish denied because policy/approval evidence is inconsistent;
- any duplicate idempotency key with conflicting payload;
- any secret-redaction test failure;
- sustained dry-run failure rate > 1% for 15 minutes;
- external connector authentication failures > 5 in 10 minutes;
- rate-limit responses that exceed configured retry budget;
- production head or readiness manifest drift.

## Incident response

1. Set all `*_PUBLISHING_ENABLED` variables to `false`.
2. Revoke/rotate the affected platform credential if exposure is suspected.
3. Preserve run ID, trace ID, idempotency key, request digest and platform response evidence.
4. Reconcile the external platform to determine whether a side effect happened; treat uncertain outcomes as `UNKNOWN`, not success.
5. Block retries until reconciliation completes.
6. Root-cause policy/tool/model/configuration behavior.
7. Add a regression/adversarial test before re-enabling a connector.
8. Require human approval for restoration of live publication.

## Observability contract

Every production request must be correlatable using trace ID, span ID, run ID and idempotency key. Telemetry must record model/tool duration, routing/fallback, retries, result class and token usage when available. Prompt or generated content is not recorded by default. Secret-like attribute names are redacted before serialization.

## Capacity / FinOps controls

- bounded tool calls, external actions, retries and wall time;
- per-platform daily limits;
- provider/model allowlist and enable flags;
- no unbounded automatic fallback loop;
- cost attribution by run/provider when paid inference is enabled.
