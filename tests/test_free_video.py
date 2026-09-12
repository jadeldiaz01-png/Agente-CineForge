from __future__ import annotations

from meta_facebook_mcp_publisher import free_stock
from meta_facebook_mcp_publisher.free_stock import StockVideoCandidate, choose_native_full_hd_vertical
from meta_facebook_mcp_publisher.free_video import (
    FreeVideoRequirement,
    RuntimeCapabilities,
    load_catalog,
    select_zero_cost_pipeline,
    validate_catalog,
)


def test_catalog_is_zero_cost_and_fail_closed() -> None:
    catalog = load_catalog()
    validate_catalog(catalog)
    assert catalog["policy"]["max_external_cash_cost_usd"] == 0.0
    assert catalog["policy"]["autonomous_purchase_allowed"] is False
    assert not any(
        p["auto_eligible"] and p["cash_cost_policy"] == "free_quota"
        for p in catalog["providers"]
    )


def test_real_footage_route_prefers_free_stock_api() -> None:
    runtime = RuntimeCapabilities(
        ffmpeg_available=True,
        cuda_ready=False,
        env_names=frozenset({"PEXELS_API_KEY"}),
        ready_markers=frozenset(),
    )
    result = select_zero_cost_pipeline(
        FreeVideoRequirement(real_footage_required=True),
        runtime,
    )
    assert result.authorized is True
    assert result.selected_provider_id == "pexels_stock_api"
    assert result.composer_id == "ffmpeg_local"


def test_no_key_and_no_gpu_fails_closed() -> None:
    runtime = RuntimeCapabilities(
        ffmpeg_available=True,
        cuda_ready=False,
        env_names=frozenset(),
        ready_markers=frozenset(),
    )
    result = select_zero_cost_pipeline(FreeVideoRequirement(), runtime)
    assert result.authorized is False
    assert result.selected_provider_id is None
    assert "ZERO_COST_SOURCE_AVAILABLE" in result.failed_gates


def test_ffmpeg_is_mandatory_for_automated_master() -> None:
    runtime = RuntimeCapabilities(
        ffmpeg_available=False,
        cuda_ready=False,
        env_names=frozenset({"PIXABAY_API_KEY"}),
        ready_markers=frozenset(),
    )
    result = select_zero_cost_pipeline(
        FreeVideoRequirement(real_footage_required=True), runtime
    )
    assert result.selected_provider_id == "pixabay_stock_api"
    assert result.authorized is False
    assert "FFMPEG_AVAILABLE" in result.failed_gates


def test_wan22_requires_gpu_runtime_and_full_hd_benchmark() -> None:
    runtime = RuntimeCapabilities(
        ffmpeg_available=True,
        cuda_ready=True,
        env_names=frozenset(),
        ready_markers=frozenset({"CINEFORGE_GPU_READY", "CINEFORGE_WAN22_READY"}),
    )
    blocked = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True), runtime
    )
    assert blocked.authorized is False

    allowed = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True),
        runtime,
        resolution_attested={"wan22_local"},
    )
    assert allowed.authorized is True
    assert allowed.selected_provider_id == "wan22_local"


def test_ltx_is_not_auto_selected_without_manual_license_attestation() -> None:
    catalog = load_catalog()
    ltx = next(p for p in catalog["providers"] if p["id"] == "ltx2_local")
    assert ltx["auto_eligible"] is False
    assert ltx["commercial_use"] == "conditional_license"


def test_full_hd_vertical_selector_rejects_upscaled_claims() -> None:
    candidates = [
        StockVideoCandidate("pexels", "1", "https://example.test/1", "a", "https://cdn.test/1.mp4", 720, 1280, 10, "https://license.test"),
        StockVideoCandidate("pexels", "2", "https://example.test/2", "b", "https://cdn.test/2.mp4", 1080, 1920, 10, "https://license.test"),
        StockVideoCandidate("pexels", "3", "https://example.test/3", "c", "https://cdn.test/3.mp4", 2160, 3840, 10, "https://license.test"),
    ]
    selected = choose_native_full_hd_vertical(candidates)
    assert selected is not None
    assert selected.asset_id == "3"
    assert selected.is_native_full_hd_vertical is True


def test_pexels_parser_preserves_source_dimensions(monkeypatch) -> None:
    payload = {
        "videos": [
            {
                "id": 99,
                "url": "https://www.pexels.com/video/99/",
                "duration": 8,
                "user": {"name": "Example Creator"},
                "video_files": [
                    {"file_type": "video/mp4", "link": "https://cdn.example/720.mp4", "width": 720, "height": 1280},
                    {"file_type": "video/mp4", "link": "https://cdn.example/4k.mp4", "width": 2160, "height": 3840},
                ],
            }
        ]
    }
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: payload)
    result = free_stock.search_pexels_vertical("morning", "secret")
    assert result[0].width == 2160
    assert result[0].height == 3840
    assert result[0].is_native_full_hd_vertical is True


def test_pixabay_parser_filters_to_best_variant(monkeypatch) -> None:
    payload = {
        "hits": [
            {
                "id": 88,
                "pageURL": "https://pixabay.com/videos/id-88/",
                "user": "Example",
                "duration": 12,
                "videos": {
                    "medium": {"url": "https://cdn.example/m.mp4", "width": 720, "height": 1280},
                    "large": {"url": "https://cdn.example/l.mp4", "width": 1080, "height": 1920},
                },
            }
        ]
    }
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: payload)
    result = free_stock.search_pixabay_vertical("coffee", "secret")
    assert result[0].width == 1080
    assert result[0].height == 1920
    assert result[0].is_native_full_hd_vertical is True
