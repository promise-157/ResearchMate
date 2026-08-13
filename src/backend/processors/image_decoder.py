"""Deterministic, offline validation for user-imported raster images."""
import io
import warnings
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_WIDTH = 12_000
MAX_IMAGE_HEIGHT = 12_000
MAX_IMAGE_PIXELS = 40_000_000
SUPPORTED_FORMATS = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}

# Pillow checks dimensions before allocating decoded pixel buffers. Use our product
# limit for its decompression-bomb warning and turn that warning into a rejection.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


@dataclass(frozen=True)
class DecodedImage:
    mime_type: str
    suffix: str
    width: int
    height: int


def decode_image(data: bytes) -> DecodedImage:
    """Fully decode supported image bytes and return trusted image facts."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format
                if image_format not in SUPPORTED_FORMATS:
                    raise ValueError("仅支持完整有效的 PNG、JPEG 或 WebP 图片")
                width, height = image.size
                _check_dimensions(width, height)
                image.verify()

            # verify() checks the encoded structure but does not retain decoded
            # pixels. Reopen and load() to force decoding of the complete image.
            with Image.open(io.BytesIO(data)) as image:
                if image.format != image_format or image.size != (width, height):
                    raise ValueError("图片解码结果不一致")
                image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError(f"图片疑似解压炸弹，总像素不能超过 {MAX_IMAGE_PIXELS:,}") from exc
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("图片已损坏、格式伪装或无法完整解码") from exc

    mime_type, suffix = SUPPORTED_FORMATS[image_format]
    return DecodedImage(
        mime_type=mime_type,
        suffix=suffix,
        width=width,
        height=height,
    )


def _check_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("图片尺寸必须大于 0")
    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise ValueError(
            f"图片尺寸不能超过 {MAX_IMAGE_WIDTH:,} × {MAX_IMAGE_HEIGHT:,} 像素"
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"图片总像素不能超过 {MAX_IMAGE_PIXELS:,}")
