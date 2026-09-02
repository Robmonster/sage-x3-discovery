import json, re, html, os
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests, feedparser
from bs4 import BeautifulSoup

ROOT = os.path.dirname(__file__)
cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
data_path = os.path.join(ROOT, "candidates.json")

try:
    db = json.load(open(data_path, encoding="utf-8"))
except Exception:
    db = {"last_search": "", "search_stats": {}, "candidates": []}

known = {x.lower().strip() for x in cfg.get("known_companies", [])}
exclude = set(cfg.get("exclude_domains", []))
headers = {"User-Agent": "Mozilla/5.0 Sage-X3-Discovery-Monitor/1.1"}

stats = {
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "queries": len(cfg.get("queries", [])),
    "google_news_queries": 0,
    "google_news_results": 0,
    "duckduckgo_queries": 0,
    "duckduckgo_results": 0,
    "new_candidates": 0,
    "duplicates": 0,
    "excluded": 0,
    "known": 0,
    "non_sage_x3": 0,
    "errors": 0,
}

def domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def clean_title(title):
    title = re.sub(r"\s+", " ", html.unescape(title)).strip()
    for sep in [" | ", " - ", " — ", " – "]:
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            for p in parts:
                if re.search(r"\b(Ltd|Limited|Inc|LLC|GmbH|AG|PLC|Group|Company|Corp|Co\.|SA|SAS|ApS)\b", p, re.I):
                    return p
            return parts[0]
    return title[:120]

def likely_company(title, summary):
    text = f"{title} {summary}"
    patterns = [
        r"\b([A-Z][A-Za-z0-9&'().,\- ]{2,80}\b(?:Ltd|Limited|Inc|LLC|GmbH|AG|PLC|Group|Company|Corp|Co\.|SA|SAS|ApS))",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip(" ,.-")
    return clean_title(title)

def score(title, summary, published):
    t = (title + " " + summary).lower()
    conf = 5 if any(k in t for k in [
        "go live", "go-live", "went live", "new erp",
        "implemented sage x3", "implementation of sage x3",
        "migration to sage x3", "migrated to sage x3",
        "selected sage x3", "sage x3 implementation"
    ]) else 4 if "sage x3" in t else 3

    # Prefer evidence explicitly mentioning the recent target years.
    fresh = 5 if any(k in t for k in ["2026", "2025"]) else 3
    return fresh, conf

def add_result(company, url, title, summary, published, source):
    d = domain(url)

    if any(x.lower() in d for x in exclude):
        stats["excluded"] += 1
        return
    if not company or company.lower() in known:
        stats["known"] += 1
        return
    if "sage x3" not in (title + " " + summary).lower():
        stats["non_sage_x3"] += 1
        return
    if any(x in d for x in ["google.com", "bing.com", "duckduckgo.com"]):
        stats["excluded"] += 1
        return
    if any(c.get("evidence_url") == url for c in db["candidates"]):
        stats["duplicates"] += 1
        return

    fresh, conf = score(title, summary, published)
    priority = (
        "1 - Submit first" if fresh >= 5 and conf >= 5
        else "2 - Strong" if conf >= 4
        else "3 - Reserve"
    )

    clean_summary = re.sub(
        r"\s+",
        " ",
        BeautifulSoup(summary, "html.parser").get_text(" ")
    ).strip()

    db["candidates"].append({
        "priority": priority,
        "company": company,
        "country": "",
        "reason": clean_summary[:500],
        "evidence_date": published[:10] if published else "",
        "freshness": "★" * fresh + "☆" * (5 - fresh),
        "confidence": "★" * conf + "☆" * (5 - conf),
        "source_type": source,
        "evidence_url": url,
        "discovered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    stats["new_candidates"] += 1

# Google News RSS
for q in cfg.get("queries", []):
    stats["google_news_queries"] += 1
    feed_url = (
        "https://news.google.com/rss/search?q=" + quote(q)
        + "&hl=en-GB&gl=GB&ceid=GB:en"
    )
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries[:20]
        stats["google_news_results"] += len(entries)
        for e in entries:
            add_result(
                likely_company(e.get("title", ""), e.get("summary", "")),
                e.get("link", ""),
                e.get("title", ""),
                e.get("summary", ""),
                e.get("published", ""),
                "Google News RSS",
            )
    except Exception as ex:
        stats["errors"] += 1
        print("RSS error", q, ex)

# DuckDuckGo HTML search
for q in cfg.get("queries", []):
    stats["duckduckgo_queries"] += 1
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/?q=" + quote(q),
            headers=headers,
            timeout=20,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select(".result")[:10]
        stats["duckduckgo_results"] += len(results)

        for res in results:
            a = res.select_one(".result__a")
            sn = res.select_one(".result__snippet")
            if not a:
                continue
            url = a.get("href", "")
            title = a.get_text(" ", strip=True)
            summary = sn.get_text(" ", strip=True) if sn else ""
            add_result(
                likely_company(title, summary),
                url,
                title,
                summary,
                "",
                "DuckDuckGo HTML",
            )
    except Exception as ex:
        stats["errors"] += 1
        print("DDG error", q, ex)

db["candidates"] = sorted(
    db["candidates"],
    key=lambda x: (
        -x["freshness"].count("★"),
        -x["confidence"].count("★"),
        x.get("discovered_at", ""),
    ),
)

finished = datetime.now(timezone.utc)
stats["finished_at"] = finished.isoformat(timespec="seconds")
stats["duration_seconds"] = int(
    (finished - datetime.fromisoformat(stats["started_at"])).total_seconds()
)

# Store a full timestamp so every run creates a visible Git commit.
db["last_search"] = finished.isoformat(timespec="seconds")
db["search_stats"] = stats

with open(data_path, "w", encoding="utf-8") as f:
    json.dump(db, f, indent=2, ensure_ascii=False)

print("Search completed")
print("New candidates:", stats["new_candidates"])
print("Google News results:", stats["google_news_results"])
print("DuckDuckGo results:", stats["duckduckgo_results"])
print("Duplicates:", stats["duplicates"])
print("Excluded:", stats["excluded"])
print("Known:", stats["known"])
print("Errors:", stats["errors"])
print("Total candidates:", len(db["candidates"]))
