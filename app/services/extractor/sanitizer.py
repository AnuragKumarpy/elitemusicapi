"""
URL Sanitizer and Security Validator for Media Ingestion.
Prevents command injection, validates domain whitelists, and enforces duration caps.
"""
import re
from urllib.parse import urlparse
from fastapi import HTTPException
from app.config import ALLOWED_MEDIA_DOMAINS, TIER_PLANS, PlanTierConfig


class MediaSanitizer:
    # Dangerous shell metacharacters for command injection prevention
    DANGEROUS_CHAR_PATTERN = re.compile(r"[;&|`$<>\x00\r\n]")

    @classmethod
    def sanitize_query_or_url(cls, raw_input: str) -> str:
        """
        Sanitize input query or URL. Rejects shell injection patterns.
        """
        cleaned = raw_input.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Media query cannot be empty.")

        if cls.DANGEROUS_CHAR_PATTERN.search(cleaned):
            raise HTTPException(
                status_code=400,
                detail="Security violation: Query contains disallowed shell control characters."
            )

        return cleaned

    @classmethod
    def validate_stream_url(cls, url: str) -> str:
        """
        Ensure URL is well-formed http/https and belongs to whitelisted domain list.
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URI scheme: '{parsed.scheme}'. Only HTTPS/HTTP are permitted."
            )

        hostname = (parsed.hostname or "").lower()
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in ALLOWED_MEDIA_DOMAINS):
            raise HTTPException(
                status_code=403,
                detail=f"Security violation: Domain '{hostname}' is not in the allowed media domain whitelist."
            )

        return url

    @classmethod
    def validate_duration_and_live(
        cls,
        duration_sec: int,
        is_live: bool,
        tier: str,
        is_video: bool = False,
        is_master: bool = False
    ) -> None:
        """
        Enforce duration ceilings and live-stream anti-exhaustion policies.
        """
        if is_master:
            return

        plan: PlanTierConfig = TIER_PLANS.get(tier, TIER_PLANS["tier_free"])

        # Check live streams
        if is_live and not plan.allow_live_stream:
            raise HTTPException(
                status_code=400,
                detail="Live streams are disabled to prevent infinite worker resource lockup."
            )

        max_allowed = plan.max_video_duration_sec if is_video else plan.max_audio_duration_sec

        if is_video and not plan.allow_video:
            raise HTTPException(
                status_code=403,
                detail=f"Video streaming is not enabled on {plan.name}. Upgrade to Pro or Enterprise."
            )

        if max_allowed > 0 and duration_sec > max_allowed:
            raise HTTPException(
                status_code=413,
                detail=f"Track length ({duration_sec}s) exceeds maximum permitted limit ({max_allowed}s) for {plan.name}."
            )
