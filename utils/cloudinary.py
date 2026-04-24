"""
Cloudinary image upload utility.
Uses Cloudinary REST API directly via httpx (no SDK needed).
Uploads images to the 'egolist-events' folder in Cloudinary.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/upload"
FOLDER = "egolist-events"

DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://gorod.dp.ua/",
}


def _sign(params: dict) -> str:
    """Generate Cloudinary API signature: SHA-1 of sorted params + api_secret."""
    # Sort params alphabetically, exclude api_key / resource_type / file
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
    Download image from source_url and upload to Cloudinary.
    Returns the Cloudinary secure_url or None on failure.
    """
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
        return None

    try:
        # Step 1: download original image
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=DOWNLOAD_HEADERS,
        ) as client:
            resp = await client.get(source_url)
            if resp.status_code != 200 or "image" not in resp.headers.get("content-type", ""):
                logger.warning("cloudinary: failed to download %s (HTTP %d)", source_url, resp.status_code)
                return None
            image_bytes = resp.content

        # Step 2: upload to Cloudinary
        ts = int(time.time())
        params = {
            "folder": FOLDER,
            "public_id": public_id,
            "timestamp": ts,
            "api_key": settings.CLOUDINARY_API_KEY,
        }
        params["signature"] = _sign(params)

        async with httpx.AsyncClient(timeout=30) as client:
            upload_resp = await client.post(
                UPLOAD_URL,
                data=params,
                files={"file": ("photo.jpg", image_bytes, "image/jpeg")},
            )
            if upload_resp.status_code != 200:
                logger.warning("cloudinary: upload failed for %s: %s", public_id, upload_resp.text[:200])
                return None

            data = upload_resp.json()
            url = data.get("secure_url")
            logger.info("cloudinary: uploaded %s → %s", public_id, url)
            return url

    except Exception as e:
        logger.warning("cloudinary: error uploading %s: %s", public_id, e)
        return None
