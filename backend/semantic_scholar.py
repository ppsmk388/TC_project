from typing import List, Dict, Any, Optional, Tuple
import re
import requests
import pandas as pd

from .config import S2_BASE, S2_HEADERS


def s2_search_papers(query: str, year_from: int = 2022, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"{S2_BASE}/paper/search"
    params = {
        "query": query,
        "limit": max(10, min(limit, 100)),
        "fields": "title,year,venue,authors,url,externalIds,isOpenAccess,publicationTypes",
        "offset": 0,
    }
    results: List[Dict[str, Any]] = []
    while len(results) < limit and params["offset"] < 200:
        r = requests.get(url, params=params, headers=S2_HEADERS, timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        papers = data.get("data", [])
        for p in papers:
            if p.get("year") and p["year"] >= year_from:
                results.append(p)
        if not papers:
            break
        params["offset"] += params["limit"]
    return results[:limit]


def s2_get_author(author_id: str) -> Optional[Dict[str, Any]]:
    url = f"{S2_BASE}/author/{author_id}"
    fields = (
        "name,aliases,affiliations,homepage,profilePicture,urls,hIndex,"
        "papers.title,papers.year,papers.venue,papers.url"
    )
    r = requests.get(url, params={"fields": fields}, headers=S2_HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def infer_student_status(affiliations: List[Dict[str, Any]], text_blob: str = "") -> Tuple[bool, str]:
    hints = ["phd", "m.s", "msc", "master", "student", "doctoral", "grad student"]
    blob = (text_blob or "").lower()
    for a in affiliations or []:
        _ = (a.get("name") or "").lower()
    is_student = any(k in blob for k in hints)
    reason = "contains student/degree keywords" if is_student else "no student keywords found"
    return is_student, reason


def targeted_search(
    topic: str,
    location_hint: str,
    role_type: str,
    desired_year: int,
    n_candidates: int = 10,
) -> pd.DataFrame:
    papers = s2_search_papers(topic, year_from=max(2020, desired_year - 6), limit=80)
    author_rows: Dict[str, Dict[str, Any]] = {}
    for p in papers:
        year = p.get("year")
        venue = p.get("venue")
        for a in p.get("authors", []) or []:
            aid = a.get("authorId")
            if not aid:
                continue
            row = author_rows.setdefault(
                aid,
                {
                    "author_id": aid,
                    "name": a.get("name"),
                    "affiliations": "",
                    "urls": [],
                    "h_index": None,
                    "top_papers": [],
                    "profile": {},
                    "student": None,
                    "student_reason": "",
                },
            )
            if len(row["top_papers"]) < 5:
                row["top_papers"].append(f"{p.get('title','')} ({year}, {venue})")

    for aid, row in list(author_rows.items()):
        prof = s2_get_author(aid)
        if not prof:
            continue
        row["profile"] = prof
        row["h_index"] = prof.get("hIndex")
        row["urls"] = list(filter(None, [prof.get("homepage")] + (prof.get("urls") or [])))
        affs = prof.get("affiliations") or []
        row["affiliations"] = "; ".join([a.get("name") for a in affs if a.get("name")])
        blob = " ".join([row.get("affiliations", "")] + (prof.get("aliases") or []))
        is_student, reason = infer_student_status(affs, text_blob=blob)
        row["student"], row["student_reason"] = is_student, reason

    df = pd.DataFrame(author_rows.values())
    if df.empty:
        return df

    if role_type.lower() == "intern":
        df = df[df["student"] == True]
    if location_hint:
        pat = re.compile(location_hint, re.I)
        df = df[df["affiliations"].str.contains(pat, na=False)]

    df["recent_count"] = df["top_papers"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    df["h_index_score"] = df["h_index"].fillna(0).astype(float).rsub(100).clip(lower=0)
    df["score"] = df["recent_count"] * 2 + df["h_index_score"] * 0.1 + df["student"].fillna(False).astype(int) * 5
    df = df.sort_values(["score", "recent_count"], ascending=[False, False]).head(n_candidates)
    return df[["name", "affiliations", "h_index", "top_papers", "urls", "author_id", "student", "student_reason"]]


