"""
Unit tests for Media Sanitizer and Anti-Abuse validation.
"""
import pytest
from fastapi import HTTPException
from app.services.extractor.sanitizer import MediaSanitizer


def test_sanitize_clean_query():
    clean = "The Weeknd Starboy"
    assert MediaSanitizer.sanitize_query_or_url(clean) == clean


def test_sanitize_command_injection_rejection():
    dangerous_inputs = [
        "https://youtube.com/watch?v=123; rm -rf /",
        "https://youtube.com/watch?v=123 | cat /etc/passwd",
        "https://youtube.com/watch?v=123 && echo hacked",
        "https://youtube.com/watch?v=123 `id`",
        "https://youtube.com/watch?v=123 $(whoami)",
        "https://youtube.com/watch?v=123 > /dev/null",
    ]
    for bad in dangerous_inputs:
        with pytest.raises(HTTPException) as exc_info:
            MediaSanitizer.sanitize_query_or_url(bad)
        assert exc_info.value.status_code == 400


def test_domain_whitelist_validation():
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp",
        "https://soundcloud.com/artist/track",
    ]
    for url in valid_urls:
        assert MediaSanitizer.validate_stream_url(url) == url

    invalid_urls = [
        "https://malicious-site.ru/payload.mp3",
        "https://evil-hacker.com/stream",
        "ftp://youtube.com/file",
    ]
    for bad_url in invalid_urls:
        with pytest.raises(HTTPException):
            MediaSanitizer.validate_stream_url(bad_url)


def test_duration_caps_and_live_stream_rejection():
    # 1. Live stream rejection on Free tier
    with pytest.raises(HTTPException) as exc:
        MediaSanitizer.validate_duration_and_live(
            duration_sec=0,
            is_live=True,
            tier="tier_free"
        )
    assert exc.value.status_code == 400

    # 2. Exceeding Free tier 20-min cap (1200s)
    with pytest.raises(HTTPException) as exc:
        MediaSanitizer.validate_duration_and_live(
            duration_sec=1500,
            is_live=False,
            tier="tier_free"
        )
    assert exc.value.status_code == 413

    # 3. Video blocked on Free tier
    with pytest.raises(HTTPException) as exc:
        MediaSanitizer.validate_duration_and_live(
            duration_sec=300,
            is_live=False,
            tier="tier_free",
            is_video=True
        )
    assert exc.value.status_code == 403

    # 4. Master key bypasses all limits
    MediaSanitizer.validate_duration_and_live(
        duration_sec=999999,
        is_live=True,
        tier="tier_free",
        is_video=True,
        is_master=True
    )
