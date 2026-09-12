from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Iterable


_CATALOG_PACKAGE = "meta_facebook_mcp_publisher"
_CATALOG_RESOURCE = ("data", "free-video-providers-2026.json")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class FreeVideoRequirement:
    """Requirements for a zero-external-cash source-selection decision."""

    real_footage_required: bool = False
    generated_video_required: bool = False
    commercial_use: bool = True
    native_full_hd_vertical_required: bool = True

    def __post_init__(self) -> None:
        if self.real_footage_required and self.generated_video_required:
            raise ValueError(
                "real_footage_required and generated_video_required are mutually exclusive"
            )


@dataclass(frozen=True)
class RuntimeCapabilities:
    ffmpeg_available: bool
    cuda_ready: bool
    env_names: frozenset[str] = field(default_factory=frozenset)
    ready_markers: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def detect(cls, environ: dict[str, str] | None = None) -> "RuntimeCapabilities":
        env = environ if environ is not None else dict(os.environ)
        markers = frozenset(
            key
            for key, value in env.items()
            if key.startswith("CINEFORGE_")
            and str(value).strip().lower() in {"1", "true", "yes", "on"}
        )
        cuda_ready = any(
            marker in markers
            for marker in {"CINEFORGE_GPU_READY", "CINEFORGE_CUDA_READY"}
        )
        return cls(
            ffmpeg_available=shutil.which("ffmpeg") is not None,
            cuda_ready=cuda_ready,
            env_names=frozenset(
                key for key, value in env.items() if str(value).strip()
            ),
            ready_markers=markers,
        )


@dataclass(frozen=True)
class ProviderDecision:
    provider_id: str
    allowed: bool
    failed_gates: tuple[str, ...]


@dataclass(frozen=True)
class ZeroCostSelection:
    selected_provider_id: str | None
    composer_id: str | None
    authorized: bool
    decisions: tuple[ProviderDecision, ...]
    failed_gates: tuple[str, ...]


def _read_packaged_catalog() -> str:
    item = resources.files(_CATALOG_PACKAGE)
    for part in _CATALOG_RESOURCE:
        item = item.joinpath(part)
    return item.read_text(encoding="utf-8")


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    override = path or os.getenv("CINEFORGE_FREE_VIDEO_CATALOG")
    raw = Path(override).read_text(encoding="utf-8") if override else _read_packaged_catalog()
    data = json.loads(raw)
    validate_catalog(data)
    return data


def validate_catalog(catalog: dict[str, Any]) -> None:
    policy = catalog.get("policy", {})
    if policy.get("max_external_cash_cost_usd") != 0.0:
        raise ValueError("zero-cost catalog must have max_external_cash_cost_usd=0.0")
    if policy.get("autonomous_purchase_allowed") is not False:
        raise ValueError("autonomous purchases must be disabled")
    if policy.get("paid_fallback_allowed") is not False:
        raise ValueError("paid fallback must be disabled")

    ids: set[str] = set()
    for provider in catalog.get("providers", []):
        provider_id = provider.get("id")
        if not provider_id or provider_id in ids:
            raise ValueError(f"invalid or duplicate provider id: {provider_id!r}")
        ids.add(provider_id)

        cost_policy = provider.get("cash_cost_policy")
        auto_eligible = provider.get("auto_eligible") is True
        if auto_eligible and cost_policy in {"paid", "free_quota"}:
            raise ValueError(
                f"provider {provider_id} cannot be auto-eligible under zero-cost policy: {cost_policy}"
            )
        if provider.get("role") == "source" and not provider.get("license_url"):
            raise ValueError(f"source provider {provider_id} must declare license_url")
        if (
            provider.get("commercial_use") == "allowed_with_asset_license_gate"
            and provider.get("asset_license_gate") is not True
        ):
            raise ValueError(
                f"provider {provider_id} must require an asset license gate"
            )


def _commercial_rights_pass(provider: dict[str, Any], license_attested: set[str]) -> bool:
    status = provider.get("commercial_use")
    if status in {
        "allowed",
        "allowed_subject_to_build_license",
        "allowed_with_asset_license_gate",
    }:
        return True
    return provider.get("id") in license_attested


def _native_resolution_gate(
    provider: dict[str, Any], provider_id: str, resolution_attested: set[str]
) -> str | None:
    status = provider.get("native_1080_vertical")
    if status in {"yes", "asset_dependent"}:
        return None
    if status == "runtime_benchmark_required":
        return None if provider_id in resolution_attested else "NATIVE_FULL_HD_BENCHMARK"
    if status in {"no", "unsupported"}:
        return "NATIVE_FULL_HD_UNSUPPORTED"
    return "NATIVE_FULL_HD_NOT_CERTIFIED"


def evaluate_source_provider(
    provider: dict[str, Any],
    requirement: FreeVideoRequirement,
    runtime: RuntimeCapabilities,
    *,
    verified_free_quota: set[str] | None = None,
    license_attested: set[str] | None = None,
    resolution_attested: set[str] | None = None,
) -> ProviderDecision:
    verified_free_quota = verified_free_quota or set()
    license_attested = license_attested or set()
    resolution_attested = resolution_attested or set()
    failed: list[str] = []
    provider_id = str(provider.get("id"))

    if provider.get("role") != "source":
        failed.append("ROLE_SOURCE")

    cost_policy = provider.get("cash_cost_policy")
    if cost_policy == "free_quota" and provider_id not in verified_free_quota:
        failed.append("FREE_QUOTA_VERIFIED")
    elif cost_policy not in {"zero", "zero_local_compute", "free_quota"}:
        failed.append("ZERO_CASH_COST")

    if provider.get("auto_eligible") is not True:
        failed.append("AUTO_ELIGIBLE")

    missing_env = [
        name for name in provider.get("requires_env", []) if name not in runtime.env_names
    ]
    if missing_env:
        failed.append("REQUIRED_ENV_PRESENT")

    if provider.get("requires_gpu") and not runtime.cuda_ready:
        failed.append("GPU_READY")

    marker = provider.get("runtime_marker")
    if marker and marker not in runtime.ready_markers:
        failed.append("RUNTIME_CERTIFIED")

    origin = provider.get("media_origin")
    if requirement.real_footage_required and origin != "real_footage":
        failed.append("REAL_FOOTAGE")
    if requirement.generated_video_required and origin != "generated_video":
        failed.append("GENERATED_VIDEO")

    if requirement.commercial_use and not _commercial_rights_pass(
        provider, license_attested
    ):
        failed.append("COMMERCIAL_RIGHTS")

    if requirement.native_full_hd_vertical_required:
        resolution_failure = _native_resolution_gate(
            provider, provider_id, resolution_attested
        )
        if resolution_failure:
            failed.append(resolution_failure)

    return ProviderDecision(provider_id, not failed, tuple(failed))


def select_zero_cost_pipeline(
    requirement: FreeVideoRequirement,
    runtime: RuntimeCapabilities | None = None,
    *,
    catalog: dict[str, Any] | None = None,
    verified_free_quota: Iterable[str] = (),
    license_attested: Iterable[str] = (),
    resolution_attested: Iterable[str] = (),
) -> ZeroCostSelection:
    catalog = catalog or load_catalog()
    runtime = runtime or RuntimeCapabilities.detect()
    quota = set(verified_free_quota)
    licenses = set(license_attested)
    resolutions = set(resolution_attested)

    sources = sorted(
        (p for p in catalog["providers"] if p.get("role") == "source"),
        key=lambda p: int(p.get("priority", 9999)),
    )
    decisions = tuple(
        evaluate_source_provider(
            provider,
            requirement,
            runtime,
            verified_free_quota=quota,
            license_attested=licenses,
            resolution_attested=resolutions,
        )
        for provider in sources
    )
    selected = next((decision.provider_id for decision in decisions if decision.allowed), None)

    composer = None
    failed: list[str] = []
    if runtime.ffmpeg_available:
        composer = "ffmpeg_local"
    else:
        failed.append("FFMPEG_AVAILABLE")
    if selected is None:
        failed.append("ZERO_COST_SOURCE_AVAILABLE")

    return ZeroCostSelection(
        selected_provider_id=selected,
        composer_id=composer,
        authorized=not failed,
        decisions=decisions,
        failed_gates=tuple(failed),
    )


def load_resolution_attestations(paths: Iterable[str | Path]) -> set[str]:
    """Load benchmark evidence; never accepts a bare boolean."""
    providers: set[str] = set()
    for value in paths:
        path = Path(value)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("passed") is not True:
            raise ValueError(f"invalid resolution attestation: {path}")
        provider_id = str(data.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError(f"resolution attestation missing provider_id: {path}")
        width = int(data.get("native_width") or 0)
        height = int(data.get("native_height") or 0)
        if width < 1080 or height < 1920 or height <= width:
            raise ValueError(f"attestation is not native Full-HD vertical: {path}")
        if data.get("upscaled") is not False:
            raise ValueError(f"upscaled evidence cannot attest native resolution: {path}")
        sha256 = str(data.get("artifact_sha256") or "")
        if not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"resolution attestation has invalid artifact_sha256: {path}")
        providers.add(provider_id)
    return providers


def readiness_manifest(
    runtime: RuntimeCapabilities | None = None,
    *,
    catalog: dict[str, Any] | None = None,
    verified_free_quota: Iterable[str] = (),
    license_attested: Iterable[str] = (),
    resolution_attested: Iterable[str] = (),
) -> dict[str, Any]:
    runtime = runtime or RuntimeCapabilities.detect()
    catalog = catalog or load_catalog()
    real = select_zero_cost_pipeline(
        FreeVideoRequirement(real_footage_required=True),
        runtime,
        catalog=catalog,
        verified_free_quota=verified_free_quota,
        license_attested=license_attested,
        resolution_attested=resolution_attested,
    )
    generated_native_fhd = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True),
        runtime,
        catalog=catalog,
        verified_free_quota=verified_free_quota,
        license_attested=license_attested,
        resolution_attested=resolution_attested,
    )
    generated_720p = select_zero_cost_pipeline(
        FreeVideoRequirement(
            generated_video_required=True,
            native_full_hd_vertical_required=False,
        ),
        runtime,
        catalog=catalog,
        verified_free_quota=verified_free_quota,
        license_attested=license_attested,
        resolution_attested=resolution_attested,
    )
    return {
        "policy": "ZERO_EXTERNAL_CASH_COST",
        "max_external_cash_cost_usd": 0.0,
        "autonomous_purchase_allowed": False,
        "paid_fallback_allowed": False,
        "runtime": {
            "ffmpeg_available": runtime.ffmpeg_available,
            "cuda_ready": runtime.cuda_ready,
            "ready_markers": sorted(runtime.ready_markers),
        },
        "real_footage_route": {
            "authorized": real.authorized,
            "source": real.selected_provider_id,
            "composer": real.composer_id,
            "failed_gates": list(real.failed_gates),
        },
        "generated_video_native_fhd_route": {
            "authorized": generated_native_fhd.authorized,
            "source": generated_native_fhd.selected_provider_id,
            "composer": generated_native_fhd.composer_id,
            "failed_gates": list(generated_native_fhd.failed_gates),
        },
        "generated_video_720p_route": {
            "authorized": generated_720p.authorized,
            "source": generated_720p.selected_provider_id,
            "composer": generated_720p.composer_id,
            "failed_gates": list(generated_720p.failed_gates),
        },
        "generated_video_route": {
            "authorized": generated_native_fhd.authorized,
            "source": generated_native_fhd.selected_provider_id,
            "composer": generated_native_fhd.composer_id,
            "failed_gates": list(generated_native_fhd.failed_gates),
        },
        "publication_authorized": False,
        "publication_note": "Publishing remains a separate human-approved action.",
    }
