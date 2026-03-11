import cloudinary
import cloudinary.uploader

from app.config.settings import settings

# Configure once at import time
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

FOLDER = "gold-shop"


def upload_image(file_bytes: bytes, filename: str) -> str:
    """
    Uploads image bytes to Cloudinary under the gold-shop/ folder.
    Returns the secure HTTPS URL of the uploaded image.
    """
    # Use the original filename (without extension) as the public_id
    # so re-uploading the same file overwrites it instead of creating duplicates.
    public_id = f"{FOLDER}/{filename.rsplit('.', 1)[0]}"

    result = cloudinary.uploader.upload(
        file_bytes,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
        # Auto-optimize: serve WebP/AVIF to modern browsers, compress quality
        transformation=[
            {"quality": "auto", "fetch_format": "auto"},
        ],
    )
    return result["secure_url"]


def delete_image(public_id: str) -> None:
    """Deletes an image from Cloudinary by its public_id."""
    cloudinary.uploader.destroy(public_id)
