"""JekyllAdapter — supports Jekyll (just-the-docs) textbook sites like CS186."""

from urllib.parse import urlparse

from bs4 import Tag

from adapters import (
    BaseAdapter,
    Chapter,
    clean_text,
    normalized_url,
    slug_from_url,
    absolutize_url,
    _same_domain,
    _looks_like_book_page,
)
from scraper import HttpClient


class JekyllAdapter(BaseAdapter):
    site_id = "custom"
    site_tech = "jekyll"

    def make_chapter(self, title: str, url: str, order: int, is_frontmatter: bool = False) -> Chapter:
        # Jekyll sites use ../ relative image paths that depend on directory
        # semantics, so chapter URLs MUST keep their trailing slash.
        parsed = urlparse(url)
        path = parsed.path or "/"
        if not path.endswith("/"):
            path = path + "/"
        fixed = parsed._replace(path=path, query="", fragment="").geturl()
        return Chapter(
            title=title,
            url=fixed,
            slug=slug_from_url(url),
            order=order,
            is_frontmatter=is_frontmatter,
        )

    def discover_toc(self, client: HttpClient, include_frontmatter: bool) -> list:
        soup = client.get_soup(self.base_url)
        nav = self._find_nav_root(soup)
        chapters = []
        seen = set()

        if nav is not None:
            for url, title in self._extract_nav_links(nav):
                if url in seen:
                    continue
                seen.add(url)
                chapters.append(self.make_chapter(title, url, len(chapters) + 1))
        return chapters

    def extract_root(self, soup):
        # just-the-docs: main content lives in div.main-content (inside main-content-wrap)
        root = soup.find("div", class_="main-content")
        if root is None:
            root = soup.find("article")
        if root is None:
            root = soup.find("main")
        return root

    def _find_nav_root(self, soup: Tag | None):
        selectors = (
            "nav.site-nav",
            ".site-nav",
            "nav[aria-label='Main']",
            ".side-bar nav",
            "[aria-label='Table of contents']",
        )
        for selector in selectors:
            node = soup.select_one(selector) if soup else None
            if node and len(self._extract_nav_links(node)) >= 2:
                return node

        best_node = None
        best_score = 0
        if soup:
            for tag in soup.find_all(["nav", "aside", "div", "ul"]):
                classes = " ".join(tag.get("class") or []).lower()
                element_id = (tag.get("id") or "").lower()
                haystack = f"{classes} {element_id}"
                if not any(term in haystack for term in ("nav", "sidebar", "toc", "contents", "navigation", "site-")):
                    continue
                score = len(self._extract_nav_links(tag))
                if score > best_score:
                    best_node = tag
                    best_score = score
        return best_node if best_score >= 2 else None

    def _extract_nav_links(self, node: Tag) -> list:
        pairs = []
        seen = set()
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
