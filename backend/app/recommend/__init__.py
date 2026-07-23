from __future__ import annotations

import urllib.parse
from typing import Any


def _tb_label(tb: float) -> str:
    if tb >= 1:
        # Prefer integer TB for search queries when close
        if abs(tb - round(tb)) < 0.05:
            return f"{int(round(tb))}TB"
        return f"{tb:.1f}TB"
    gb = int(round(tb * 1024))
    return f"{gb}GB"


def _desired_capacity_tb(target: dict[str, Any], settings: dict[str, Any]) -> float:
    pref = float(settings.get("capacity_preference_tb") or 0)
    size_gb = float(target.get("size_gb") or 0)
    current_tb = size_gb / 1024 if size_gb else 1.0
    return max(pref, current_tb, 1.0)


def _media_query(settings: dict[str, Any], target: dict[str, Any]) -> str:
    prefer = (settings.get("prefer_media") or "ssd").lower()
    if prefer == "either":
        media = (target.get("media_type") or "").lower()
        if "ssd" in media:
            return "SSD"
        if "hdd" in media:
            return "HDD"
        return "SSD"
    return "SSD" if prefer == "ssd" else "HDD"


def build_query(target: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    cap = _desired_capacity_tb(target, settings)
    media = _media_query(settings, target)
    priority = settings.get("priority") or "speed"
    budget = int(settings.get("budget_max_yen") or 30000)
    prefer_nu = settings.get("prefer_new_used") or "either"

    keywords = [media, _tb_label(cap)]
    if priority == "quiet" and media == "HDD":
        keywords.append("静音")
    elif priority == "speed":
        if media == "SSD":
            keywords.append("NVMe")
        else:
            keywords.append("7200rpm")
    elif priority == "price":
        keywords.append("コスパ")

    query = " ".join(keywords)
    note_parts = [
        f"現行: {target.get('model')}（{target.get('size_gb')} GB / {target.get('media_type')}）",
        f"希望: {media} {_tb_label(cap)}前後",
        f"予算目安: {budget:,}円",
    ]
    if prefer_nu == "new":
        note_parts.append("新品優先")
    elif prefer_nu == "used":
        note_parts.append("中古も可")

    reasons = target.get("reasons") or []
    if reasons:
        note_parts.append("理由: " + " / ".join(reasons[:3]))

    return {
        "query": query,
        "media": media,
        "capacity_label": _tb_label(cap),
        "budget_max_yen": budget,
        "prefer_new_used": prefer_nu,
        "notes": note_parts,
        "target_model": target.get("model"),
        "target_device_id": target.get("device_id"),
        "risk_level": target.get("risk_level"),
    }


def _quote_utf8(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def _quote_kakaku(text: str) -> str:
    """価格.com のパス検索は Shift_JIS（CP932）のパーセントエンコードが必要。"""
    return urllib.parse.quote(text.encode("cp932", errors="replace"))


def _search_urls(query: str) -> list[dict[str, str]]:
    q_utf8 = _quote_utf8(query)
    q_kakaku = _quote_kakaku(query)
    return [
        {
            "source": "価格.com",
            "kind": "price_research",
            "title": f"価格.comで「{query}」を検索",
            "url": f"https://kakaku.com/search_results/{q_kakaku}/",
            "condition": "新品相場",
            "price_hint": "相場確認用（ページ内の最安〜平均を参照）",
        },
        {
            "source": "Amazon",
            "kind": "new",
            "title": f"Amazonで「{query}」を検索",
            "url": f"https://www.amazon.co.jp/s?k={q_utf8}",
            "condition": "新品中心",
            "price_hint": "新品価格帯を比較",
        },
        {
            "source": "楽天市場",
            "kind": "new",
            "title": f"楽天で「{query}」を検索",
            "url": f"https://search.rakuten.co.jp/search/mall/{q_utf8}/",
            "condition": "新品中心",
            "price_hint": "ポイント込みで比較しやすい",
        },
        {
            "source": "メルカリ",
            "kind": "used",
            "title": f"メルカリで「{query}」を検索",
            "url": f"https://jp.mercari.com/search?keyword={q_utf8}&status=on_sale",
            "condition": "中古・個人出品",
            "price_hint": "中古相場の目安（状態・保証に注意）",
        },
        {
            "source": "Yahoo!フリマ",
            "kind": "used",
            "title": f"Yahoo!フリマで「{query}」を検索",
            "url": f"https://paypayfleamarket.yahoo.co.jp/search?keyword={q_utf8}",
            "condition": "中古・個人出品",
            "price_hint": "中古候補の比較用",
        },
    ]


def _rough_price_band(media: str, capacity_label: str, budget: int) -> str:
    """Heuristic price band for UI (not live scraped)."""
    # Very rough JP market hints for common sizes
    bands = {
        ("SSD", "1TB"): (7000, 15000),
        ("SSD", "2TB"): (12000, 28000),
        ("SSD", "4TB"): (25000, 55000),
        ("HDD", "1TB"): (4000, 9000),
        ("HDD", "2TB"): (6000, 12000),
        ("HDD", "4TB"): (9000, 18000),
        ("HDD", "160GB"): (2000, 5000),
        ("SSD", "120GB"): (3000, 7000),
    }
    key = (media, capacity_label)
    if key in bands:
        lo, hi = bands[key]
    else:
        lo, hi = max(3000, budget // 3), budget
    used_lo, used_hi = int(lo * 0.55), int(hi * 0.8)
    return (
        f"新品の目安 {lo:,}〜{hi:,}円 / "
        f"中古の目安 {used_lo:,}〜{used_hi:,}円"
        f"（実売は変動。リンク先で確認）"
    )


def build_recommendations(
    evaluated: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    targets = list(evaluated.get("replacement_targets") or [])

    # Also suggest capacity upgrade if critical volume but no disk flagged
    for issue in evaluated.get("volume_issues") or []:
        if issue.get("risk_level") in ("Watch", "Critical"):
            # Find related disk with lowest free space
            related = None
            for d in evaluated.get("disks") or []:
                for v in d.get("volumes") or []:
                    if v.get("letter") == issue.get("letter"):
                        related = d
                        break
            synthetic = related or {
                "device_id": f"vol-{issue.get('letter')}",
                "model": f"容量不足ボリューム {issue.get('letter')}",
                "size_gb": issue.get("size_gb") or 1000,
                "media_type": "SSD",
                "risk_level": issue.get("risk_level"),
                "reasons": [issue.get("reason")],
                "needs_replacement": True,
            }
            # Avoid duplicates
            if not any(
                t.get("device_id") == synthetic.get("device_id")
                or t.get("model") == synthetic.get("model")
                for t in targets
            ):
                targets.append(synthetic)

    results: list[dict[str, Any]] = []
    prefer_nu = settings.get("prefer_new_used") or "either"
    seen_queries: set[str] = set()

    for target in targets:
        meta = build_query(target, settings)
        if meta["query"] in seen_queries:
            # Merge notes into existing entry if same query
            for existing in results:
                if existing["query"] == meta["query"]:
                    for note in meta["notes"]:
                        if note not in existing["notes"]:
                            existing["notes"].append(note)
                    break
            continue
        seen_queries.add(meta["query"])
        candidates = _search_urls(meta["query"])
        if prefer_nu == "new":
            candidates = [c for c in candidates if c["kind"] in ("new", "price_research")]
        elif prefer_nu == "used":
            candidates = [c for c in candidates if c["kind"] in ("used", "price_research")]

        results.append(
            {
                "for_device_id": meta["target_device_id"],
                "for_model": meta["target_model"],
                "risk_level": meta["risk_level"],
                "query": meta["query"],
                "notes": meta["notes"],
                "price_band": _rough_price_band(
                    meta["media"], meta["capacity_label"], meta["budget_max_yen"]
                ),
                "candidates": candidates,
                "disclaimer": "商品の自動購入機能はありません。リンク先で状態・保証・価格を必ず確認してください。",
            }
        )

    return results
