from copy import deepcopy
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

from image_handler import resolve_image_url

SKIP_TAGS = {"script", "style", "noscript", "svg"}
DROP_CLASSES = {
    "myst-jp-nb-block-spinner",
    "myst-code-copy-icon",
    "myst-fm-block-badges",
    "myst-fm-block-header",
    "myst-fm-downloads-dropdown",
    "button",
    "button-content",
    "button-leading-icon",
    "gb-icon",
}


def collect_image_urls(root, page_url: str) -> list[str]:
    urls: list[str] = []
    for image in root.find_all("img"):
        src = image.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        urls.append(resolve_image_url(src, page_url))
    return urls


def clean_content(root, page_url: str, title: str, chapter_id: str, image_map: dict[str, str | None], site_id: str) -> str:
    cleaned = deepcopy(root)
    _remove_noise(cleaned, site_id=site_id)
    _normalize_math(cleaned)
    _normalize_admonitions(cleaned)
    _normalize_code_blocks(cleaned)
    _normalize_headings(cleaned, title)
    _normalize_links(cleaned, page_url)
    _apply_images(cleaned, page_url, image_map)
    _strip_attributes(cleaned)
    cleaned["id"] = chapter_id
    return str(cleaned)


def _remove_noise(root, site_id: str) -> None:
    for tag_name in SKIP_TAGS:
        for tag in root.find_all(tag_name):
            tag.decompose()

    for tag in list(root.find_all(True)):
        if not isinstance(tag, Tag) or tag.attrs is None:
            continue
        classes = set(tag.get("class") or [])
        text = " ".join(tag.get_text(" ", strip=True).split())

        if tag.get("aria-hidden") == "true":
            tag.decompose()
            continue
        if tag.name in {"button", "nav"}:
            tag.decompose()
            continue
        if classes & DROP_CLASSES and tag.name in {"button", "svg", "span", "div", "a"}:
            tag.decompose()
            continue
        if tag.name == "a" and (text.startswith("Next ") or text.startswith("Previous ")):
            tag.decompose()
            continue
        if tag.name == "p" and text.startswith("Last updated"):
            tag.decompose()
            continue

    if site_id in {"ds100", "myst"}:
        frontmatter = root.find("div", attrs={"aria-label": "article frontmatter"})
        if frontmatter:
            h1 = frontmatter.find("h1")
            if h1:
                frontmatter.replace_with(h1.extract())
            else:
                frontmatter.decompose()


def _normalize_math(root) -> None:
    for selector in (
        ("span", "katex-mathml"),
        ("span", "katex-display"),
        ("span", "katex"),
    ):
        for node in root.find_all(selector[0], class_=selector[1]):
            node.unwrap()


def _normalize_admonitions(root) -> None:
    for aside in root.find_all("aside"):
        classes = aside.get("class") or []
        if "myst-admonition" not in classes:
            continue
        admonition_type = "note"
        for item in classes:
            if item.startswith("myst-admonition-") and item != "myst-admonition":
                admonition_type = item.replace("myst-admonition-", "")
                break
        body = aside.find(class_="myst-admonition-body")
        body_children = [child.extract() for child in list(body.children)] if body else []
        title_node = aside.find(class_="myst-admonition-header-text")
        title_text = title_node.get_text(strip=True) if title_node else admonition_type.title()

        aside.clear()
        aside["class"] = ["admonition", f"admonition-{admonition_type}"]
        soup = BeautifulSoup("", "html.parser")
        title_div = soup.new_tag("div")
        title_div["class"] = ["admonition-title"]
        title_div.string = title_text
        body_div = soup.new_tag("div")
        body_div["class"] = ["admonition-body"]
        for child in body_children:
            body_div.append(child)
        aside.append(title_div)
        aside.append(body_div)


def _normalize_code_blocks(root) -> None:
    for pre in root.find_all("pre"):
        code = pre.find("code")
        text = code.get_text() if code else pre.get_text()
        language = ""
        if code:
            for css_class in code.get("class") or []:
                if css_class.startswith("language-"):
                    language = css_class
                    break
        pre.clear()
        pre.attrs = {}
        new_code = BeautifulSoup("", "html.parser").new_tag("code")
        if language:
            new_code["class"] = [language]
        new_code.string = text.rstrip("\n")
        pre.append(new_code)


def _normalize_headings(root, title: str) -> None:
    heading = root.find("h1")
    if heading is None:
        heading = BeautifulSoup("", "html.parser").new_tag("h1")
        heading.string = title
        root.insert(0, heading)
    else:
        heading.clear()
        heading.append(NavigableString(title))
    heading["class"] = ["chapter-title"]

    for item in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        for link in item.find_all("a"):
            if not link.get_text(strip=True) or link.get_text(strip=True) == "¶":
                link.decompose()
        for span in item.find_all("span", class_="heading-text"):
            span.unwrap()
        if item is not heading:
            item.attrs.pop("class", None)


def _normalize_links(root, page_url: str) -> None:
    for link in root.find_all("a"):
        href = link.get("href", "").strip()
        if not href:
            link.unwrap()
            continue
        absolute = urljoin(page_url, href)
        link.attrs = {"href": absolute}


def _apply_images(root, page_url: str, image_map: dict[str, str | None]) -> None:
    for image in root.find_all("img"):
        src = image.get("src", "").strip()
        if not src:
            image.decompose()
            continue
        if src.startswith("data:"):
            continue
        full_url = resolve_image_url(src, page_url)
        replacement = image_map.get(full_url)
        if replacement is None:
            image.decompose()
            continue
        image.attrs = {
            "src": replacement,
            "alt": image.get("alt", ""),
        }


def _strip_attributes(root) -> None:
    allowed = {"href", "src", "alt", "id", "class", "width", "height", "colspan", "rowspan", "open"}
    keep_classes = {"chapter-title", "admonition", "admonition-title", "admonition-body"}
    for tag in root.find_all(True):
        classes = [item for item in (tag.get("class") or []) if item in keep_classes or item.startswith("admonition-")]
        if classes:
            tag["class"] = classes
        else:
            tag.attrs.pop("class", None)
        for attr in list(tag.attrs.keys()):
            if attr not in allowed:
                del tag.attrs[attr]
