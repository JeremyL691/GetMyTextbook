import hashlib
from pathlib import Path

from config import HTML_CACHE_DIR, IMAGE_CACHE_DIR


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def ensure_cache_dirs() -> None:
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def html_cache_path(url: str) -> Path:
    ensure_cache_dirs()
    return HTML_CACHE_DIR / f"{_url_hash(url)}.html"


def image_cache_path(url: str, profile: str) -> Path:
    ensure_cache_dirs()
    return IMAGE_CACHE_DIR / f"{_url_hash(f'{profile}:{url}')}.txt"
