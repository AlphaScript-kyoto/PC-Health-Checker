from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import DATA_DIR

NEWS_FEEDS: list[dict[str, str]] = [
    {
        "id": "pcwatch",
        "name": "PC Watch",
        "url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
    },
    {
        "id": "akiba",
        "name": "AKIBA PC Hotline!",
        "url": "https://akiba-pc.watch.impress.co.jp/data/rss/1.0/ah/feed.rdf",
    },
    {
        "id": "itmedia",
        "name": "ITmedia PC USER",
        "url": "https://rss.itmedia.co.jp/rss/2.0/pcuser.xml",
    },
]

_HARDWARE_KEYWORDS = (
    "SSD",
    "HDD",
    "NVMe",
    "GPU",
    "CPU",
    "Ryzen",
    "Core Ultra",
    "GeForce",
    "Radeon",
    "メモリ",
    "DDR",
    "マザー",
    "電源",
    "ケース",
    "クーラー",
    "ストレージ",
    "PCパーツ",
    "アキバ",
    "価格",
    "発売",
    "レビュー",
)

_cache: dict[str, Any] = {"fetched_at": 0.0, "items": []}
_CACHE_TTL_SEC = 30 * 60
_IMAGE_CACHE_PATH = DATA_DIR / "news_image_cache.json"
_image_cache: dict[str, str] = {}
_OG_FETCH_LIMIT = 24


def _load_image_cache() -> None:
    global _image_cache
    if _image_cache:
        return
    try:
        if _IMAGE_CACHE_PATH.exists():
            _image_cache = json.loads(_IMAGE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _image_cache = {}


def _save_image_cache() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Keep cache bounded
        items = list(_image_cache.items())[-400:]
        _IMAGE_CACHE_PATH.write_text(
            json.dumps(dict(items), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return " ".join(el.text.split())


def _parse_date(value: str) -> float:
    if not value:
        return 0.0
    try:
        return parsedate_to_datetime(value).timestamp()
    except Exception:
        pass
    try:
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _extract_image_from_html(html: str, base_url: str = "") -> str | None:
    if not html:
        return None
    patterns = (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    )
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            src = m.group(1).strip()
            if src.startswith("//"):
                src = "https:" + src
            if base_url and src.startswith("/"):
                src = urljoin(base_url, src)
            if src.startswith("http"):
                return src
    return None


def _image_from_rss_node(node: ET.Element) -> str | None:
    # media:thumbnail / media:content / enclosure
    for child in node.iter():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("thumbnail", "content", "enclosure", "image"):
            url = (
                child.attrib.get("url")
                or child.attrib.get("href")
                or child.attrib.get("rdf:resource")
                or _text(child)
            )
            if url and url.startswith("http"):
                return url
    # description may contain HTML img
    for child in node:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("description", "summary", "content", "encoded"):
            # include nested text
            raw = ET.tostring(child, encoding="unicode")
            found = _extract_image_from_html(raw)
            if found:
                return found
    return None


def _parse_rss_or_rdf(xml_text: str, source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    nodes: list[ET.Element] = []
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag in ("item", "entry"):
            nodes.append(el)

    for node in nodes:
        title = ""
        link = ""
        summary = ""
        published = ""

        for child in node:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "title" and not title:
                title = _text(child)
            elif tag in ("link", "guid") and not link:
                href = child.attrib.get("href") or _text(child)
                if href:
                    link = href
            elif tag in ("description", "summary", "content", "encoded") and not summary:
                # strip tags lightly
                raw = _text(child) or re.sub(r"<[^>]+>", " ", ET.tostring(child, encoding="unicode"))
                summary = " ".join(raw.split())[:220]
            elif tag in ("pubDate", "date", "updated", "published") and not published:
                published = _text(child)

        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "summary": summary,
                "source": source,
                "published": published,
                "published_ts": _parse_date(published),
                "image": _image_from_rss_node(node),
            }
        )
    return items


def _is_hardware_ish(item: dict[str, Any], source_id: str) -> bool:
    if source_id in ("pcwatch", "akiba", "itmedia"):
        return True
    blob = f"{item.get('title', '')} {item.get('summary', '')}"
    return any(k.lower() in blob.lower() for k in _HARDWARE_KEYWORDS)


def _enrich_images(client: httpx.Client, items: list[dict[str, Any]]) -> None:
    _load_image_cache()
    fetched = 0
    for item in items:
        url = item.get("url") or ""
        if item.get("image"):
            continue
        if url in _image_cache:
            item["image"] = _image_cache[url]
            continue
        if fetched >= _OG_FETCH_LIMIT:
            continue
        try:
            resp = client.get(
                url,
                headers={
                    "User-Agent": "PCHealthMonitor/0.2 (local news; +https://127.0.0.1)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=8.0,
            )
            if resp.status_code >= 400:
                continue
            img = _extract_image_from_html(resp.text, base_url=str(resp.url))
            if img:
                item["image"] = img
                _image_cache[url] = img
                fetched += 1
        except Exception:
            continue
    if fetched:
        _save_image_cache()


def fetch_news(force: bool = False, limit: int = 40) -> dict[str, Any]:
    now = time.time()
    if not force and _cache["items"] and now - float(_cache["fetched_at"]) < _CACHE_TTL_SEC:
        return {
            "fetched_at": _cache["fetched_at"],
            "cached": True,
            "items": _cache["items"][:limit],
        }

    collected: list[dict[str, Any]] = []
    errors: list[str] = []

    headers = {
        "User-Agent": "PCHealthMonitor/0.2 (local RSS reader; +https://127.0.0.1)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
        for feed in NEWS_FEEDS:
            try:
                resp = client.get(feed["url"])
                if resp.status_code >= 400:
                    errors.append(f"{feed['name']}: HTTP {resp.status_code}")
                    continue
                parsed = _parse_rss_or_rdf(resp.text, feed["name"])
                for item in parsed:
                    if _is_hardware_ish(item, feed["id"]):
                        collected.append(item)
            except Exception as exc:
                errors.append(f"{feed['name']}: {exc}")

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in collected:
            key = (item.get("url") or item.get("title") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)

        unique.sort(key=lambda x: x.get("published_ts") or 0, reverse=True)
        _enrich_images(client, unique[:limit])

    _cache["fetched_at"] = now
    _cache["items"] = unique

    return {
        "fetched_at": now,
        "cached": False,
        "items": unique[:limit],
        "errors": errors,
    }
