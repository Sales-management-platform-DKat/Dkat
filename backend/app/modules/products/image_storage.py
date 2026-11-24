import os
import warnings
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_TYPES = {
    "image/jpeg": ("jpg", "JPEG"),
    "image/png": ("png", "PNG"),
    "image/webp": ("webp", "WEBP"),
}
MAX_IMAGE_PIXELS = 40_000_000
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_configured_directory = Path(os.getenv("DKAT_PRODUCT_IMAGE_DIR", "uploads/products")).expanduser()
IMAGE_DIR = (_configured_directory if _configured_directory.is_absolute() else _BACKEND_ROOT / _configured_directory).resolve()


def save_product_image(content: bytes, declared_type: str | None) -> tuple[str, str]:
    if not content:
        raise HTTPException(422, "Tệp ảnh đang trống.")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise HTTPException(413, {"code": "PRODUCT_IMAGE_TOO_LARGE", "maxBytes": MAX_PRODUCT_IMAGE_BYTES})
    image_type = (declared_type or "").split(";", 1)[0].strip().lower()
    match = _IMAGE_TYPES.get(image_type)
    if match is None:
        raise HTTPException(415, "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP hợp lệ.")

    extension, expected_format = match
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Unsupported image format or dimensions")
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.seek(0)
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                normalized = BytesIO()
                if expected_format == "JPEG":
                    image.convert("RGB").save(normalized, format="JPEG", quality=90, optimize=True)
                elif expected_format == "PNG":
                    image.save(normalized, format="PNG", optimize=True)
                else:
                    image.save(normalized, format="WEBP", quality=90, method=4)
                content = normalized.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP hợp lệ.") from None

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = IMAGE_DIR / filename
    temporary = IMAGE_DIR / f".{filename}.tmp"
    try:
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return filename, image_type


def product_image_path(filename: str) -> Path:
    # Filenames are server-generated UUIDs; reject traversal and arbitrary names.
    if not any(filename.endswith(f".{extension}") for extension in ("jpg", "png", "webp")):
        raise HTTPException(404, "Không tìm thấy ảnh sản phẩm.")
    stem, _, extension = filename.rpartition(".")
    if len(stem) != 32 or any(char not in "0123456789abcdef" for char in stem):
        raise HTTPException(404, "Không tìm thấy ảnh sản phẩm.")
    path = (IMAGE_DIR / filename).resolve()
    if path.parent != IMAGE_DIR or not path.is_file():
        raise HTTPException(404, "Không tìm thấy ảnh sản phẩm.")
    return path
