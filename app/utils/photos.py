import uuid
import os
from io import BytesIO
from PIL import Image
from fastapi import UploadFile, HTTPException
from app.config import settings

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 5
MAX_DIMENSION = 800


def _get_gcs_client():
    from google.cloud import storage
    return storage.Client()


def _process_image(contents: bytes) -> bytes:
    """Validate, resize and convert image to JPEG."""
    try:
        img = Image.open(BytesIO(contents))
        img.verify()
        img = Image.open(BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file")

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    output = BytesIO()
    img.save(output, "JPEG", quality=85, optimize=True)
    return output.getvalue()


async def save_member_photo(file: UploadFile, member_id: str) -> str:
    """
    Validates, resizes, and saves a member photo.
    - In production (GCS_BUCKET_NAME set): uploads to Google Cloud Storage
    - In local dev (no bucket): saves to local uploads/members/ folder
    Returns the URL or path to store in the database.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed: JPEG, PNG, WebP"
        )

    contents = await file.read()

    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_SIZE_MB}MB"
        )

    processed = _process_image(contents)
    filename = f"{member_id}_{uuid.uuid4().hex[:8]}.jpg"

    # ── Production: upload to GCS ─────────────────────────────────────────
    if settings.GCS_BUCKET_NAME:
        client = _get_gcs_client()
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(f"members/{filename}")
        blob.upload_from_string(processed, content_type="image/jpeg")
        blob.cache_control = "public, max-age=3600"
        blob.patch()
        # Return the public GCS URL
        return f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/members/{filename}"

    # ── Local dev: save to disk ───────────────────────────────────────────
    from pathlib import Path
    upload_dir = Path("uploads/members")
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / filename
    save_path.write_bytes(processed)
    return f"/uploads/members/{filename}"


def delete_member_photo(photo_url: str):
    """Deletes a photo from GCS or local disk."""
    if not photo_url:
        return

    # ── Production: delete from GCS ──────────────────────────────────────
    if settings.GCS_BUCKET_NAME and photo_url.startswith("https://storage.googleapis.com"):
        try:
            client = _get_gcs_client()
            bucket = client.bucket(settings.GCS_BUCKET_NAME)
            # Extract blob name from URL
            # URL format: https://storage.googleapis.com/BUCKET/members/filename.jpg
            blob_name = "/".join(photo_url.split("/")[4:])
            blob = bucket.blob(blob_name)
            blob.delete()
        except Exception:
            pass  # Non-fatal — log in production
        return

    # ── Local dev: delete from disk ──────────────────────────────────────
    from pathlib import Path
    relative_path = photo_url.lstrip("/")
    path = Path(relative_path)
    if path.exists():
        path.unlink()