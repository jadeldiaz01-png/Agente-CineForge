from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


PEXELS_LICENSE_URL = "https://www.pexels.com/license/"
PIXABAY_LICENSE_URL = "https://pixabay.com/service/license-summary/"
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


class FreeStockError(RuntimeError):
    pass


@dataclass(frozen=True)
class StockVideoCandidate:
    provider: str
    asset_id: str
    page_url: str
    contributor: str
    source_url: str
    width: int
    height: int
    duration_seconds: float | None
    license_url: str

    @property
    def is_native_full_hd_vertical(self) -> bool:
        return self.width >= 1080 and self.height >= 1920 and self.height > self.width


def _https_only(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise FreeStockError("Only HTTPS media URLs are permitted")


def _read_json(request: Request, *, timeout: int = 30) -> dict[str, Any]:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is fixed by caller
        final_url = response.geturl()
        _https_only(final_url)
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise FreeStockError("API response exceeded safety limit")
        return json.loads(body.decode("utf-8"))


def search_pexels_vertical(
    query: str,
    api_key: str,
    *,
    per_page: int = 15,
    timeout: int = 30,
) -> list[StockVideoCandidate]:
    if not api_key.strip():
        raise FreeStockError("PEXELS_API_KEY is required")
    params = urlencode({"query": query, "orientation": "portrait", "per_page": max(1, min(per_page, 80))})
    request = Request(
        f"https://api.pexels.com/v1/videos/search?{params}",
        headers={"Authorization": api_key, "Accept": "application/json"},
    )
    data = _read_json(request, timeout=timeout)
    candidates: list[StockVideoCandidate] = []
    for video in data.get("videos", []):
        files = [
            item
            for item in video.get("video_files", [])
            if str(item.get("file_type", "")).lower() == "video/mp4"
            and str(item.get("link", "")).startswith("https://")
        ]
        if not files:
            continue
        files.sort(key=lambda item: (int(item.get("width") or 0) * int(item.get("height") or 0)), reverse=True)
        best = files[0]
        candidates.append(
            StockVideoCandidate(
                provider="pexels",
                asset_id=str(video.get("id", "")),
                page_url=str(video.get("url", "")),
                contributor=str((video.get("user") or {}).get("name", "")),
                source_url=str(best["link"]),
                width=int(best.get("width") or 0),
                height=int(best.get("height") or 0),
                duration_seconds=float(video["duration"]) if video.get("duration") is not None else None,
                license_url=PEXELS_LICENSE_URL,
            )
        )
    return candidates


def search_pixabay_vertical(
    query: str,
    api_key: str,
    *,
    per_page: int = 20,
    timeout: int = 30,
) -> list[StockVideoCandidate]:
    if not api_key.strip():
        raise FreeStockError("PIXABAY_API_KEY is required")
    params = urlencode(
        {
            "key": api_key,
            "q": query,
            "video_type": "film",
            "safesearch": "true",
            "order": "popular",
            "per_page": max(3, min(per_page, 200)),
            "min_width": 1080,
            "min_height": 1920,
        }
    )
    request = Request(f"https://pixabay.com/api/videos/?{params}", headers={"Accept": "application/json"})
    data = _read_json(request, timeout=timeout)
    candidates: list[StockVideoCandidate] = []
    for hit in data.get("hits", []):
        variants = []
        for name, item in (hit.get("videos") or {}).items():
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", ""))
            if not url.startswith("https://"):
                continue
            variants.append(item)
        if not variants:
            continue
        variants.sort(key=lambda item: (int(item.get("width") or 0) * int(item.get("height") or 0)), reverse=True)
        best = variants[0]
        candidates.append(
            StockVideoCandidate(
                provider="pixabay",
                asset_id=str(hit.get("id", "")),
                page_url=str(hit.get("pageURL", "")),
                contributor=str(hit.get("user", "")),
                source_url=str(best["url"]),
                width=int(best.get("width") or 0),
                height=int(best.get("height") or 0),
                duration_seconds=float(hit["duration"]) if hit.get("duration") is not None else None,
                license_url=PIXABAY_LICENSE_URL,
            )
        )
    return candidates


def choose_native_full_hd_vertical(candidates: list[StockVideoCandidate]) -> StockVideoCandidate | None:
    eligible = [candidate for candidate in candidates if candidate.is_native_full_hd_vertical]
    if not eligible:
        return None
    return max(eligible, key=lambda candidate: candidate.width * candidate.height)


def download_with_provenance(
    candidate: StockVideoCandidate,
    destination: str | Path,
    *,
    timeout: int = 60,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> dict[str, Any]:
    if not candidate.is_native_full_hd_vertical:
        raise FreeStockError("Source asset is not native Full-HD vertical")
    _https_only(candidate.source_url)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    request = Request(candidate.source_url, headers={"User-Agent": "CineForge-ZeroCost/2026"})
    try:
        with urlopen(request, timeout=timeout) as response, temporary.open("wb") as output:  # noqa: S310
            _https_only(response.geturl())
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise FreeStockError("Video exceeds configured download limit")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FreeStockError("Video exceeded configured download limit")
                digest.update(chunk)
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    provenance = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
        "bytes": total,
        "asset": asdict(candidate),
        "rights_review_required": True,
        "human_release_approval_required": True,
    }
    sidecar = destination.with_suffix(destination.suffix + ".provenance.json")
    sidecar.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return provenance
