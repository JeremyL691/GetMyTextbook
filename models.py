from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Chapter:
    title: str
    url: str
    slug: str
    order: int
    is_frontmatter: bool = False


@dataclass
class ExtractionOptions:
    include_frontmatter: bool = True
    image_profile: str = "fast"
    output_dir: Path = Path("output")
    output_path: Path | None = None
    timeout: int = 20
    request_delay: float = 0.0
    max_retries: int = 3
    html_workers: int = 8
    image_workers: int = 12
    refresh: bool = False
    debug_html: bool = False


@dataclass
class ExtractionRequest:
    site_id: str
    base_url: str | None = None
    site_tech: str | None = None
    options: ExtractionOptions = field(default_factory=ExtractionOptions)


@dataclass
class ExtractionResult:
    site_id: str
    output_path: Path
    debug_html_path: Path | None
    chapters: list[Chapter]
    failed: list[tuple[str, str]]


@dataclass
class ValidationReport:
    site_id: str
    discovered: list[Chapter]
    missing_from_live: list[tuple[str, str]]
    extra_in_live: list[tuple[str, str]]
    title_mismatches: list[tuple[str, str, str]]
    order_mismatches: list[tuple[int, str, str]]


ProgressCallback = Callable[[str], None]
