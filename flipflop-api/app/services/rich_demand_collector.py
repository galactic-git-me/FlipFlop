"""
Collects and persists rich demand data from Google Trends, Reddit, and Steam.

Called from external_demand.ingest_external_demand_signals() after the
aggregate signal records are written, so the two systems stay independent.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models.demand_rich import (
    GoogleTrendsGeo,
    GoogleTrendsTimeSeries,
    RedditPost,
    SteamHardwareStat,
)
from app.services.external_demand import TOPIC_QUERIES, _parse_trends_json


# ── Google Trends ─────────────────────────────────────────────────────────────

async def collect_google_trends_rich(now: datetime) -> dict:
    """Fetch full time-series and worldwide geo data for every tracked query."""
    ts_rows: list[dict] = []
    geo_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for topic, queries in TOPIC_QUERIES.items():
            try:
                ts, geo = await _fetch_trends_detail(client, queries[:5], topic, now)
                ts_rows.extend(ts)
                geo_rows.extend(geo)
            except Exception:
                continue

    if ts_rows or geo_rows:
        await _persist_trends(ts_rows, geo_rows, now)

    return {"timeseries_rows": len(ts_rows), "geo_rows": len(geo_rows)}


async def _fetch_trends_detail(
    client: httpx.AsyncClient,
    queries: list[str],
    topic: str,
    now: datetime,
) -> tuple[list[dict], list[dict]]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FlipFlopBot/1.0)"}
    req = {
        "comparisonItem": [{"keyword": query, "geo": "GB", "time": "now 7-d"} for query in queries],
        "category": 0,
        "property": "",
    }

    explore_resp = await client.get(
        "https://trends.google.com/trends/api/explore",
        params={"hl": "en-GB", "tz": "0", "req": json.dumps(req, separators=(",", ":"))},
        headers=headers,
    )
    if explore_resp.status_code != 200:
        return [], []

    explore = _parse_trends_json(explore_resp.text)
    widgets = explore.get("widgets") or []

    ts_widget = next((w for w in widgets if str(w.get("id", "")).startswith("TIMESERIES")), None)
    geo_widget = next((w for w in widgets if str(w.get("id", "")).startswith("GEO_MAP")), None)

    ts_rows: list[dict] = []
    if ts_widget:
        ts_resp = await client.get(
            "https://trends.google.com/trends/api/widgetdata/multiline",
            params={
                "hl": "en-GB", "tz": "0",
                "req": json.dumps(ts_widget.get("request", {}), separators=(",", ":")),
                "token": ts_widget.get("token"),
            },
            headers=headers,
        )
        if ts_resp.status_code == 200:
            ts_data = _parse_trends_json(ts_resp.text)
            for row in (ts_data.get("default", {}).get("timelineData") or []):
                label = (row.get("formattedTime") or row.get("formattedAxisTime") or "")
                val_list = row.get("value") or []
                for index, query in enumerate(queries):
                    try:
                        val = float(val_list[index])
                    except (IndexError, TypeError, ValueError):
                        val = 0.0
                    ts_rows.append({
                        "query": query, "topic": topic, "date_label": str(label),
                        "value": val, "collected_at": now,
                    })

    geo_rows: list[dict] = []
    if geo_widget and geo_widget.get("request") and geo_widget.get("token"):
        geo_resp = await client.get(
            "https://trends.google.com/trends/api/widgetdata/comparedgeo",
            params={
                "hl": "en-GB", "tz": "0",
                "req": json.dumps(geo_widget.get("request", {}), separators=(",", ":")),
                "token": geo_widget.get("token"),
            },
            headers=headers,
        )
        if geo_resp.status_code == 200:
            geo_data = _parse_trends_json(geo_resp.text)
            for r in (geo_data.get("default", {}).get("geoMapData") or []):
                region_name = r.get("geoName")
                region_code = r.get("geoCode")
                val_list = r.get("value") or []
                for index, query in enumerate(queries):
                    try:
                        val = float(val_list[index])
                    except (IndexError, TypeError, ValueError):
                        val = 0.0
                    if region_name and val > 0:
                        geo_rows.append({
                            "query": query, "topic": topic, "region_name": str(region_name),
                            "region_code": str(region_code) if region_code else None,
                            "value": val, "collected_at": now,
                        })

    return ts_rows, geo_rows


async def _persist_trends(ts_rows: list[dict], geo_rows: list[dict], now: datetime) -> None:
    cutoff = now - timedelta(days=8)
    async with AsyncSessionLocal() as db:
        # Wipe stale rows before inserting fresh batch
        await db.execute(delete(GoogleTrendsTimeSeries).where(GoogleTrendsTimeSeries.collected_at < cutoff))
        await db.execute(delete(GoogleTrendsGeo).where(GoogleTrendsGeo.collected_at < cutoff))
        for row in ts_rows:
            db.add(GoogleTrendsTimeSeries(**row))
        for row in geo_rows:
            db.add(GoogleTrendsGeo(**row))
        await db.commit()


# ── Reddit ────────────────────────────────────────────────────────────────────

async def collect_reddit_rich(now: datetime) -> dict:
    """Fetch individual Reddit posts for every tracked query."""
    posts: list[dict] = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for topic, queries in TOPIC_QUERIES.items():
            for query in queries:
                try:
                    batch = await _fetch_reddit_posts(client, query, topic, now)
                    posts.extend(batch)
                except Exception:
                    continue

    inserted = await _persist_reddit_posts(posts, now)
    return {"posts_fetched": len(posts), "inserted": inserted}


async def _fetch_reddit_posts(
    client: httpx.AsyncClient,
    query: str,
    topic: str,
    now: datetime,
) -> list[dict]:
    resp = await client.get(
        "https://www.reddit.com/search.json",
        params={"q": query, "sort": "new", "limit": 25, "t": "month"},
        headers={"User-Agent": "FlipFlopDemandBot/1.0"},
    )
    if resp.status_code != 200:
        return await _fetch_reddit_posts_rss(client, query, topic, now)

    children = resp.json().get("data", {}).get("children", [])
    posts = []
    for child in children:
        d: dict[str, Any] = child.get("data", {})
        reddit_id = d.get("id", "")
        if not reddit_id:
            continue
        created = d.get("created_utc")
        try:
            created_dt = datetime.utcfromtimestamp(float(created)) if created else now
        except Exception:
            created_dt = now
        permalink = d.get("permalink")
        posts.append({
            "reddit_id": reddit_id,
            "query": query,
            "topic": topic,
            "title": str(d.get("title", ""))[:500],
            "subreddit": str(d.get("subreddit", "unknown")),
            "post_score": int(d.get("score", 0) or 0),
            "num_comments": int(d.get("num_comments", 0) or 0),
            "permalink": f"https://reddit.com{permalink}" if permalink else None,
            "created_utc": created_dt,
            "collected_at": now,
        })
    return posts


async def _fetch_reddit_posts_rss(
    client: httpx.AsyncClient, query: str, topic: str, now: datetime,
) -> list[dict]:
    """Fallback for environments where Reddit blocks anonymous JSON search."""
    resp = await client.get(
        "https://www.reddit.com/search.rss",
        params={"q": query, "sort": "new", "t": "month"},
        headers={"User-Agent": "Mozilla/5.0 FlipFlopDemand/1.0"},
    )
    if resp.status_code != 200:
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    posts: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        raw_id = entry.findtext("atom:id", default="", namespaces=ns)
        # Reddit RSS search may include communities (t5_) as well as posts.
        if not raw_id.startswith("t3_"):
            continue
        link_node = entry.find("atom:link", ns)
        link = link_node.get("href") if link_node is not None else None
        subreddit_match = re.search(r"/r/([^/]+)", link or "")
        updated = entry.findtext("atom:updated", default="", namespaces=ns)
        try:
            created = datetime.fromisoformat(updated.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            created = now
        posts.append({
            "reddit_id": raw_id.removeprefix("t3_"),
            "query": query,
            "topic": topic,
            "title": entry.findtext("atom:title", default="", namespaces=ns)[:500],
            "subreddit": subreddit_match.group(1) if subreddit_match else "unknown",
            "post_score": 0,
            "num_comments": 0,
            "permalink": link,
            "created_utc": created,
            "collected_at": now,
        })
    return posts


async def _persist_reddit_posts(posts: list[dict], now: datetime) -> int:
    if not posts:
        return 0
    cutoff = now - timedelta(days=32)
    inserted = 0
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RedditPost).where(RedditPost.collected_at < cutoff))
        # get existing IDs to skip duplicates
        existing_ids_result = await db.execute(
            select(RedditPost.reddit_id).where(
                RedditPost.reddit_id.in_([p["reddit_id"] for p in posts])
            )
        )
        existing_ids = {r[0] for r in existing_ids_result.all()}
        for post in posts:
            if post["reddit_id"] in existing_ids:
                continue
            db.add(RedditPost(**post))
            inserted += 1
        await db.commit()
    return inserted


# ── Steam ─────────────────────────────────────────────────────────────────────

# Category markers found in the Steam Hardware Survey HTML
_STEAM_CATEGORY_MARKERS = [
    ("GPU", ["video card description", "directx 12 gpu", "directx 11 gpu"]),
    ("CPU", ["processor information", "cpu vendor", "number of cpus"]),
    ("RAM", ["system ram", "physical memory"]),
    ("OS", ["operating system version"]),
]

# Matches lines like: "NVIDIA GeForce RTX 3060   5.23%   +0.14%"
_STAT_RE = re.compile(
    r"([\w\s\(\)\-\.\/]+?)\s{2,}(\d+\.\d+)%\s*([+\-]\d+\.\d+%)?",
    re.IGNORECASE,
)

# Steam publishes a JSON endpoint for hardware survey
_STEAM_SURVEY_JSON_URL = "https://store.steampowered.com/hwsurvey/Steam-Hardware-Software-Survey-Welcome-to-Steam"


async def collect_steam_rich(now: datetime) -> dict:
    """Parse Steam Hardware Survey for real GPU/CPU/RAM percentages."""
    stats: list[dict] = []

    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        try:
            resp = await client.get(
                _STEAM_SURVEY_JSON_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; FlipFlopBot/1.0)"},
            )
            if resp.status_code == 200:
                stats = _parse_steam_survey(resp.text, now)
        except Exception:
            pass

    inserted = await _persist_steam_stats(stats, now)
    return {"stats_parsed": len(stats), "inserted": inserted}


def _parse_steam_survey(html: str, now: datetime) -> list[dict]:
    """
    Extract hardware stat rows from the Steam Hardware Survey page.
    The page embeds data in JSON-like JS variable assignments.
    Falls back to scanning for percentage patterns in page text.
    """
    rows: list[dict] = []

    # Current Steam markup (2026): each top-level `stats_row row_0` names a
    # category and its leading item; the following `stats_row_details` holds
    # the remaining item/percentage/change columns.
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.select("div.stats_row.row_0"):
            section_name = heading.select_one(".stats_col_left")
            category = _map_steam_category(section_name.get_text(" ", strip=True) if section_name else "")
            if not category:
                continue
            item_nodes = list(heading.select(".stats_col_mid"))
            pct_nodes = list(heading.select(".stats_col_right"))
            change_nodes = list(heading.select(".stats_col_right2"))
            details = heading.find_next_sibling("div", class_="stats_row_details")
            if details:
                item_nodes.extend(details.select(".stats_col_mid.data_row"))
                pct_nodes.extend(details.select(".stats_col_right.data_row"))
                change_nodes.extend(details.select(".stats_col_right2.data_row"))
            for index, (item_node, pct_node) in enumerate(zip(item_nodes, pct_nodes)):
                name = item_node.get_text(" ", strip=True)
                pct_text = pct_node.get_text(" ", strip=True).replace("%", "")
                try:
                    percentage = float(pct_text)
                except ValueError:
                    continue
                change = None
                if index < len(change_nodes):
                    change_text = change_nodes[index].get_text(" ", strip=True).replace("%", "").replace("+", "")
                    try:
                        change = float(change_text)
                    except ValueError:
                        pass
                if name and percentage > 0:
                    rows.append({
                        "category": category, "item_name": name[:255],
                        "percentage": round(percentage, 4),
                        "change_pct": round(change, 4) if change is not None else None,
                        "collected_at": now,
                    })
        if rows:
            return rows
    except Exception:
        rows = []

    # Try JSON embedded as JavaScript variable: UserHWSurveyData = {...}
    json_match = re.search(r"UserHWSurveyData\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if json_match:
        try:
            survey_data = json.loads(json_match.group(1))
            for section in survey_data:
                category = _map_steam_category(section.get("sSection", ""))
                if not category:
                    continue
                for entry in section.get("entries", []):
                    name = entry.get("sDescription", "").strip()
                    pct_str = entry.get("percents", "0")
                    change_str = entry.get("change", None)
                    try:
                        pct = float(str(pct_str).replace("%", ""))
                    except Exception:
                        continue
                    change = None
                    if change_str:
                        try:
                            change = float(str(change_str).replace("%", "").replace("+", ""))
                        except Exception:
                            pass
                    if name and pct > 0:
                        rows.append({
                            "category": category,
                            "item_name": name[:255],
                            "percentage": round(pct, 4),
                            "change_pct": round(change, 4) if change is not None else None,
                            "collected_at": now,
                        })
            if rows:
                return rows
        except Exception:
            pass

    # Fallback: regex scan for percentage patterns in page source
    # Look for section headers then collect rows until next header
    current_category = "GPU"
    lower = html.lower()
    for line in html.splitlines():
        line_lower = line.lower()
        for cat, markers in _STEAM_CATEGORY_MARKERS:
            if any(m in line_lower for m in markers):
                current_category = cat
                break

        m = _STAT_RE.search(line)
        if m:
            name = m.group(1).strip()
            try:
                pct = float(m.group(2))
            except Exception:
                continue
            change = None
            if m.group(3):
                try:
                    change = float(m.group(3).replace("%", "").replace("+", ""))
                except Exception:
                    pass
            if name and 0 < pct <= 100 and len(name) > 3:
                rows.append({
                    "category": current_category,
                    "item_name": name[:255],
                    "percentage": round(pct, 4),
                    "change_pct": round(change, 4) if change is not None else None,
                    "collected_at": now,
                })

    return rows


def _map_steam_category(section_name: str) -> str | None:
    s = section_name.lower()
    if "video" in s or "directx" in s or "gpu" in s:
        return "GPU"
    if "processor" in s or "cpu" in s:
        return "CPU"
    if "ram" in s or "memory" in s:
        return "RAM"
    if "os" in s or "operating" in s:
        return "OS"
    return None


async def _persist_steam_stats(stats: list[dict], now: datetime) -> int:
    if not stats:
        return 0
    cutoff = now - timedelta(days=60)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(SteamHardwareStat).where(SteamHardwareStat.collected_at < cutoff))
        for row in stats:
            db.add(SteamHardwareStat(**row))
        await db.commit()
    return len(stats)


# ── Query helpers (read path) ─────────────────────────────────────────────────

async def get_rich_signals() -> dict:
    """Return all rich signal data for the frontend demand explorer."""
    async with AsyncSessionLocal() as db:
        # Google Trends — latest collection only
        ts_result = await db.execute(
            select(GoogleTrendsTimeSeries).order_by(
                GoogleTrendsTimeSeries.query,
                GoogleTrendsTimeSeries.collected_at.desc(),
                GoogleTrendsTimeSeries.date_label,
            )
        )
        ts_rows = ts_result.scalars().all()

        geo_result = await db.execute(
            select(GoogleTrendsGeo).order_by(
                GoogleTrendsGeo.query,
                GoogleTrendsGeo.collected_at.desc(),
                GoogleTrendsGeo.value.desc(),
            )
        )
        geo_rows = geo_result.scalars().all()

        # Reddit posts — last 30 days, sorted by score desc
        reddit_result = await db.execute(
            select(RedditPost).order_by(RedditPost.post_score.desc()).limit(500)
        )
        reddit_rows = reddit_result.scalars().all()

        # Steam — most recent batch only
        steam_result = await db.execute(
            select(SteamHardwareStat).order_by(
                SteamHardwareStat.category,
                SteamHardwareStat.percentage.desc(),
            )
        )
        steam_rows = steam_result.scalars().all()

    # Build Google Trends response — keep latest collection per query
    ts_by_query: dict[str, list[dict]] = {}
    latest_ts_collection: dict[str, datetime] = {}
    for r in ts_rows:
        latest_ts_collection.setdefault(r.query, r.collected_at)
        if r.collected_at != latest_ts_collection[r.query]:
            continue
        ts_by_query.setdefault(r.query, [])
        ts_by_query[r.query].append({
            "date": r.date_label,
            "value": r.value,
        })

    geo_by_query: dict[str, list[dict]] = {}
    latest_geo_collection: dict[str, datetime] = {}
    for r in geo_rows:
        latest_geo_collection.setdefault(r.query, r.collected_at)
        if r.collected_at != latest_geo_collection[r.query]:
            continue
        geo_by_query.setdefault(r.query, [])
        if len(geo_by_query[r.query]) < 20:
            geo_by_query[r.query].append({
                "region": r.region_name,
                "code": r.region_code,
                "value": r.value,
            })

    return {
        "google_trends": {
            "queries": list(ts_by_query.keys()),
            "timeseries": ts_by_query,
            "geo": geo_by_query,
        },
        "reddit": {
            "posts": [
                {
                    "reddit_id": r.reddit_id,
                    "query": r.query,
                    "topic": r.topic,
                    "title": r.title,
                    "subreddit": r.subreddit,
                    "score": r.post_score,
                    "comments": r.num_comments,
                    "url": r.permalink,
                    "created_utc": r.created_utc.isoformat() if r.created_utc else None,
                }
                for r in reddit_rows
            ]
        },
        "steam": {
            "stats": [
                {
                    "category": r.category,
                    "name": r.item_name,
                    "percentage": r.percentage,
                    "change": r.change_pct,
                    "collected_at": r.collected_at.isoformat() if r.collected_at else None,
                }
                for r in steam_rows
            ]
        },
    }
