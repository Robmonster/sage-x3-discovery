import json, re, html, os, hashlib
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
import requests, feedparser
from bs4 import BeautifulSoup

ROOT=os.path.dirname(os.path.dirname(__file__))
cfg=json.load(open(os.path.join(ROOT,"config.json"),encoding="utf-8"))
data_path=os.path.join(ROOT,"candidates.json")
try:
    db=json.load(open(data_path,encoding="utf-8"))
except:
    db={"last_search":"","candidates":[]}

known={x.lower().strip() for x in cfg.get("known_companies",[])}
exclude=set(cfg.get("exclude_domains",[]))
headers={"User-Agent":"Mozilla/5.0 Sage-X3-Discovery-Monitor/1.0"}

def domain(url):
    try:return urlparse(url).netloc.lower().replace("www.","")
    except:return ""

def clean_title(title):
    title=re.sub(r"\s+"," ",html.unescape(title)).strip()
    # crude extraction of a company name from common title patterns
    for sep in [" | "," - "," — "," – "]:
        if sep in title:
            parts=[p.strip() for p in title.split(sep) if p.strip()]
            # Prefer a part containing corporate indicators
            for p in parts:
                if re.search(r"\b(Ltd|Limited|Inc|LLC|GmbH|AG|PLC|Group|Company|Corp|Co\.|SA|SAS|ApS)\b",p,re.I):
                    return p
            return parts[0]
    return title[:120]

def likely_company(title, summary):
    text=f"{title} {summary}"
    patterns=[
        r"\b([A-Z][A-Za-z0-9&'().,\- ]{2,80}\b(?:Ltd|Limited|Inc|LLC|GmbH|AG|PLC|Group|Company|Corp|Co\.|SA|SAS|ApS))",
    ]
    for pat in patterns:
        m=re.search(pat,text)
        if m:return m.group(1).strip(" ,.-")
    return clean_title(title)

def score(title,summary,published):
    t=(title+" "+summary).lower()
    conf=5 if any(k in t for k in ["go live","went live","new erp","implemented sage x3","implementation of sage x3","migrat","selected sage x3"]) else 4 if "sage x3" in t else 3
    fresh=5 if any(k in t for k in ["2026","2025"]) else 3
    return fresh,conf

def add_result(company,url,title,summary,published,source):
    d=domain(url)
    if any(x in d for x in exclude): return
    if not company or company.lower() in known: return
    if "sage x3" not in (title+" "+summary).lower(): return
    # Avoid obvious search-engine/category pages
    if any(x in d for x in ["google.com","bing.com","duckduckgo.com"]): return
    if any(c["evidence_url"]==url for c in db["candidates"]): return
    fresh,conf=score(title,summary,published)
    priority="1 - Submit first" if fresh>=5 and conf>=5 else "2 - Strong" if conf>=4 else "3 - Reserve"
    db["candidates"].append({
        "priority":priority,
        "company":company,
        "country":"",
        "reason":re.sub(r"\s+"," ",BeautifulSoup(summary,"html.parser").get_text(" ")).strip()[:500],
        "evidence_date":published[:10] if published else "",
        "freshness":"★"*fresh+"☆"*(5-fresh),
        "confidence":"★"*conf+"☆"*(5-conf),
        "source_type":source,
        "evidence_url":url,
        "discovered_at":datetime.now(timezone.utc).date().isoformat()
    })

# Google News RSS
for q in cfg["queries"]:
    feed_url="https://news.google.com/rss/search?q="+quote(q)+"&hl=en-GB&gl=GB&ceid=GB:en"
    try:
        feed=feedparser.parse(feed_url)
        for e in feed.entries[:20]:
            add_result(likely_company(e.get("title",""),e.get("summary","")),e.get("link",""),
                       e.get("title",""),e.get("summary",""),e.get("published",""),"Google News RSS")
    except Exception as ex:
        print("RSS error",q,ex)

# DuckDuckGo HTML search as a free secondary route
for q in cfg["queries"]:
    try:
        r=requests.get("https://html.duckduckgo.com/html/?q="+quote(q),headers=headers,timeout=20)
        soup=BeautifulSoup(r.text,"html.parser")
        for res in soup.select(".result")[:10]:
            a=res.select_one(".result__a")
            sn=res.select_one(".result__snippet")
            if not a: continue
            url=a.get("href","")
            title=a.get_text(" ",strip=True)
            summary=sn.get_text(" ",strip=True) if sn else ""
            add_result(likely_company(title,summary),url,title,summary,"","DuckDuckGo HTML")
    except Exception as ex:
        print("DDG error",q,ex)

db["candidates"]=sorted(db["candidates"],key=lambda x:(
    -int(x["freshness"].count("★")),-int(x["confidence"].count("★")),x.get("discovered_at","")
),reverse=False)
db["last_search"]=datetime.now(timezone.utc).date().isoformat()
with open(data_path,"w",encoding="utf-8") as f: json.dump(db,f,indent=2,ensure_ascii=False)
print("Candidates:",len(db["candidates"]))
