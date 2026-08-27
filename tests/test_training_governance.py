from pathlib import Path

from meta_facebook_mcp_publisher.data_governance import DataSource, SourceDecision, evaluate_data_source
from meta_facebook_mcp_publisher.dataset_registry import DatasetRegistry
from meta_facebook_mcp_publisher.training_pipeline import build_training_plan


def test_blocks_missing_license() -> None:
    result = evaluate_data_source(
        DataSource(
            name="unknown",
            url="https://example.com/data",
            license="",
            intended_use="training",
            terms_reviewed=True,
            robots_reviewed=True,
        )
    )

    assert result.decision == SourceDecision.BLOCKED
    assert "LICENSE_MISSING" in result.reasons


def test_allows_open_reviewed_source() -> None:
    result = evaluate_data_source(
        DataSource(
            name="open dataset",
            url="https://example.com/data",
            license="CC-BY-4.0",
            intended_use="training",
            terms_reviewed=True,
            robots_reviewed=True,
        )
    )

    assert result.decision == SourceDecision.ALLOWED


def test_registry_and_training_plan(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "registry.jsonl")
    registry.register(
        DataSource(
            name="open dataset",
            url="https://example.com/data",
            license="CC0",
            intended_use="training",
            terms_reviewed=True,
            robots_reviewed=True,
        )
    )

    plan = build_training_plan(registry.load_all())

    assert plan.allowed
    assert plan.mode == "TRAINING_READY"

