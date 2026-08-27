from __future__ import annotations

from dataclasses import dataclass

from .dataset_registry import DatasetRecord, production_training_allowed


@dataclass(frozen=True)
class TrainingPlan:
    mode: str
    model_family: str
    objective: str
    datasets: tuple[str, ...]
    allowed: bool
    blockers: tuple[str, ...]


def build_training_plan(records: list[DatasetRecord], model_family: str = "llm-adapter") -> TrainingPlan:
    blockers: list[str] = []
    if not records:
        blockers.append("NO_DATASETS_REGISTERED")
    for record in records:
        if record.policy_decision != "ALLOWED":
            blockers.append(f"DATASET_NOT_ALLOWED:{record.dataset_id}:{record.policy_decision}")

    return TrainingPlan(
        mode="OFFLINE_EVAL_ONLY" if blockers else "TRAINING_READY",
        model_family=model_family,
        objective="Improve trend selection, caption quality, platform packaging, and QC scoring.",
        datasets=tuple(record.dataset_id for record in records),
        allowed=production_training_allowed(records),
        blockers=tuple(blockers),
    )


def training_layers() -> dict[str, list[str]]:
    return {
        "data": ["source policy", "dataset registry", "lineage hash", "license review"],
        "ml": ["feature extraction", "ranking model", "calibration", "offline evaluation"],
        "deep_learning": ["vision embeddings", "audio embeddings", "multimodal quality scoring"],
        "llm": ["prompt templates", "RAG over approved data", "pairwise evals", "red-team evals"],
        "automation": ["dry-run", "human approval", "policy gates", "evidence ledger"],
    }

