"""
Cloudinary image upload utility.
Uses Cloudinary REST API directly via httpx (no SDK needed).
Uploads images to the 'egolist-events' folder in Cloudinary.

Strategy: pass the source URL directly to Cloudinary — their servers
fetch the image themselves, bypassing any IP blocks on Railway.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

FOLDER = "egolist-events"


def _upload_url() -> str:
    return f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/upload"


def _sign(params: dict) -> str:
    """Generate Cloudinary API signature: SHA-1 of sorted params + api_secret."""
    exclude = {"api_key", "resource_type", "file"}
    parts = "&".join(
        f"{k}={v}"
        for k, v in sorted(params.items())
        if k not in exclude
    )
    raw = parts + settings.CLOUDINARY_API_SECRET
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def upload_image(source_url: str, public_id: str) -> Optional[str]:
    """
    Upload image to Cloudinary by passing the source URL directly.
    Cloudinary fetches the image from their side — no need to download it on Railway.
    Returns the Cloudinary secure_url or None on failure.
    """
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
        return None

    try:
        ts = int(time.time())
        params = {
            "folder": FOLDER,
            "public_id": public_id,
            "timestamp": ts,
            "api_key": settings.CLOUDINARY_API_KEY,
        }
        params["signature"] = _sign(params)
        # Pass source URL as 'file' — Cloudinary fetches it from their servers
        params["file"] = source_url

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_upload_url(), data=params)

        if resp.status_code != 200:
            logger.warning("cloudinary: upload failed for %s: HTTP %d — %s",
                           public_id, resp.status_code, resp.text[:300])
            return None

        data = resp.json()
        url = data.get("secure_url")
        logger.info("cloudinary: uploaded %s → %s", public_id, url)
        return url

    except Exception as e:
        logger.warning("cloudinary: error uploading %s: %s", public_id, e)
        return None
