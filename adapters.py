from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from config import DS100_TOC_SNAPSHOT, SITES
from models import Chapter, ExtractionRequest
from scraper import HttpClient, absolutize_url, extract_main_content

NUMBERED_TITLE_RE = re.compile(r"^\d+(?:\.\d+)*\b")


def normalized_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(path=path, query="", fragment="").geturl()


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return "index"
    return path.split("/")[-1] or "index"


def clean_text(text: str) -> str:
    cleaned = " ".join(text.split())
    for suffix in (" chevron-right", " chevron-left", " chevron-down", " chevron-up"):
        cleaned = cleaned.replace(suffix, "")
    return cleaned.strip()


def is_numbered_title(title: str) -> bool:
    return bool(NUMBERED_TITLE_RE.match(title))


def _same_domain(url: str, base_url: str) -> bool:
    return urlparse(url).netloc == urlparse(base_url).netloc


def _looks_like_book_page(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if not path:
        return True
    return not path.endswith((
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".zip",
        ".json",
        ".xml",
        ".txt",
        ".css",
        ".js",
    ))


class BaseAdapter(ABC):
    site_id: str
    site_tech: str

    def __init__(self, *, base_url: str | None = None, label: str | None = None, subtitle: str | None = None) -> None:
        site = SITES.get(getattr(self, "site_id", ""), {})
        default_base_url = site.get("base_url", "")
        self.base_url = normalized_url(base_url or default_base_url)
        if not self.base_url:
            raise ValueError("A base URL is required for this adapter.")
        default_label = site.get("label") or urlparse(self.base_url).netloc
        self.label = label or default_label
        self.subtitle = subtitle or site.get("subtitle", "")

    def make_chapter(self, title: str, url: str, order: int, is_frontmatter: bool = False) -> Chapter:
        return Chapter(
            title=title,
            url=normalized_url(url),
            slug=slug_from_url(url),
            order=order,
            is_frontmatter=is_frontmatter,
        )

    @abstractmethod
    def discover_toc(self, client: HttpClient, include_frontmatter: bool) -> list[Chapter]:
        raise NotImplementedError

    def fetch_soup(self, chapter: Chapter, client: HttpClient) -> BeautifulSoup:
        return client.get_soup(chapter.url)

    def extract_root(self, soup: BeautifulSoup):
        return extract_main_content(soup)

    def snapshot(self) -> list[tuple[str, str]] | None:
        return None


class DS100Adapter(BaseAdapter):
    site_id = "ds100"
    site_tech = "myst"

    def discover_toc(self, client: HttpClient, include_frontmatter: bool) -> list[Chapter]:
        soup = client.get_soup(self.base_url)
        root = extract_main_content(soup)
        chapters: list[Chapter] = []
        seen: set[str] = set()

        if include_frontmatter and root:
            h1 = root.find("h1")
            title = clean_text(h1.get_text(" ", strip=True)) if h1 else "Welcome"
            chapters.append(self.make_chapter(title or "Welcome", self.base_url, 1, True))
            seen.add(normalized_url(self.base_url))

        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href:
                continue
            full_url = normalized_url(absolutize_url(self.base_url, href))
            parsed = urlparse(full_url)
            if parsed.netloc != "ds100.org":
                continue
            if not full_url.startswith("https://ds100.org/course-notes"):
                continue
            if full_url.endswith(".md"):
                continue
            if full_url in seen:
                continue
            if full_url == normalized_url(self.base_url):
                continue
            title = clean_text(link.get_text(" ", strip=True))
            if not title:
                continue
            seen.add(full_url)
            chapters.append(self.make_chapter(title, full_url, len(chapters) + 1))

        return chapters

    def snapshot(self) -> list[tuple[str, str]] | None:
        return DS100_TOC_SNAPSHOT


class MySTAdapter(BaseAdapter):
    site_id = "custom"
    site_tech = "myst"

    def __init__(self, *, base_url: str, label: str | None = None, subtitle: str | None = None) -> None:
        parsed = urlparse(base_url)
        label = label or parsed.netloc
        subtitle = subtitle or "MyST Export"
        super().__init__(base_url=base_url, label=label, subtitle=subtitle)

    def discover_toc(self, client: HttpClient, include_frontmatter: bool) -> list[Chapter]:
        soup = client.get_soup(self.base_url)
        root = extract_main_content(soup)
        nav = self._find_nav_root(soup)
        self._ensure_root_url(soup, nav)

        chained_chapters = self._discover_by_next_links(client, include_frontmatter)
        recursive_chapters = self._discover_by_recursive_nav(
            client,
            include_frontmatter,
            initial_soup=soup,
            initial_root=root,
            initial_nav=nav,
        )

        chapters = recursive_chapters if len(recursive_chapters) > len(chained_chapters) else chained_chapters
        if len(chapters) > 1:
            return chapters

        raise RuntimeError(
            "Could not discover a full MyST book from this URL. Please provide the book root or home URL."
        )

    def _ensure_root_url(self, soup: BeautifulSoup, nav: Tag | None) -> None:
        root = extract_main_content(soup)
        if root and self._find_prev_page(root, self.base_url):
            raise RuntimeError(
                "This MyST page is not the book root or home URL. Please provide the book root or home URL."
            )
        if nav is None:
            raise RuntimeError(
                "Could not find a MyST table of contents. Please provide the book root or home URL."
            )
        candidates = [url for url, _ in self._extract_nav_links(nav)]
        candidates.append(self.base_url)
        home_url = min(candidates, key=self._root_sort_key)
        if normalized_url(home_url) != self.base_url:
            raise RuntimeError(
                "This MyST page is not the book root or home URL. Please provide the book root or home URL."
            )

    def _root_sort_key(self, url: str) -> tuple[int, int, str]:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        depth = len([part for part in path.split("/") if part])
        return depth, len(path), path

    def _discover_by_next_links(self, client: HttpClient, include_frontmatter: bool) -> list[Chapter]:
        chapters: list[Chapter] = []
        seen: set[str] = set()
        current_url = self.base_url
        max_pages = 500

        for _ in range(max_pages):
            if current_url in seen:
                break
            if not _same_domain(current_url, self.base_url):
                break
            seen.add(current_url)

            soup = client.get_soup(current_url)
            root = extract_main_content(soup)
            if root is None:
                break

            title = self._extract_page_title(root, fallback=current_url)
            is_frontmatter = current_url == self.base_url
            if include_frontmatter or not is_frontmatter:
                chapters.append(self.make_chapter(title, current_url, len(chapters) + 1, is_frontmatter))

            next_url = self._find_next_page(root, current_url)
            if not next_url:
                break
            current_url = next_url

        return chapters

    def _discover_by_recursive_nav(
        self,
        client: HttpClient,
        include_frontmatter: bool,
        *,
        initial_soup: BeautifulSoup,
        initial_root,
        initial_nav: Tag | None,
    ) -> list[Chapter]:
        ordered_urls: list[str] = []
        seen: set[str] = set()
        queue: list[str] = []
        soup_cache: dict[str, BeautifulSoup] = {self.base_url: initial_soup}
        root_cache: dict[str, Tag | None] = {self.base_url: initial_root}
        nav_cache: dict[str, Tag | None] = {self.base_url: initial_nav}

        def enqueue(url: str) -> None:
            if url in seen:
                return
            seen.add(url)
            ordered_urls.append(url)
            queue.append(url)

        enqueue(self.base_url)
        if initial_nav is not None:
            for url, _ in self._extract_nav_links(initial_nav):
                enqueue(url)

        cursor = 0
        while cursor < len(queue) and len(ordered_urls) < 500:
            page_url = queue[cursor]
            cursor += 1

            soup = soup_cache.get(page_url)
            if soup is None:
                soup = client.get_soup(page_url)
                soup_cache[page_url] = soup
            root = root_cache.get(page_url)
            if root is None:
                root = extract_main_content(soup)
                root_cache[page_url] = root
            nav = nav_cache.get(page_url)
            if nav is None:
                nav = self._find_nav_root(soup)
                nav_cache[page_url] = nav

            if root:
                next_url = self._find_next_page(root, page_url)
                if next_url:
                    enqueue(next_url)
            if nav:
                for url, _ in self._extract_nav_links(nav):
                    enqueue(url)

        chapters: list[Chapter] = []
        for url in ordered_urls:
            soup = soup_cache.get(url)
            if soup is None:
                soup = client.get_soup(url)
                soup_cache[url] = soup
            root = root_cache.get(url)
            if root is None:
                root = extract_main_content(soup)
                root_cache[url] = root
            if root is None:
                continue
            title = self._extract_page_title(root, fallback=url)
            is_frontmatter = url == self.base_url
            if include_frontmatter or not is_frontmatter:
                chapters.append(self.make_chapter(title, url, len(chapters) + 1, is_frontmatter))
        return chapters

    def _extract_page_title(self, root: Tag, fallback: str) -> str:
        heading = root.find("h1")
        title = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        return title or fallback

    def _find_prev_page(self, root: Tag, current_url: str) -> str | None:
        return self._find_footer_page(root, current_url, direction="prev")

    def _find_next_page(self, root: Tag, current_url: str) -> str | None:
        return self._find_footer_page(root, current_url, direction="next")

    def _find_footer_page(self, root: Tag, current_url: str, *, direction: str) -> str | None:
        class_marker = f"myst-footer-link-{direction}"
        title_marker = "next" if direction == "next" else "previous"
        for link in root.find_all("a", href=True):
            classes = link.get("class") or []
            text = clean_text(link.get_text(" ", strip=True)).lower()
            if class_marker not in classes and not text.startswith(title_marker):
                continue
            candidate = normalized_url(absolutize_url(current_url, link["href"]))
            if _same_domain(candidate, self.base_url) and candidate != current_url and _looks_like_book_page(candidate):
                return candidate
        return None

    def _find_nav_root(self, soup: BeautifulSoup) -> Tag | None:
        selectors = (
            "nav.myst-primary-sidebar-toc",
            ".myst-primary-sidebar-nav",
            ".myst-toc",
            "nav.bd-links",
            ".bd-sidebar-primary",
            "[aria-label='Table of contents']",
            "[aria-label='table of contents']",
        )
        for selector in selectors:
            node = soup.select_one(selector)
            if node and self._count_valid_links(node) >= 2:
                return node

        best_node: Tag | None = None
        best_score = 0
        for tag in soup.find_all(["nav", "aside", "div", "ul"]):
            classes = " ".join(tag.get("class") or []).lower()
            element_id = (tag.get("id") or "").lower()
            haystack = f"{classes} {element_id}"
            if not any(term in haystack for term in ("myst", "sidebar", "toc", "contents", "navigation", "bd-")):
                continue
            score = self._count_valid_links(tag)
            if score > best_score:
                best_node = tag
                best_score = score
        return best_node if best_score >= 2 else None

    def _count_valid_links(self, node: Tag) -> int:
        return len(self._extract_nav_links(node))

    def _extract_nav_links(self, node: Tag) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for link in node.find_all("a", href=True):
            href = link.get("href", "").strip()
            title = clean_text(link.get_text(" ", strip=True))
            if not href or not title:
                continue
            if href.startswith("#"):
                continue
            url = normalized_url(absolutize_url(self.base_url, href))
            if not _same_domain(url, self.base_url):
                continue
            if not _looks_like_book_page(url):
                continue
            if url == self.base_url or url in seen:
                continue
            seen.add(url)
            pairs.append((url, title))
        return pairs


class GitBookAdapter(BaseAdapter):
    site_id = "custom"
    site_tech = "gitbook"

    def __init__(self, *, base_url: str, label: str | None = None, subtitle: str | None = None) -> None:
        parsed = urlparse(base_url)
        label = label or parsed.netloc
        subtitle = subtitle or "GitBook Export"
        super().__init__(base_url=base_url, label=label, subtitle=subtitle)

    def discover_toc(self, client: HttpClient, include_frontmatter: bool) -> list[Chapter]:
        chapters: list[Chapter] = []
        seen: set[str] = set()
        current_url = normalized_url(self.base_url)
        numbered_section_seen = False
        max_pages = 500

        for _ in range(max_pages):
            if current_url in seen:
                break
            if not _same_domain(current_url, self.base_url):
                break
            seen.add(current_url)

            soup = client.get_soup(current_url)
            root = extract_main_content(soup)
            if root is None:
                break

            heading = root.find("h1")
            title = clean_text(heading.get_text(" ", strip=True)) if heading else current_url
            page_is_frontmatter = not numbered_section_seen and not is_numbered_title(title)
            if is_numbered_title(title):
                numbered_section_seen = True

            if include_frontmatter or not page_is_frontmatter:
                chapters.append(self.make_chapter(title, current_url, len(chapters) + 1, page_is_frontmatter))

            next_url = self._find_next_page(root, current_url)
            if not next_url:
                break
            current_url = next_url

        return chapters

    def _find_next_page(self, root: Tag, current_url: str) -> str | None:
        for link in root.find_all("a", href=True):
            label = clean_text(link.get_text(" ", strip=True))
            if not label.startswith("Next "):
                continue
            candidate = normalized_url(absolutize_url(current_url, link["href"]))
            if _same_domain(candidate, self.base_url) and candidate != current_url and _looks_like_book_page(candidate):
                return candidate
        return None


class CS61BAdapter(GitBookAdapter):
    site_id = "cs61b"

    def __init__(self) -> None:
        super().__init__(
            base_url=SITES["cs61b"]["base_url"],
            label=SITES["cs61b"]["label"],
            subtitle=SITES["cs61b"]["subtitle"],
        )


def detect_site_technology(base_url: str, client: HttpClient) -> str:
    soup = client.get_soup(base_url)
    html = str(soup).lower()

    meta_generator = " ".join(
        (meta.get("content", "") or "")
        for meta in soup.find_all("meta")
        if (meta.get("name") or "").lower() == "generator"
    ).lower()

    if "gitbook" in meta_generator or "gitbook" in html or soup.find("aside", class_=lambda value: value and "group/table-of-contents" in " ".join(value if isinstance(value, list) else [value])):
        return "gitbook"

    if "myst" in meta_generator or "made with myst" in html or soup.select_one(".myst-toc, nav.myst-primary-sidebar-toc, .myst-primary-sidebar-nav"):
        return "myst"

    raise ValueError("Unsupported custom URL. Only MyST and GitBook textbooks are supported.")


def resolve_adapter(request: ExtractionRequest, client: HttpClient | None = None) -> BaseAdapter:
    if request.site_id == "ds100":
        request.site_tech = "myst"
        return DS100Adapter()
    if request.site_id == "cs61b":
        request.site_tech = "gitbook"
        return CS61BAdapter()
    if request.site_id != "custom":
        raise ValueError(f"Unsupported site: {request.site_id}")
    if not request.base_url:
        raise ValueError("A URL is required for custom extraction.")
    if client is None:
        raise ValueError("A client is required to resolve a custom adapter.")

    detected_tech = detect_site_technology(request.base_url, client)
    request.site_tech = detected_tech
    if detected_tech == "gitbook":
        return GitBookAdapter(base_url=request.base_url)
    if detected_tech == "myst":
        return MySTAdapter(base_url=request.base_url)
    raise ValueError("Unsupported custom URL. Only MyST and GitBook textbooks are supported.")


def get_adapter(site_id: str) -> BaseAdapter:
    if site_id == "ds100":
        return DS100Adapter()
    if site_id == "cs61b":
        return CS61BAdapter()
    raise ValueError(f"Unsupported site: {site_id}")
