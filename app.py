#!/usr/bin/env python3

import argparse
from pathlib import Path
from urllib.parse import urlparse

from config import (
    DEFAULT_HTML_WORKERS,
    DEFAULT_IMAGE_PROFILE,
    DEFAULT_IMAGE_WORKERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_TIMEOUT,
    OUTPUT_DIR,
    SITES,
)
from models import ExtractionOptions, ExtractionRequest
from services import extract_book, validate_ds100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export textbook websites to a single PDF.")
    parser.add_argument("site", nargs="?", choices=["ds100", "cs61b", "custom"])
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-frontmatter", action="store_true")
    parser.add_argument("--image-profile", choices=["fast", "balanced", "high"], default=DEFAULT_IMAGE_PROFILE)
    parser.add_argument("--debug-html", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--html-workers", type=int, default=DEFAULT_HTML_WORKERS)
    parser.add_argument("--image-workers", type=int, default=DEFAULT_IMAGE_WORKERS)
    return parser


def prompt_for_site() -> str:
    options = {
        "1": "ds100",
        "2": "cs61b",
        "3": "custom",
    }
    print("Select a textbook to export:")
    print("1. Data C100")
    print("2. CS 61B")
    print("3. Custom URL (MyST or GitBook)")
    while True:
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice in options:
            return options[choice]
        print("Invalid selection. Please enter 1, 2, or 3.")


def prompt_for_url() -> str:
    while True:
        value = input("Enter the book root URL: ").strip()
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value
        print("Invalid URL. Please enter a full http:// or https:// URL.")


def build_request(args: argparse.Namespace) -> ExtractionRequest:
    options = ExtractionOptions(
        include_frontmatter=not args.skip_frontmatter,
        image_profile=args.image_profile,
        output_dir=OUTPUT_DIR,
        output_path=args.output,
        timeout=args.timeout,
        request_delay=args.request_delay,
        max_retries=args.max_retries,
        html_workers=args.html_workers,
        image_workers=args.image_workers,
        refresh=args.refresh,
        debug_html=args.debug_html,
    )
    return ExtractionRequest(site_id=args.site, base_url=args.url, options=options)


def print_validation(report) -> int:
    print(f"Site: {report.site_id}")
    print(f"Discovered chapters: {len(report.discovered)}")
    print(f"Missing from live: {len(report.missing_from_live)}")
    for title, url in report.missing_from_live:
        print(f"  - {title} | {url}")
    print(f"Extra in live: {len(report.extra_in_live)}")
    for title, url in report.extra_in_live:
        print(f"  - {title} | {url}")
    print(f"Title mismatches: {len(report.title_mismatches)}")
    for url, expected, actual in report.title_mismatches:
        print(f"  - {url}")
        print(f"    expected: {expected}")
        print(f"    actual: {actual}")
    print(f"Order mismatches: {len(report.order_mismatches)}")
    for expected_index, title, url in report.order_mismatches:
        print(f"  - expected order {expected_index}: {title} | {url}")
    return 1 if (report.missing_from_live or report.extra_in_live or report.title_mismatches or report.order_mismatches) else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.site is None:
        args.site = prompt_for_site()
    if args.site == "custom" and not args.url:
        args.url = prompt_for_url()
    request = build_request(args)

    if args.validate:
        if args.site != "ds100":
            parser.error("--validate is only supported for ds100")
        return print_validation(validate_ds100(request))

    if args.site == "custom":
        if not request.base_url:
            parser.error("--url is required for custom extraction")
        print(f"Site: {request.base_url}")
    else:
        print(f"Site: {SITES[args.site]['base_url']}")
    print(f"Include frontmatter: {request.options.include_frontmatter}")
    print(f"Image profile: {request.options.image_profile}")
    print(f"Refresh cache: {request.options.refresh or args.site == 'custom'}")

    try:
        result = extract_book(request, progress=print)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    size_mb = result.output_path.stat().st_size / 1024 / 1024
    print(f"\nDone: {result.output_path}")
    print(f"File size: {size_mb:.1f} MB")
    print(f"Sections: {len(result.chapters)}")
    if result.failed:
        print(f"Sections with warnings: {len(result.failed)}")
        for title, error in result.failed:
            print(f"  - {title}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
