import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests import exceptions as requests_exceptions

from cache_store import html_cache_path
from config import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_DELAY, DEFAULT_TIMEOUT, HEADERS


class HttpClient:
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        request_delay: float = DEFAULT_REQUEST_DELAY,
        max_retries: int = DEFAULT_MAX_RETRIES,
        refresh: bool = False,
    ) -> None:
        self.timeout = timeout
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.refresh = refresh
        self._html_memory_cache: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get(self, url: str) -> requests.Response:
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                if self.request_delay:
                    time.sleep(self.request_delay)
                return response
            except requests_exceptions.SSLError as exc:
                raise RuntimeError(f"HTTPS certificate verification failed for {url}: {exc}") from exc
            except requests_exceptions.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code == 429 and attempt < self.max_retries - 1:
                    wait = 2 ** attempt * 2
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"HTTP error for {url}: {exc}") from exc
            except requests_exceptions.Timeout as exc:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Timeout while fetching {url}") from exc
            except requests_exceptions.RequestException as exc:
                raise RuntimeError(f"Request failed for {url}: {exc}") from exc
        raise RuntimeError(f"Request failed after retries: {url}")

    def get_html(self, url: str) -> str:
        if url in self._html_memory_cache:
            return self._html_memory_cache[url]
        cache_path = html_cache_path(url)
        if cache_path.exists() and not self.refresh:
            html = cache_path.read_text(encoding="utf-8")
            self._html_memory_cache[url] = html
            return html
        html = self._fetch_html_following_meta_refresh(url)
        cache_path.write_text(html, encoding="utf-8")
        self._html_memory_cache[url] = html
        return html

    def get_soup(self, url: str) -> BeautifulSoup:
        return BeautifulSoup(self.get_html(url), "html.parser")

    def _fetch_html_following_meta_refresh(self, url: str, max_hops: int = 5) -> str:
        current_url = url
        visited: set[str] = set()
        for _ in range(max_hops):
            if current_url in visited:
                break
            visited.add(current_url)
            response = self.get(current_url)
            html = response.text
            redirect_url = self._extract_meta_refresh_url(html, current_url)
            if not redirect_url:
                return html
            current_url = redirect_url
        return html

    def _extract_meta_refresh_url(self, html: str, base_url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for meta in soup.find_all("meta"):
            http_equiv = (meta.get("http-equiv") or "").strip().lower()
            if http_equiv != "refresh":
                continue
            content = (meta.get("content") or "").strip()
            if not content:
                continue
            parts = [part.strip() for part in content.split(";")]
            for part in parts[1:]:
                if not part.lower().startswith("url="):
                    continue
                target = part.split("=", 1)[1].strip().strip("'\"")
                if target:
                    return absolutize_url(base_url, target)
        return None


def absolutize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def extract_main_content(soup: BeautifulSoup):
    return soup.find("article") or soup.find("main") or soup.find("body")
