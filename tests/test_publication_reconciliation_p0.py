from __future__ import annotations
from meta_facebook_mcp_publisher.publication_reconciliation import tiktok_status, youtube_status


def tiktok(payload):
    return lambda method,url,token,body=None: payload


def youtube(payload):
    return lambda method,url,token,body=None: payload


def test_tiktok_processing_upload_not_public():
    result=tiktok_status("v_pub_x", "fake-token", tiktok({"error":{"code":"ok"},"data":{"status":"PROCESSING_UPLOAD"}}))
    assert not result.ok and result.status=="REMOTE_UNVERIFIED"


def test_tiktok_inbox_delivered_not_public():
    result=tiktok_status("v_pub_x", "fake-token", tiktok({"error":{"code":"ok"},"data":{"status":"SEND_TO_USER_INBOX"}}))
    assert not result.ok


def test_tiktok_publish_complete_without_public_id_not_public():
    result=tiktok_status("v_pub_x", "fake-token", tiktok({"error":{"code":"ok"},"data":{"status":"PUBLISH_COMPLETE","publicaly_available_post_id":[]}}))
    assert not result.ok


def test_tiktok_confirmed_public_only_with_official_id():
    result=tiktok_status("v_pub_x", "fake-token", tiktok({"error":{"code":"ok"},"data":{"status":"PUBLISH_COMPLETE","publicaly_available_post_id":[7333444555666]}}))
    assert result.ok and result.remote_id=="7333444555666" and result.status=="CONFIRMED_PUBLIC"


def test_tiktok_auth_or_remote_error_not_public():
    r=tiktok_status("v_pub_x","fake-token",tiktok({"error":{"code":"access_token_invalid"},"data":{"status":"PUBLISH_COMPLETE","publicaly_available_post_id":[7333444555666]}}))
    assert not r.ok
    assert not tiktok_status("x"*100,"token").ok


def test_youtube_processed_private_is_not_public():
    res=youtube_status("abc123def00","token",youtube({"items":[{"id":"abc123def00","status":{"uploadStatus":"processed","privacyStatus":"private"}}]}))
    assert not res.ok and res.status=="REMOTE_UNVERIFIED"


def test_youtube_public_processed_exact_id_only():
    good={"items":[{"id":"abc123def00","status":{"uploadStatus":"processed","privacyStatus":"public"}}]}
    result=youtube_status("abc123def00","token",youtube(good))
    assert result.ok and result.status=="CONFIRMED_PUBLIC"
    assert not youtube_status("different0","token",youtube(good)).ok


def test_youtube_uploaded_public_not_yet_processed():
    res=youtube_status("abc123def00","token",youtube({"items":[{"id":"abc123def00","status":{"uploadStatus":"uploaded","privacyStatus":"public"}}]}))
    assert not res.ok


def test_youtube_rejected_never_public():
    res=youtube_status("abc123def00","token",youtube({"items":[{"id":"abc123def00","status":{"uploadStatus":"rejected","privacyStatus":"public"}}]}))
    assert not res.ok and res.status=="REMOTE_FAILED"


def test_reconciliation_network_error_fails_closed():
    def broke(*args,**kwargs):
        raise OSError("simulated connection failure")
    assert not youtube_status("abc123def00","token",broke).ok
    assert not tiktok_status("v_pub_x","token",broke).ok
