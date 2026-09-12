from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib, html, json, re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

PEXELS_LICENSE_URL = "https://www.pexels.com/license/"
PIXABAY_LICENSE_URL = "https://pixabay.com/service/license-summary/"
WIKIMEDIA_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
COMMONS_AUTO_LICENSES = frozenset({"CC0 1.0", "Public domain", "Public Domain", "CC BY 4.0", "CC BY 3.0"})
COMMONS_SHARE_ALIKE_LICENSES = frozenset({"CC BY-SA 4.0", "CC BY-SA 3.0"})
_ALLOWED_MEDIA_HOST_SUFFIXES = {"pexels": ("pexels.com",), "pixabay": ("pixabay.com",), "wikimedia_commons": ("wikimedia.org",)}

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
    license_name: str = ""
    share_alike: bool = False
    license_reviewed: bool = True

    @property
    def is_native_full_hd_vertical(self) -> bool:
        return self.width >= 1080 and self.height >= 1920 and self.height > self.width

def _https_only(url: str) -> None:
    if urlparse(url).scheme.lower() != "https":
        raise FreeStockError("Only HTTPS media URLs are permitted")

def _host_allowed(url: str, provider: str) -> bool:
    _https_only(url)
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in _ALLOWED_MEDIA_HOST_SUFFIXES.get(provider, ()))

def _require_allowed_media_host(url: str, provider: str) -> None:
    if not _host_allowed(url, provider):
        raise FreeStockError(f"Media host is not allowlisted for provider {provider}")

def _read_json(request: Request, *, timeout: int = 30) -> dict[str, Any]:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        _https_only(response.geturl())
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise FreeStockError("API response exceeded safety limit")
        return json.loads(body.decode("utf-8"))

def _clean_metadata(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(str(value or ""))).split())

def _commons_license_allowed(name: str, *, allow_share_alike: bool) -> bool:
    return name in COMMONS_AUTO_LICENSES or (allow_share_alike and name in COMMONS_SHARE_ALIKE_LICENSES)

def _commons_page_to_candidate(page: dict[str, Any], *, allow_share_alike: bool) -> StockVideoCandidate | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    width, height = int(info.get("width") or 0), int(info.get("height") or 0)
    source_url = str(info.get("url") or "")
    if width <= 0 or height <= 0 or not source_url or not _host_allowed(source_url, "wikimedia_commons"):
        return None
    categories = {str(x.get("title") or "").lower() for x in page.get("categories", []) if isinstance(x, dict)}
    if any("license review needed" in x for x in categories):
        return None
    ext = info.get("extmetadata") or {}
    license_name = _clean_metadata(ext.get("LicenseShortName"))
    if not _commons_license_allowed(license_name, allow_share_alike=allow_share_alike):
        return None
    license_url = _clean_metadata(ext.get("LicenseUrl"))
    if not license_url.startswith("https://"):
        return None
    title = str(page.get("title") or "")
    mime = str(info.get("mime") or "").lower()
    if not (mime.startswith("video/") or title.lower().endswith((".webm", ".ogv", ".ogg"))):
        return None
    return StockVideoCandidate("wikimedia_commons", title, str(info.get("descriptionurl") or ""), _clean_metadata(ext.get("Artist")) or _clean_metadata(ext.get("Credit")), source_url, width, height, None, license_url, license_name, license_name in COMMONS_SHARE_ALIKE_LICENSES, True)

def _commons_request(params: dict[str, Any], timeout: int) -> dict[str, Any]:
    params = dict(params, action="query", prop="imageinfo|categories", iiprop="url|size|mime|extmetadata", iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|Credit|UsageTerms", cllimit="max", format="json")
    return _read_json(Request(f"{WIKIMEDIA_COMMONS_API}?{urlencode(params)}", headers={"Accept":"application/json","User-Agent":"CineForge-ZeroCost/2026"}), timeout=timeout)

def search_wikimedia_commons_vertical(query: str, *, per_page: int = 20, timeout: int = 30, allow_share_alike: bool = False) -> list[StockVideoCandidate]:
    data = _commons_request({"generator":"search","gsrnamespace":6,"gsrsearch":f"{query} filetype:video","gsrlimit":max(1,min(per_page,50))}, timeout)
    pages = (data.get("query") or {}).get("pages") or {}
    values = pages.values() if isinstance(pages, dict) else pages
    out = []
    for page in values:
        c = _commons_page_to_candidate(page, allow_share_alike=allow_share_alike)
        if c is not None and c.height > c.width:
            out.append(c)
    return out

def lookup_wikimedia_commons_file(title: str, *, timeout: int = 30, allow_share_alike: bool = False) -> StockVideoCandidate:
    title = title if title.startswith("File:") else "File:" + title
    data = _commons_request({"titles": title}, timeout)
    pages = (data.get("query") or {}).get("pages") or {}
    values = list(pages.values()) if isinstance(pages, dict) else list(pages)
    if not values:
        raise FreeStockError("Wikimedia Commons file not found")
    c = _commons_page_to_candidate(values[0], allow_share_alike=allow_share_alike)
    if c is None:
        raise FreeStockError("Wikimedia Commons file did not pass media/license gates")
    return c

def search_pexels_vertical(query: str, api_key: str, *, per_page: int = 15, timeout: int = 30) -> list[StockVideoCandidate]:
    if not api_key.strip():
        raise FreeStockError("PEXELS_API_KEY is required")
    params = urlencode({"query":query,"orientation":"portrait","per_page":max(1,min(per_page,80))})
    data = _read_json(Request(f"https://api.pexels.com/v1/videos/search?{params}", headers={"Authorization":api_key,"Accept":"application/json"}), timeout=timeout)
    out=[]
    for video in data.get("videos", []):
        files=[x for x in video.get("video_files",[]) if str(x.get("file_type","")).lower()=="video/mp4" and str(x.get("link","")).startswith("https://")]
        if not files: continue
        best=max(files,key=lambda x:int(x.get("width") or 0)*int(x.get("height") or 0))
        out.append(StockVideoCandidate("pexels",str(video.get("id","")),str(video.get("url","")),str((video.get("user") or {}).get("name","")),str(best["link"]),int(best.get("width") or 0),int(best.get("height") or 0),float(video["duration"]) if video.get("duration") is not None else None,PEXELS_LICENSE_URL,"Pexels License"))
    return out

def search_pixabay_vertical(query: str, api_key: str, *, per_page: int = 20, timeout: int = 30) -> list[StockVideoCandidate]:
    if not api_key.strip():
        raise FreeStockError("PIXABAY_API_KEY is required")
    params=urlencode({"key":api_key,"q":query,"video_type":"film","safesearch":"true","order":"popular","per_page":max(3,min(per_page,200)),"min_width":1080,"min_height":1920})
    data=_read_json(Request(f"https://pixabay.com/api/videos/?{params}",headers={"Accept":"application/json"}),timeout=timeout)
    out=[]
    for hit in data.get("hits",[]):
        variants=[x for x in (hit.get("videos") or {}).values() if isinstance(x,dict) and str(x.get("url","")).startswith("https://")]
        if not variants: continue
        best=max(variants,key=lambda x:int(x.get("width") or 0)*int(x.get("height") or 0))
        out.append(StockVideoCandidate("pixabay",str(hit.get("id","")),str(hit.get("pageURL","")),str(hit.get("user","")),str(best["url"]),int(best.get("width") or 0),int(best.get("height") or 0),float(hit["duration"]) if hit.get("duration") is not None else None,PIXABAY_LICENSE_URL,"Pixabay Content License"))
    return out

def choose_native_full_hd_vertical(candidates: list[StockVideoCandidate]) -> StockVideoCandidate | None:
    eligible=[c for c in candidates if c.is_native_full_hd_vertical]
    return max(eligible,key=lambda c:c.width*c.height) if eligible else None

def download_with_provenance(candidate: StockVideoCandidate, destination: str | Path, *, timeout: int = 60, max_bytes: int = MAX_DOWNLOAD_BYTES) -> dict[str, Any]:
    if not candidate.is_native_full_hd_vertical:
        raise FreeStockError("Source asset is not native Full-HD vertical")
    if not candidate.license_reviewed:
        raise FreeStockError("Source asset license has not passed review")
    _require_allowed_media_host(candidate.source_url,candidate.provider)
    destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix(destination.suffix+".part")
    digest=hashlib.sha256(); total=0
    try:
        with urlopen(Request(candidate.source_url,headers={"User-Agent":"CineForge-ZeroCost/2026"}),timeout=timeout) as response, temporary.open("wb") as output:  # noqa: S310
            _require_allowed_media_host(response.geturl(),candidate.provider)
            content_length=response.headers.get("Content-Length")
            if content_length and int(content_length)>max_bytes:
                raise FreeStockError("Video exceeds configured download limit")
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                total += len(chunk)
                if total>max_bytes: raise FreeStockError("Video exceeded configured download limit")
                digest.update(chunk); output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True); raise
    provenance={"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":digest.hexdigest(),"bytes":total,"asset":asdict(candidate),"rights_review_required":True,"human_release_approval_required":True,"attribution_required":bool(candidate.contributor),"share_alike_obligation":candidate.share_alike}
    destination.with_suffix(destination.suffix+".provenance.json").write_text(json.dumps(provenance,indent=2,sort_keys=True),encoding="utf-8")
    return provenance
