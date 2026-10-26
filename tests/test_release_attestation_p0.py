from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from meta_facebook_mcp_publisher import release_attestation as release
from meta_facebook_mcp_publisher.cli import run
from meta_facebook_mcp_publisher import gates
from meta_facebook_mcp_publisher.models import Platform, PlatformPublishRequest
from meta_facebook_mcp_publisher.platform_clients import YouTubeClient, TikTokClient, XClient


def _mp4(tmp_path, monkeypatch):
    file=tmp_path/"video.mp4"
    file.write_bytes(b"video-for-controlled-ffprobe")
    response = {"streams":[{"codec_type":"video","codec_name":"h264","width":1080,"height":1920}],
                "format":{"duration":"24"}}
    monkeypatch.setattr(release.subprocess,"run",lambda *args,**kwargs: SimpleNamespace(stdout=json.dumps(response)))
    return file


def _approval(path, media, key="a"*40):
    payload={"version":1,"video_sha256":media["sha256"],"caption":"caption",
             "platforms":["youtube"],"approved_by":"human-owner",
             "human_approved":True,"video_qc_passed":True,"originality_reviewed":True,
             "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    sig=hmac.new(key.encode(),release.canonical(payload),hashlib.sha256).hexdigest()
    path.write_text(json.dumps({"payload":payload,"signature":sig}))
    return path


def test_signed_release_binds_exact_video_caption_and_platform(tmp_path, monkeypatch):
    video=_mp4(tmp_path,monkeypatch)
    media=release.inspect_mp4(video)
    e=_approval(tmp_path/"approval.json",media)
    assert release.verify_release(e,media,"caption",["youtube"],"a"*40)["approved_by"]=="human-owner"
    with pytest.raises(release.ReleaseDenied,match="MISMATCH"):
        release.verify_release(e,media,"changed",["youtube"],"a"*40)
    with pytest.raises(release.ReleaseDenied,match="MISMATCH"):
        release.verify_release(e,media,"caption",["tiktok"],"a"*40)
    video.write_bytes(b"modified-file")
    with pytest.raises(release.ReleaseDenied,match="MISMATCH"):
        release.verify_release(e,release.inspect_mp4(video),"caption",["youtube"],"a"*40)


def test_signature_and_expiry_are_required(tmp_path,monkeypatch):
    video=_mp4(tmp_path,monkeypatch)
    media=release.inspect_mp4(video)
    e=_approval(tmp_path/"approval.json",media)
    data=json.loads(e.read_text())
    data["payload"]["human_approved"]=False
    e.write_text(json.dumps(data))
    with pytest.raises(release.ReleaseDenied,match="SIGNATURE"):
        release.verify_release(e,media,"caption",["youtube"],"a"*40)
    with pytest.raises(release.ReleaseDenied,match="KEY"):
        release.verify_release(e,media,"caption",["youtube"],"short")


def test_dry_run_fails_without_real_media(monkeypatch,capsys):
    monkeypatch.setattr(sys,"argv",["cineforge","--video","/absent.mp4","--caption","caption",
                                   "--platforms","youtube","--idempotency-key","ref","--dry-run"])
    assert run()==2
    assert "VIDEO_QC_BLOCKED" in capsys.readouterr().out


def test_dry_run_checks_video_without_claiming_publish(tmp_path,monkeypatch,capsys):
    p=_mp4(tmp_path,monkeypatch)
    monkeypatch.setattr(sys,"argv",["cineforge","--video",str(p),"--caption","caption",
                                   "--platforms","youtube","--idempotency-key","ref","--dry-run"])
    assert run()==0
    out=capsys.readouterr().out
    assert "DRY_RUN_VALIDATED" in out and "remote_id=-" in out and "MEDIA_SHA256" in out


def test_live_blocked_without_separate_authorization(tmp_path,monkeypatch,capsys):
    p=_mp4(tmp_path,monkeypatch)
    monkeypatch.delenv("CINEFORGE_LIVE_PUBLISH_AUTHORIZED",raising=False)
    monkeypatch.setattr(sys,"argv",["cineforge","--video",str(p),"--caption","caption",
                                   "--platforms","youtube","--idempotency-key","ref"])
    assert run()==2
    assert "LIVE_BLOCKED" in capsys.readouterr().out


def _req(tmp_path,platform):
    file=tmp_path/"sample.mp4"
    file.write_bytes(b"controlled-mock-video")
    return PlatformPublishRequest(platform=platform,video_path=file,caption="approved",idempotency_key="key",
                                  human_approved=True,video_qc_passed=True,originality_reviewed=True,
                                  publishing_enabled=True,access_token="token",account_id="account")


def test_youtube_requires_final_binary_put(tmp_path, monkeypatch):
    monkeypatch.setattr(gates, "_release_gate", lambda *args: True)
    calls=[]
    def transport(method,url,payload,bytes_,headers):
        calls.append(method)
        if method=="POST":
            return {"headers":{"location":"https://www.googleapis.com/upload/youtube/v3/videos?upload_id=a"}}
        assert bytes_ == b"controlled-mock-video"
        return {"id":"remote-id"}
    out=YouTubeClient(transport=transport).publish_video(_req(tmp_path,Platform.YOUTUBE))
    assert out.ok and out.status=="UPLOAD_CONFIRMED" and calls==["POST","PUT"]


def test_youtube_rejects_session_only_and_untrusted_host(tmp_path, monkeypatch):
    monkeypatch.setattr(gates, "_release_gate", lambda *args: True)
    def untrusted(method,url,payload,bytes_,headers):
        return {"headers":{"location":"https://attacker.invalid/upload"}}
    assert not YouTubeClient(transport=untrusted).publish_video(_req(tmp_path,Platform.YOUTUBE)).ok
    def unconfirmed(method,url,payload,bytes_,headers):
        return {"headers":{"location":"https://www.googleapis.com/upload/youtube/v3/videos?upload_id=a"}} if method=="POST" else {}
    assert not YouTubeClient(transport=unconfirmed).publish_video(_req(tmp_path,Platform.YOUTUBE)).ok


def test_tiktok_never_treats_upload_as_published(tmp_path, monkeypatch):
    monkeypatch.setattr(gates, "_release_gate", lambda *args: True)
    calls=[]
    def transport(method,url,payload,bytes_,headers):
        calls.append(method)
        if method=="POST":
            return {"data":{"publish_id":"id","upload_url":"https://open-upload.tiktokapis.com/video/?id=x"}}
        return {"_http_status":201}
    res=TikTokClient(transport=transport).publish_video(_req(tmp_path,Platform.TIKTOK))
    assert calls==["POST","PUT"] and not res.ok and res.status=="DISPATCHED_UNVERIFIED"


def test_x_not_sent_without_upload_protocol(tmp_path, monkeypatch):
    monkeypatch.setattr(gates, "_release_gate", lambda *args: True)
    calls=[]
    def transport(*args):
        calls.append(args)
        return {"id":"forged"}
    res=XClient(transport=transport).publish_video(_req(tmp_path,Platform.X))
    assert not res.ok and res.status=="BLOCKED_BY_POLICY" and calls==[]


def test_direct_connector_cannot_bypass_signed_release(tmp_path):
    request=_req(tmp_path,Platform.YOUTUBE)
    result=YouTubeClient(transport=lambda *a: {"id":"forged"}).publish_video(request)
    assert not result.ok
    assert result.status=="BLOCKED_BY_POLICY"
    assert "SIGNED_CONTENT_BOUND_RELEASE" in (result.error or "")
