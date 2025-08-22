from typing import List, Dict, Any, Optional
import requests

from .config import S2_BASE, S2_HEADERS
from .semantic_scholar import s2_get_author
from .llm import llm_chat


def humanize_list(items: List[str], max_items: int = 5) -> str:
    items = items[:max_items]
    if not items:
        return "—"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def get_arxiv_recent(name_query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    import xml.etree.ElementTree as ET
    url = (
        "http://export.arxiv.org/api/query?search_query=au:" +
        requests.utils.quote(name_query) + "&start=0&max_results=" + str(max_results)
    )
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return []
    feed = ET.fromstring(r.text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in feed.findall("a:entry", ns):
        title = e.findtext("a:title", default="", namespaces=ns).strip().replace("\n", " ")
        link = ""
        for l in e.findall("a:link", ns):
            if l.attrib.get("type") == "text/html":
                link = l.attrib.get("href", "")
        updated = e.findtext("a:updated", default="", namespaces=ns)
        out.append({"title": title, "url": link, "updated": updated})
    return out


def build_achievement_report(person_name: str) -> str:
    best_author = None
    try:
        r = requests.get(
            f"{S2_BASE}/author/search",
            params={"query": person_name, "limit": 1, "fields": "name,affiliations,homepage,authorId"},
            headers=S2_HEADERS,
            timeout=30,
        )
        if r.status_code == 200 and r.json().get("data"):
            best_author = r.json()["data"][0]
    except Exception:
        pass

    lines: List[str] = []
    if best_author:
        aid = best_author.get("authorId")
        a = s2_get_author(aid) or {}
        aff = humanize_list([x.get("name", "") for x in a.get("affiliations", []) if x.get("name")])
        hix = a.get("hIndex")
        lines.append(f"Primary profile: {a.get('name')}  |  Affiliation(s): {aff}  |  h-index: {hix}")
        papers = sorted((a.get("papers") or []), key=lambda p: p.get("year", 0), reverse=True)[:8]
        for p in papers:
            lines.append(f"Paper: {p.get('title')}  ({p.get('year')}, {p.get('venue')})  {p.get('url')}")

    if len(lines) < 5:
        for p in get_arxiv_recent(person_name, max_results=5):
            lines.append(f"arXiv: {p['title']}  ({p['updated'][:10]})  {p['url']}")

    system = (
        "You are an expert academic assistant. Given raw bullets about a researcher, "
        "produce a crisp achievements report (recent 2-3 years). Include 1) overview, 2) highlights, 3) notable publications/links. "
        "Keep it factual and concise (<=250 words)."
    )
    user = "\n".join(lines) if lines else f"No signals available for {person_name}."
    summary = llm_chat(system, user)
    return summary


