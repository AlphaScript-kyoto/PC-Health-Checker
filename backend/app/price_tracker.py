from __future__ import annotations

import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

from app import db
from app.parts_catalog import (
    CATALOG_VERSION,
    active_catalog_ids,
    catalog_by_id,
    get_catalog_grouped,
)

WEEK_SEC = 7 * 24 * 60 * 60


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_catalog_migration() -> dict[str, Any]:
    stored = db.get_catalog_version()
    version_changed = stored is not None and stored != CATALOG_VERSION
    active = active_catalog_ids()
    by_id = catalog_by_id()
    tracked = db.get_tracked_parts()
    orphans: list[dict[str, Any]] = []

    if stored != CATALOG_VERSION:
        if version_changed:
            for row in tracked:
                cid = row["catalog_id"]
                if cid not in active and not row.get("keep_legacy"):
                    db.mark_tracked_pending(cid, True)
        db.set_catalog_version(CATALOG_VERSION)
        tracked = db.get_tracked_parts()

    for row in tracked:
        cid = row["catalog_id"]
        if row.get("pending_decision") and not row.get("keep_legacy"):
            info = by_id.get(cid) or {
                "id": cid,
                "name": row.get("display_name") or cid,
                "category": row.get("category") or "legacy",
                "brand": "",
                "generation": "リスト外（旧世代）",
                "query": row.get("query") or cid,
            }
            orphans.append({**info, "tracked": True})

    return {
        "catalog_version": CATALOG_VERSION,
        "previous_version": stored,
        "orphans": orphans,
        "version_changed": version_changed,
    }


def get_tracker_state() -> dict[str, Any]:
    migration = ensure_catalog_migration()
    tracked = db.get_tracked_parts()
    tracked_ids = {t["catalog_id"] for t in tracked}
    by_id = catalog_by_id()
    active = active_catalog_ids()

    legacy_items = []
    for t in tracked:
        cid = t["catalog_id"]
        if cid not in active and t.get("keep_legacy"):
            snap = by_id.get(cid) or {
                "id": cid,
                "name": t.get("display_name") or cid,
                "category": t.get("category") or "legacy",
                "brand": "",
                "generation": "キープ中（旧世代）",
                "query": t.get("query") or cid,
            }
            legacy_items.append({**snap, "keep_legacy": True})

    latest_by_source = db.get_latest_prices_by_source(list(tracked_ids))
    overview = []
    for t in tracked:
        if t.get("pending_decision") and not t.get("keep_legacy"):
            continue
        cid = t["catalog_id"]
        meta = by_id.get(cid) or {
            "id": cid,
            "name": t.get("display_name") or cid,
            "category": t.get("category") or "legacy",
            "brand": "",
            "generation": "キープ中（旧世代）",
            "query": t.get("query") or "",
        }
        sources = latest_by_source.get(cid) or {}
        kakaku_hist = db.get_price_history(cid, limit=52, source="kakaku")
        amazon_hist = db.get_price_history(cid, limit=52, source="amazon")
        asin = db.get_meta(f"amazon_asin:{cid}")
        overview.append(
            {
                **meta,
                "tracked": True,
                "keep_legacy": bool(t.get("keep_legacy")),
                "latest_kakaku": sources.get("kakaku"),
                "latest_amazon": sources.get("amazon"),
                "kakaku_history": kakaku_hist,
                "amazon_history": amazon_hist,
                "kakaku_url": _kakaku_url(meta.get("query") or meta.get("name") or cid),
                "amazon_url": _amazon_url(meta.get("query") or meta.get("name") or cid),
                "amazon_asin": asin,
                "keepa_graph_url": keepa_graph_url(asin) if asin else None,
                "keepa_product_url": keepa_product_url(asin) if asin else None,
            }
        )

    return {
        "catalog_version": CATALOG_VERSION,
        "groups": get_catalog_grouped(),
        "tracked_ids": sorted(tracked_ids - {o["id"] for o in migration["orphans"]}),
        "overview": overview,
        "legacy_items": legacy_items,
        "orphans": migration["orphans"],
        "last_price_fetch": db.get_meta("last_price_fetch"),
        "next_due": _next_due(),
    }


def _next_due() -> str | None:
    last = db.get_meta("last_price_fetch")
    if not last:
        return "soon"
    try:
        ts = datetime.fromisoformat(last).timestamp()
        due = ts + WEEK_SEC
        return datetime.fromtimestamp(due, tz=timezone.utc).isoformat()
    except Exception:
        return None


def set_tracked(ids: list[str]) -> dict[str, Any]:
    by_id = catalog_by_id()
    active = active_catalog_ids()
    wanted = set(ids)
    current = {t["catalog_id"]: t for t in db.get_tracked_parts()}

    for cid in list(current.keys()):
        # Don't drop orphans waiting for decision via this endpoint
        if current[cid].get("pending_decision") and not current[cid].get("keep_legacy"):
            continue
        if cid not in wanted:
            db.remove_tracked(cid)

    for cid in wanted:
        meta = by_id.get(cid)
        if meta and cid in active:
            db.upsert_tracked(
                cid,
                keep_legacy=False,
                pending_decision=False,
                display_name=meta["name"],
                category=meta["category"],
                query=meta["query"],
            )
        elif cid in current and current[cid].get("keep_legacy"):
            db.upsert_tracked(
                cid,
                keep_legacy=True,
                pending_decision=False,
                display_name=current[cid].get("display_name"),
                category=current[cid].get("category"),
                query=current[cid].get("query"),
            )

    return get_tracker_state()


def resolve_orphans(decisions: dict[str, str]) -> dict[str, Any]:
    by_id = catalog_by_id()
    for cid, action in decisions.items():
        if action == "drop":
            db.remove_tracked(cid)
        elif action == "keep":
            meta = by_id.get(cid) or {}
            row = next((t for t in db.get_tracked_parts() if t["catalog_id"] == cid), None)
            db.upsert_tracked(
                cid,
                keep_legacy=True,
                pending_decision=False,
                display_name=(row or {}).get("display_name") or meta.get("name") or cid,
                category=(row or {}).get("category") or meta.get("category") or "legacy",
                query=(row or {}).get("query") or meta.get("query") or cid,
            )
    return get_tracker_state()


def _amazon_url(query: str) -> str:
    return f"https://www.amazon.co.jp/s?k={urllib.parse.quote(query)}"


def _extract_asin(html: str) -> str | None:
    """First organic (non-sponsored) search-result ASIN for Keepa graph embedding."""
    matches = list(re.finditer(r'data-asin="(B[0-9A-Z]{9})"', html))
    fallback: str | None = None
    for i, m in enumerate(matches):
        if fallback is None:
            fallback = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(html), m.start() + 8000)
        chunk = html[m.start():end]
        if "スポンサー" in chunk or "Sponsored" in chunk or "AdHolder" in chunk:
            continue
        return m.group(1)
    return fallback


def keepa_graph_url(asin: str) -> str:
    return (
        "https://graph.keepa.com/pricehistory.png"
        f"?asin={asin}&domain=co.jp&amazon=1&new=1&used=0&salesrank=0"
        "&range=365&width=560&height=200"
    )


def keepa_product_url(asin: str) -> str:
    # 5 = Keepa country code for amazon.co.jp
    return f"https://keepa.com/#!product/5-{asin}"


def _average_new_price(candidates: list[int]) -> tuple[int | None, int]:
    """Average of top search-result (new listing) prices, outliers removed.

    Search results mix in accessories/bundles, so keep only values within
    0.55x-1.8x of the median before averaging.
    """
    if not candidates:
        return None, 0
    top = candidates[:12]  # document order == search relevance order
    ordered = sorted(top)
    median = ordered[len(ordered) // 2]
    kept = [v for v in top if 0.55 * median <= v <= 1.8 * median]
    if not kept:
        kept = [median]
    return round(sum(kept) / len(kept)), len(kept)


def _looks_blocked(html: str) -> bool:
    return "api-services-support@amazon.com" in html or "validateCaptcha" in html


def _fetch_amazon_price(query: str) -> dict[str, Any] | None:
    """Amazon.co.jp search scrape: average of new-listing prices (no auto-purchase)."""
    url = _amazon_url(query)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.amazon.co.jp/",
    }
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
            html = ""
            for attempt in range(3):
                if attempt:
                    time.sleep(4.0 * attempt)
                resp = client.get(url)
                if resp.status_code >= 400:
                    continue
                html = resp.text
                if not _looks_blocked(html):
                    break
            else:
                return {
                    "price_yen": None,
                    "url": url,
                    "source": "amazon",
                    "note": "Amazonが一時的にアクセス制限中（次回更新で再取得）",
                }
            candidates: list[int] = []
            # Prefer structured search-result prices (avoids junk accessory hits)
            for m in re.finditer(
                r'a-price-whole[^>]*>\s*([0-9]{1,3}(?:,[0-9]{3})*)', html, flags=re.I
            ):
                try:
                    val = int(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                if 10_000 <= val <= 2_000_000:
                    candidates.append(val)
            if not candidates:
                for pat in (
                    r'a-offscreen">\s*[^0-9]{0,4}([0-9]{1,3}(?:,[0-9]{3})*)',
                    r'"priceAmount"\s*:\s*([0-9]{4,7})',
                ):
                    for m in re.finditer(pat, html, flags=re.I):
                        try:
                            val = int(m.group(1).replace(",", ""))
                        except ValueError:
                            continue
                        if 10_000 <= val <= 2_000_000:
                            candidates.append(val)
                    if candidates:
                        break
            if not candidates:
                return {
                    "price_yen": None,
                    "url": url,
                    "source": "amazon",
                    "note": "Amazon価格抽出失敗",
                    "asin": _extract_asin(html),
                }
            avg, used = _average_new_price(candidates)
            return {
                "price_yen": avg,
                "url": url,
                "source": "amazon",
                "note": f"新品出品 {used}件の平均",
                "asin": _extract_asin(html),
            }
    except Exception as exc:
        return {"price_yen": None, "url": url, "source": "amazon", "note": str(exc)}


def _kakaku_url(query: str) -> str:
    # 価格.com の検索パスは CP932（Shift_JIS）エンコードが必要
    encoded = urllib.parse.quote(query.encode("cp932", errors="replace"))
    return f"https://kakaku.com/search_results/{encoded}/"


def _fetch_kakaku_price(query: str) -> dict[str, Any] | None:
    url = _kakaku_url(query)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja,en;q=0.9",
    }
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return None
            html = resp.text
            candidates: list[int] = []
            for pat in (
                r'p-item_priceNum[^>]*>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*<',
                r'class="[^"]*p-item_priceNum[^"]*"[^>]*>\s*([0-9,]+)\s*<',
                r"createJsonKakaku\([^;]{0,500}?'([0-9]{4,7})','[0-9a-f]{16,}",
                r">([0-9]{1,3}(?:,[0-9]{3})+)</",
            ):
                for m in re.finditer(pat, html, flags=re.I):
                    try:
                        val = int(m.group(1).replace(",", ""))
                    except ValueError:
                        continue
                    if 3000 <= val <= 2_000_000:
                        candidates.append(val)
                if candidates:
                    break
            if not candidates:
                return {"price_yen": None, "url": url, "source": "kakaku", "note": "価格抽出失敗"}
            return {
                "price_yen": min(candidates),
                "url": url,
                "source": "kakaku",
                "note": None,
            }
    except Exception as exc:
        return {"price_yen": None, "url": url, "source": "kakaku", "note": str(exc)}


def refresh_prices(force: bool = False) -> dict[str, Any]:
    last = db.get_meta("last_price_fetch")
    if not force and last:
        try:
            ts = datetime.fromisoformat(last).timestamp()
            if time.time() - ts < WEEK_SEC:
                return {
                    "skipped": True,
                    "reason": "週次未到来（手動なら「今すぐ価格更新」を使用）",
                    "last_price_fetch": last,
                    "state": get_tracker_state(),
                }
        except Exception:
            pass

    by_id = catalog_by_id()
    tracked = [
        t
        for t in db.get_tracked_parts()
        if not (t.get("pending_decision") and not t.get("keep_legacy"))
    ]
    results = []
    for t in tracked:
        cid = t["catalog_id"]
        meta = by_id.get(cid)
        query = (meta or {}).get("query") or t.get("query") or t.get("display_name") or cid
        for fetcher in (_fetch_kakaku_price, _fetch_amazon_price):
            fetched = fetcher(query) or {}
            if fetched.get("asin"):
                db.set_meta(f"amazon_asin:{cid}", fetched["asin"])
            db.add_price_point(
                cid,
                price_yen=fetched.get("price_yen"),
                source=fetched.get("source") or "kakaku",
                url=fetched.get("url"),
                note=fetched.get("note"),
            )
            results.append({"catalog_id": cid, "query": query, **fetched})
            # Amazon rate-limits rapid sequential hits; keep a polite gap
            time.sleep(1.5)
        time.sleep(1.0)

    db.set_meta("last_price_fetch", _utc_now())
    return {"skipped": False, "updated": len(results), "results": results, "state": get_tracker_state()}


def maybe_weekly_price_job() -> None:
    tracked = db.get_tracked_parts()
    if not tracked:
        return
    refresh_prices(force=False)
