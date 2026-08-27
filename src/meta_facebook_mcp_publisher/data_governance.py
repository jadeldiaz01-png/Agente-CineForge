from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse


class SourceDecision(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class DataSource:
    name: str
    url: str
    license: str
    intended_use: str
    contains_personal_data: bool = False
    robots_reviewed: bool = False
    terms_reviewed: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcePolicyResult:
    decision: SourceDecision
    reasons: tuple[str, ...]


OPEN_LICENSE_HINTS = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "mit",
    "apache-2.0",
    "bsd",
    "public-domain",
    "open-data",
}


def evaluate_data_source(source: DataSource) -> SourcePolicyResult:
    reasons: list[str] = []
    parsed = urlparse(source.url)

    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        reasons.append("SOURCE_URL_INVALID")
    if not source.terms_reviewed:
        reasons.append("TERMS_NOT_REVIEWED")
    if not source.robots_reviewed:
        reasons.append("ROBOTS_NOT_REVIEWED")
    if source.contains_personal_data:
        reasons.append("PERSONAL_DATA_REQUIRES_REVIEW")

    license_name = source.license.strip().lower()
    if not license_name:
        reasons.append("LICENSE_MISSING")
    elif not any(hint in license_name for hint in OPEN_LICENSE_HINTS):
        reasons.append("LICENSE_NEEDS_REVIEW")

    if any(reason in reasons for reason in {"SOURCE_URL_INVALID", "LICENSE_MISSING"}):
        return SourcePolicyResult(SourceDecision.BLOCKED, tuple(reasons))
    if reasons:
        return SourcePolicyResult(SourceDecision.NEEDS_REVIEW, tuple(reasons))
    return SourcePolicyResult(SourceDecision.ALLOWED, ())

