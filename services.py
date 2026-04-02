from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from adapters import BaseAdapter, get_adapter, normalized_url, resolve_adapter
from html_builder import clean_content, collect_image_urls
from image_handler import fetch_image_data_uri
from models import Chapter, ExtractionRequest, ExtractionResult, ProgressCallback, ValidationReport
from pdf_renderer import build_full_html, render_pdf
from scraper import HttpClient


@dataclass
class ChapterPayload:
    chapter: Chapter
    root_html: object
    page_url: str


def _report(progress: ProgressCallback | None, message: str) -> None:
    if progress:
        progress(message)


def build_cover(title: str, subtitle: str, source_url: str) -> str:
    generated_on = date.today().isoformat()
    return f"""
<div class="cover-page">
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
  <hr style="width: 120pt; border: 1px solid #aaa; margin: 20pt auto;">
  <div class="meta">
    Source: {source_url}<br>
    Generated: {generated_on}
  </div>
</div>
"""


def build_toc(chapters: list[Chapter]) -> str:
    items = "".join(
        f'<li><a href="#{chapter.slug}">{index}. {chapter.title}</a></li>\n'
        for index, chapter in enumerate(chapters, 1)
    )
    return f"""
<div class="toc-page">
  <h2>Table of Contents</h2>
  <ol>
{items}  </ol>
</div>
"""


def _default_output_path(site_id: str, output_dir: Path) -> Path:
    return output_dir / f"{site_id}.pdf"


def _custom_output_name(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.replace(".", "_") or "custom"
    tail = parsed.path.rstrip("/").split("/")[-1] if parsed.path.rstrip("/") else ""
    if tail:
        tail = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in tail.lower())
        return f"{host}_{tail}.pdf"
    return f"{host}.pdf"


def _default_output_path_for_request(request: ExtractionRequest, adapter: BaseAdapter, output_dir: Path) -> Path:
    if request.site_id == "custom":
        return output_dir / _custom_output_name(adapter.base_url)
    return _default_output_path(request.site_id, output_dir)


def _fetch_chapter_payload(chapter: Chapter, adapter: BaseAdapter, client: HttpClient) -> ChapterPayload:
    soup = adapter.fetch_soup(chapter, client)
    root = adapter.extract_root(soup)
    if root is None:
        raise RuntimeError(f"No main content found for {chapter.url}")
    return ChapterPayload(chapter=chapter, root_html=root, page_url=chapter.url)


def _fetch_images(image_urls: list[str], image_profile: str, refresh: bool, workers: int, progress: ProgressCallback | None) -> dict[str, str | None]:
    results: dict[str, str | None] = {}
    if not image_urls:
        return results

    _report(progress, f"Fetching {len(image_urls)} images...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(fetch_image_data_uri, url, image_profile, refresh): url
            for url in image_urls
        }
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = None
    return results


def extract_book(request: ExtractionRequest, progress: ProgressCallback | None = None) -> ExtractionResult:
    options = request.options
    html_refresh = options.refresh or request.site_id == "custom"
    client = HttpClient(
        timeout=options.timeout,
        request_delay=options.request_delay,
        max_retries=options.max_retries,
        refresh=html_refresh,
    )
    adapter = resolve_adapter(request, client)

    if request.site_id == "custom":
        _report(progress, f"Detected technology: {request.site_tech}")

    _report(progress, "Discovering chapters...")
    chapters = adapter.discover_toc(client, options.include_frontmatter)
    if not chapters:
        raise RuntimeError("No chapters were discovered.")
    _report(progress, f"Discovered {len(chapters)} chapters.")

    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = options.output_path or _default_output_path_for_request(request, adapter, output_dir)
    debug_html_path = output_path.with_name(output_path.stem + "_debug.html") if options.debug_html else None

    payloads: list[ChapterPayload | None] = [None] * len(chapters)
    failed: list[tuple[str, str]] = []

    _report(progress, "Fetching chapter HTML...")
    with ThreadPoolExecutor(max_workers=options.html_workers) as executor:
        future_map = {
            executor.submit(_fetch_chapter_payload, chapter, adapter, client): index
            for index, chapter in enumerate(chapters)
        }
        completed = 0
        for future in as_completed(future_map):
            index = future_map[future]
            chapter = chapters[index]
            try:
                payloads[index] = future.result()
            except Exception as exc:
                failed.append((chapter.title, str(exc)))
            completed += 1
            _report(progress, f"Fetched chapters: {completed}/{len(chapters)}")

    image_urls: set[str] = set()
    for payload in payloads:
        if payload is None:
            continue
        image_urls.update(collect_image_urls(payload.root_html, payload.page_url))

    image_map = _fetch_images(
        sorted(image_urls),
        image_profile=options.image_profile,
        refresh=options.refresh,
        workers=options.image_workers,
        progress=progress,
    )

    _report(progress, "Building HTML...")
    chapters_html: list[str] = []
    for chapter, payload in zip(chapters, payloads):
        if payload is None:
            chapters_html.append(
                f'<div id="{chapter.slug}"><h1 class="chapter-title">{chapter.title}</h1>'
                f'<p style="color: red">Failed to fetch this section.</p></div>'
            )
            continue
        try:
            chapters_html.append(
                clean_content(
                    payload.root_html,
                    page_url=payload.page_url,
                    title=chapter.title,
                    chapter_id=chapter.slug,
                    image_map=image_map,
                    site_id=request.site_tech or request.site_id,
                )
            )
        except Exception as exc:
            failed.append((chapter.title, str(exc)))
            chapters_html.append(
                f'<div id="{chapter.slug}"><h1 class="chapter-title">{chapter.title}</h1>'
                f'<p style="color: red">Failed to render this section.</p></div>'
            )

    full_html = build_full_html(
        chapters_html,
        cover_html=build_cover(adapter.label, adapter.subtitle, adapter.base_url) + build_toc(chapters),
    )

    if debug_html_path is not None:
        debug_html_path.write_text(full_html, encoding="utf-8")
        _report(progress, f"Saved debug HTML: {debug_html_path}")

    _report(progress, "Rendering PDF...")
    render_pdf(full_html, str(output_path))
    _report(progress, f"Done: {output_path}")

    return ExtractionResult(
        site_id=request.site_id,
        output_path=output_path,
        debug_html_path=debug_html_path,
        chapters=chapters,
        failed=failed,
    )


def validate_ds100(request: ExtractionRequest) -> ValidationReport:
    if request.site_id != "ds100":
        raise ValueError("Validation is only supported for ds100.")

    adapter = get_adapter("ds100")
    client = HttpClient(
        timeout=request.options.timeout,
        request_delay=request.options.request_delay,
        max_retries=request.options.max_retries,
        refresh=request.options.refresh,
    )
    discovered = adapter.discover_toc(client, include_frontmatter=True)
    snapshot = adapter.snapshot() or []

    discovered_pairs = [(chapter.title, normalized_url(chapter.url)) for chapter in discovered]
    snapshot_urls = [normalized_url(url) for _, url in snapshot]
    discovered_urls = [url for _, url in discovered_pairs]

    missing_from_live = [(title, normalized_url(url)) for title, url in snapshot if normalized_url(url) not in discovered_urls]
    extra_in_live = [item for item in discovered_pairs if item[1] not in snapshot_urls]

    title_mismatches: list[tuple[str, str, str]] = []
    order_mismatches: list[tuple[int, str, str]] = []
    snapshot_map = {normalized_url(url): (index + 1, title) for index, (title, url) in enumerate(snapshot)}
    for index, chapter in enumerate(discovered, 1):
        chapter_url = normalized_url(chapter.url)
        if chapter_url not in snapshot_map:
            continue
        snapshot_index, snapshot_title = snapshot_map[chapter_url]
        if snapshot_title != chapter.title:
            title_mismatches.append((chapter_url, snapshot_title, chapter.title))
        if snapshot_index != index:
            order_mismatches.append((snapshot_index, chapter.title, chapter_url))

    return ValidationReport(
        site_id="ds100",
        discovered=discovered,
        missing_from_live=missing_from_live,
        extra_in_live=extra_in_live,
        title_mismatches=title_mismatches,
        order_mismatches=order_mismatches,
    )
