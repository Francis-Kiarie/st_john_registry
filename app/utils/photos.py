import os
import uuid
from pathlib import Path
from PIL import Image
from fastapi import UploadFile, HTTPException

# Photos stored under uploads/members/
UPLOAD_DIR = Path("uploads/members")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 5
MAX_DIMENSION = 800  # resize to max 800x800 preserving aspect ratio


async def save_member_photo(file: UploadFile, member_id: str) -> str:
    """
    Validates, resizes, and saves a member photo.
    Returns the relative URL path to store in the database.
    """
    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: JPEG, PNG, WebP"
        )

    contents = await file.read()

    # Validate file size
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_SIZE_MB}MB"
        )

    # Validate it's actually an image using Pillow
    try:
        from io import BytesIO
        img = Image.open(BytesIO(contents))
        img.verify()  # checks file integrity
        img = Image.open(BytesIO(contents))  # reopen after verify (verify closes it)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file")

    # Convert to RGB (handles PNG with transparency)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Resize if larger than MAX_DIMENSION
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    # Save with a unique filename
    filename = f"{member_id}_{uuid.uuid4().hex[:8]}.jpg"
    save_path = UPLOAD_DIR / filename
    img.save(save_path, "JPEG", quality=85, optimize=True)

    return f"/uploads/members/{filename}"


def delete_member_photo(photo_url: str):
    """Deletes an old photo file when replacing it."""
    if not photo_url:
        return
    # Strip the leading slash and resolve relative to project root
    relative_path = photo_url.lstrip("/")
    path = Path(relative_path)
    if path.exists():
        path.unlink()