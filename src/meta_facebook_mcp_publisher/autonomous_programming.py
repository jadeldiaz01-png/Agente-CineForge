from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeChangeProposal:
    title: str
    files: tuple[str, ...]
    risk_level: str
    requires_human_approval: bool
    rationale: str


def propose_safe_code_change(title: str, files: tuple[str, ...], touches_credentials: bool = False) -> CodeChangeProposal:
    risk = "HIGH" if touches_credentials else "MEDIUM"
    return CodeChangeProposal(
        title=title,
        files=files,
        risk_level=risk,
        requires_human_approval=True,
        rationale="Autonomous code changes must be reviewed before deployment.",
    )

