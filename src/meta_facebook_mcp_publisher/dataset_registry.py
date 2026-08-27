from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .data_governance import DataSource, SourceDecision, evaluate_data_source


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    name: str
    purpose: str
    source_url: str
    source_license: str
    policy_decision: str
    policy_reasons: tuple[str, ...]
    created_at: str
    lineage_hash: str
    splits: dict[str, float] = field(default_factory=lambda: {"train": 0.8, "validation": 0.1, "test": 0.1})


class DatasetRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def register(self, source: DataSource) -> DatasetRecord:
        policy = evaluate_data_source(source)
        payload = {
            "name": source.name,
            "url": source.url,
            "license": source.license,
            "intended_use": source.intended_use,
        }
        lineage_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        record = DatasetRecord(
            dataset_id=lineage_hash[:16],
            name=source.name,
            purpose=source.intended_use,
            source_url=source.url,
            source_license=source.license,
            policy_decision=policy.decision.value,
            policy_reasons=policy.reasons,
            created_at=datetime.now(UTC).isoformat(),
            lineage_hash=lineage_hash,
        )
        self._append(record)
        return record

    def _append(self, record: DatasetRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def load_all(self) -> list[DatasetRecord]:
        if not self.path.exists():
            return []
        records: list[DatasetRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                data = json.loads(line)
                data["policy_reasons"] = tuple(data.get("policy_reasons", []))
                records.append(DatasetRecord(**data))
        return records


def production_training_allowed(records: list[DatasetRecord]) -> bool:
    return bool(records) and all(record.policy_decision == SourceDecision.ALLOWED.value for record in records)

