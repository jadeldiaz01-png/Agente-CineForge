from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_facebook_mcp_publisher import free_stock
from meta_facebook_mcp_publisher.free_stock import (
    FreeStockError,
    StockVideoCandidate,
    choose_native_full_hd_vertical,
)
from meta_facebook_mcp_publisher.free_video import (
    FreeVideoRequirement,
    RuntimeCapabilities,
    load_catalog,
    load_resolution_attestations,
    readiness_manifest,
    select_zero_cost_pipeline,
    validate_catalog,
)


def runtime(*, ffmpeg=True, cuda=False, env=(), markers=()):
    return RuntimeCapabilities(ffmpeg, cuda, frozenset(env), frozenset(markers))


def test_catalog_is_packaged_zero_cost_and_fail_closed() -> None:
    catalog = load_catalog()
    validate_catalog(catalog)
    assert catalog["schema_version"] >= 2
    assert catalog["policy"]["max_external_cash_cost_usd"] == 0.0
    assert catalog["policy"]["autonomous_purchase_allowed"] is False
    assert catalog["policy"]["paid_fallback_allowed"] is False
    assert not any(
        p["auto_eligible"] and p["cash_cost_policy"] == "free_quota"
        for p in catalog["providers"]
    )


def test_real_footage_route_is_keyless_via_wikimedia() -> None:
    result = select_zero_cost_pipeline(
        FreeVideoRequirement(real_footage_required=True), runtime()
    )
    assert result.authorized is True
    assert result.selected_provider_id == "wikimedia_commons_api"
    assert result.composer_id == "ffmpeg_local"


def test_generated_route_without_gpu_fails_closed() -> None:
    result = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True), runtime()
    )
    assert result.authorized is False
    assert "ZERO_COST_SOURCE_AVAILABLE" in result.failed_gates


def test_ffmpeg_is_mandatory_for_automated_master() -> None:
    result = select_zero_cost_pipeline(
        FreeVideoRequirement(real_footage_required=True), runtime(ffmpeg=False)
    )
    assert result.selected_provider_id == "wikimedia_commons_api"
    assert result.authorized is False
    assert "FFMPEG_AVAILABLE" in result.failed_gates


def test_wan22_is_never_native_full_hd_but_can_be_720p() -> None:
    rt = runtime(cuda=True, markers={"CINEFORGE_GPU_READY", "CINEFORGE_WAN22_READY"})
    native = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True), rt
    )
    assert native.authorized is False
    wan = next(d for d in native.decisions if d.provider_id == "wan22_local")
    assert "NATIVE_FULL_HD_UNSUPPORTED" in wan.failed_gates

    hd = select_zero_cost_pipeline(
        FreeVideoRequirement(generated_video_required=True, native_full_hd_vertical_required=False), rt
    )
    assert hd.authorized is True
    assert hd.selected_provider_id == "wan22_local"


def test_readiness_separates_native_fhd_from_720p() -> None:
    rt = runtime(cuda=True, markers={"CINEFORGE_GPU_READY", "CINEFORGE_WAN22_READY"})
    manifest = readiness_manifest(rt)
    assert manifest["generated_video_native_fhd_route"]["authorized"] is False
    assert manifest["generated_video_720p_route"]["authorized"] is True


def test_resolution_attestation_rejects_upscale(tmp_path: Path) -> None:
    p = tmp_path / "attestation.json"
    p.write_text(json.dumps({
        "schema_version": 1, "passed": True, "provider_id": "example",
        "native_width": 1080, "native_height": 1920, "upscaled": True,
        "artifact_sha256": "a" * 64,
    }))
    with pytest.raises(ValueError, match="upscaled"):
        load_resolution_attestations([p])


def test_resolution_attestation_requires_real_hash_and_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "attestation.json"
    p.write_text(json.dumps({
        "schema_version": 1, "passed": True, "provider_id": "example",
        "native_width": 1080, "native_height": 1920, "upscaled": False,
        "artifact_sha256": "b" * 64,
    }))
    assert load_resolution_attestations([p]) == {"example"}


def commons_payload(*, license_name="CC BY 4.0", license_review_needed=False):
    cats = [{"title": "Category:License review needed"}] if license_review_needed else []
    page = {
        "pageid": 1,
        "title": "File:Example.webm",
        "categories": cats,
        "imageinfo": [{
            "url": "https://upload.wikimedia.org/example.webm",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.webm",
            "width": 1080,
            "height": 1920,
            "mime": "video/webm",
            "extmetadata": {
                "LicenseShortName": {"value": license_name},
                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/" if license_name == "CC BY 4.0" else "https://creativecommons.org/licenses/by-sa/4.0/"},
                "Artist": {"value": "Example Creator"},
            },
        }],
    }
    return {"query": {"pages": {"1": page}}}


def test_wikimedia_cc_by_keyless_parser(monkeypatch) -> None:
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: commons_payload())
    c = free_stock.lookup_wikimedia_commons_file("File:Example.webm")
    assert c.provider == "wikimedia_commons"
    assert c.license_name == "CC BY 4.0"
    assert c.is_native_full_hd_vertical


def test_wikimedia_sharealike_requires_explicit_opt_in(monkeypatch) -> None:
    payload = commons_payload(license_name="CC BY-SA 4.0")
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: payload)
    with pytest.raises(FreeStockError):
        free_stock.lookup_wikimedia_commons_file("File:Example.webm")
    c = free_stock.lookup_wikimedia_commons_file("File:Example.webm", allow_share_alike=True)
    assert c.share_alike is True


def test_wikimedia_license_review_needed_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        free_stock, "_read_json",
        lambda request, timeout=30: commons_payload(license_review_needed=True),
    )
    with pytest.raises(FreeStockError):
        free_stock.lookup_wikimedia_commons_file("File:Example.webm")


def test_download_rejects_untrusted_host(tmp_path: Path) -> None:
    c = StockVideoCandidate(
        "wikimedia_commons", "1", "https://commons.wikimedia.org/wiki/File:X",
        "x", "https://evil.example/x.mp4", 1080, 1920, 1,
        "https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"
    )
    with pytest.raises(FreeStockError, match="allowlisted"):
        free_stock.download_with_provenance(c, tmp_path / "x.mp4")


def test_full_hd_vertical_selector_rejects_upscaled_claims() -> None:
    candidates = [
        StockVideoCandidate("pexels", "1", "https://example.test/1", "a", "https://cdn.test/1.mp4", 720, 1280, 10, "https://license.test"),
        StockVideoCandidate("pexels", "2", "https://example.test/2", "b", "https://cdn.test/2.mp4", 1080, 1920, 10, "https://license.test"),
        StockVideoCandidate("pexels", "3", "https://example.test/3", "c", "https://cdn.test/3.mp4", 2160, 3840, 10, "https://license.test"),
    ]
    selected = choose_native_full_hd_vertical(candidates)
    assert selected is not None and selected.asset_id == "3"


def test_pexels_parser_preserves_source_dimensions(monkeypatch) -> None:
    payload = {"videos": [{"id": 99,"url": "https://www.pexels.com/video/99/","duration": 8,"user": {"name": "Example Creator"},"video_files": [{"file_type": "video/mp4", "link": "https://videos.pexels.com/720.mp4", "width": 720, "height": 1280},{"file_type": "video/mp4", "link": "https://videos.pexels.com/4k.mp4", "width": 2160, "height": 3840}]}]}
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: payload)
    result = free_stock.search_pexels_vertical("morning", "secret")
    assert (result[0].width, result[0].height) == (2160, 3840)


def test_pixabay_parser_filters_to_best_variant(monkeypatch) -> None:
    payload = {"hits": [{"id": 88,"pageURL": "https://pixabay.com/videos/id-88/","user": "Example","duration": 12,"videos": {"medium": {"url": "https://cdn.pixabay.com/m.mp4", "width": 720, "height": 1280},"large": {"url": "https://cdn.pixabay.com/l.mp4", "width": 1080, "height": 1920}}}]}
    monkeypatch.setattr(free_stock, "_read_json", lambda request, timeout=30: payload)
    result = free_stock.search_pixabay_vertical("coffee", "secret")
    assert (result[0].width, result[0].height) == (1080, 1920)
