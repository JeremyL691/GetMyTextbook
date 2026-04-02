import base64
import io
from urllib.parse import urljoin

import requests

from cache_store import image_cache_path
from config import DEFAULT_IMAGE_PROFILE, DEFAULT_TIMEOUT, HEADERS, IMAGE_PROFILES


def resolve_image_url(src: str, base_url: str) -> str:
    return urljoin(base_url, src)


def _compress_image(image_bytes: bytes, profile_name: str) -> tuple[bytes, str] | None:
    profile = IMAGE_PROFILES[profile_name]
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        if profile["skip_small_images"] and min(image.size) <= profile["min_dimension"]:
            return None

        if image.width > profile["max_width"]:
            ratio = profile["max_width"] / image.width
            new_height = int(image.height * ratio)
            image = image.resize((profile["max_width"], new_height), Image.LANCZOS)

        output = io.BytesIO()
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha:
            image.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"

        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(output, format="JPEG", quality=profile["jpeg_quality"], optimize=True)
        return output.getvalue(), "image/jpeg"
    except Exception:
        return None


def fetch_image_data_uri(url: str, image_profile: str = DEFAULT_IMAGE_PROFILE, refresh: bool = False) -> str | None:
    cache_path = image_cache_path(url, image_profile)
    if cache_path.exists() and not refresh:
        cached = cache_path.read_text(encoding="utf-8")
        return cached or None

    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        compressed = _compress_image(response.content, image_profile)
        if compressed is None:
            cache_path.write_text("", encoding="utf-8")
            return None
        content, mime = compressed
        data_uri = f"data:{mime};base64,{base64.b64encode(content).decode('utf-8')}"
        cache_path.write_text(data_uri, encoding="utf-8")
        return data_uri
    except Exception as exc:
        print(f"[WARN] Failed to fetch image {url}: {exc}")
        cache_path.write_text("", encoding="utf-8")
        return None
