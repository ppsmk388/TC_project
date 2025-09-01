# -*- coding: utf-8 -*-
"""
talent_search_langgraph_v3_router.py
SearXNG + vLLM + LangGraph
- Name+paper enrichment, coauthor expansion (as before)
- NEW: LLM selects per-query search engines (google / google scholar / arxiv / …)
"""

import os, re, io, sys, json, time, html, asyncio, datetime, contextlib
from typing import List, Dict, Any, Optional

import requests, trafilatura
from bs4 import BeautifulSoup

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False

from pydantic import BaseModel, Field, ConfigDict, field_validator
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

# ============================ CONFIG ============================

SAVE_DIR = "./result_save"
os.makedirs(SAVE_DIR, exist_ok=True)

SEARXNG_BASE_URL = "http://127.0.0.1:8888"

# default when router has no opinion
SEARXNG_ENGINES  = "google"
SEARXNG_PAGES    = 3

LOCAL_OPENAI_BASE_URL = "http://localhost:8000/v1"
LOCAL_OPENAI_MODEL    = "Qwen3-8B"
LOCAL_OPENAI_API_KEY  = "sk-local"

MAX_ROUNDS       = 1
SEARCH_K         = 8
SELECT_K         = 50
FETCH_MAX_CHARS  = 30000
VERBOSE          = True
DEFAULT_TOP_N    = 10

# ==== NEW: engine router switches ====
ENABLE_LLM_ENGINE_ROUTER = True
ALLOWED_ENGINES = [
    "google", "startpage", "brave",
    "google scholar", "arxiv", "crossref",
    "github", "wikipedia", "wikidata"
]

# ---- tight context budget for ~4k ctx models ----
PRESELECT_JSON_CHAR_BUDGET = 2200
SRC_DUMP_CHAR_BUDGET       = 6000
PER_SOURCE_CHAR_MAX        = 800
SRC_MAX_FOR_SYNTH          = 6

UA = {"User-Agent": "Mozilla/5.0 (TalentSearch-LangGraph-v3-router)"}

DEFAULT_CONFERENCES = {
    "ICLR": ["ICLR"], "ICML": ["ICML"], "NeurIPS": ["NeurIPS","NIPS"],
    "ACL": ["ACL"], "EMNLP": ["EMNLP"], "NAACL": ["NAACL"],
    "KDD": ["KDD"], "WWW": ["WWW","The Web Conference","WebConf"],
    "AAAI": ["AAAI"], "IJCAI": ["IJCAI"], "CVPR": ["CVPR"],
    "ECCV": ["ECCV"], "ICCV": ["ICCV"], "SIGIR": ["SIGIR"],
}
DEFAULT_YEARS = [2025, 2024]
ACCEPT_HINTS = ["accepted papers","accept","acceptance","program","proceedings","schedule","paper list","main conference","research track"]

FIELD_ONTOLOGY = {
    "social_sim": {
        "venues": ["ICLR","NeurIPS","ICML","ACL","EMNLP","AAAI","IJCAI"],
        "synonyms": ["social simulation","multi-agent","llm agents","agent-based","agentic","behavior modeling"],
    },
    "nlp": {"venues":["ACL","EMNLP","NAACL","COLING","TACL"],"synonyms":["natural language","language modeling","llm","text generation","machine translation"]},
    "ml_general": {"venues":["ICLR","ICML","NeurIPS","AISTATS"],"synonyms":["foundation model","pretraining","self-supervised","representation learning"]},
}

# ============================ LOGGING ============================

def now_ts(): return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

class Tee:
    def __init__(self, stream, file_obj): self.stream, self.file_obj = stream, file_obj
    def write(self, data): self.stream.write(data); self.file_obj.write(data)
    def flush(self): self.stream.flush(); self.file_obj.flush()

def setup_tee_logging(save_dir: str, ts: str):
    os.makedirs(save_dir, exist_ok=True)
    p = os.path.join(save_dir, f"{ts}_run.log")
    f = open(p, "a", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, f); sys.stderr = Tee(sys.stderr, f)
    print(f"[log] tee to: {p}")
    return p

# ============================ LLM ============================

LLM_OUT_TOKENS = {
    "parse":20000,"plan":20000,"select":20000,"authors":20000,
    "qopt":20000,"synthesize":20000,"router":20000
}

def get_llm(role: str, temperature: float = 0.4):
    return ChatOpenAI(
        model=LOCAL_OPENAI_MODEL, api_key=LOCAL_OPENAI_API_KEY, base_url=LOCAL_OPENAI_BASE_URL,
        temperature=temperature, max_tokens=LLM_OUT_TOKENS.get(role, 800)
    )

# ============================ HTTP ============================

def normalize_url(u: str) -> str:
    u = (u or "").strip(); u = re.sub(r"#.*$", "", u)
    if len(u) > 1 and u.endswith("/"): u = u[:-1]
    return u

def domain_of(u: str) -> str:
    try: return re.sub(r"^www\.", "", re.split(r"/+", u)[1])
    except Exception: return ""

def fetch_text(url: str, max_chars: int = FETCH_MAX_CHARS) -> str:
    if "scholar.google.com/citations" in url:
        return "[Skip] Google Scholar citations page (JS-heavy)"
    try:
        r = requests.get(url, timeout=30, headers=UA)
        if not r.ok: return f"[FetchError] HTTP {r.status_code} for {url}"
        ct = (r.headers.get("content-type") or "").lower()
        is_pdf = ("application/pdf" in ct) or url.lower().endswith(".pdf")
        if is_pdf:
            try:
                from pdfminer.high_level import extract_text as pdf_extract
                text = pdf_extract(io.BytesIO(r.content)) or ""
            except Exception as e:
                return f"[Skip] PDF extract failed: {e!r}"
        else:
            if ("text/html" not in ct) and ("application/xhtml" not in ct): return f"[Skip] Content-Type not HTML/PDF: {ct}"
            html_doc = r.text
            text = trafilatura.extract(html_doc) or ""
            if not text:
                soup = BeautifulSoup(html_doc, "html.parser")
                heads = []
                if soup.title and soup.title.string: heads.append(soup.title.string.strip())
                for h in soup.find_all(["h1","h2"])[:2]: heads.append(h.get_text(" ", strip=True))
                text = "\n".join(heads) or "[Empty after parse]"
        text = html.unescape(text).strip()
        if len(text) > max_chars: text = text[:max_chars] + "\n...[truncated]"
        return text
    except Exception as e:
        return f"[FetchError] {e!r}"

def fetch_html(url: str, timeout: int = 30) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        if not r.ok: return ""
        ct = (r.headers.get("content-type") or "").lower()
        if "text/html" in ct or "application/xhtml" in ct: return r.text or ""
        return ""
    except Exception:
        return ""

# ============================ SEARCH ============================

def searxng_search(query: str, engines: str, pages: int = SEARXNG_PAGES, k_per_query: int = SEARCH_K) -> List[Dict[str, str]]:
    """engines: comma-separated engine names as configured in SearXNG (e.g., 'google', 'google scholar,arxiv')."""
    out, base = [], SEARXNG_BASE_URL.rstrip("/")
    for p in range(1, pages + 1):
        try:
            params = {"q": query, "format":"json", "engines":engines, "pageno":p, "page":p}
            r = requests.get(f"{base}/search", params=params, timeout=35, headers=UA); r.raise_for_status()
            rows = (r.json() or {}).get("results") or []
            for it in rows[:k_per_query]:
                u = normalize_url(it.get("url") or "")
                if not u.startswith("http"): continue
                out.append({"title":(it.get("title") or "").strip(),"url":u,"snippet":(it.get("content") or "").strip(),"engine":it.get("engine") or ""})
        except Exception as e:
            if VERBOSE: print(f"[searxng] error: {e!r} ({query}, engines={engines}, p={p})")
        time.sleep(0.06)
    return out

# ============================ SCHEMAS ============================

class QuerySpec(BaseModel):
    top_n: int = DEFAULT_TOP_N
    years: List[int] = Field(default_factory=lambda: DEFAULT_YEARS)
    venues: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    must_be_current_student: bool = True
    degree_levels: List[str] = Field(default_factory=lambda: ["PhD","MSc","Master","Graduate"])
    author_priority: List[str] = Field(default_factory=lambda: ["first","last"])
    extra_constraints: List[str] = Field(default_factory=list)
    @field_validator("years")
    @classmethod
    def keep_ints(cls, v):
        out = []; 
        for x in v:
            try: out.append(int(x))
            except: pass
        return out[:5]
    @field_validator("keywords","venues","degree_levels","author_priority","extra_constraints")
    @classmethod
    def trim_list(cls, v):
        seen, out = set(), []
        for s in v:
            s = re.sub(r"\s+"," ",(s or "").strip())
            if s and s not in seen: seen.add(s); out.append(s)
        return out[:32]

class ResearchState(BaseModel):
    query: str
    round: int = 0
    query_spec: QuerySpec = Field(default_factory=QuerySpec)
    plan: Dict[str, Any] = Field(default_factory=dict)
    serp: List[Dict[str, str]] = Field(default_factory=list)
    selected_urls: List[str] = Field(default_factory=list)
    sources: Dict[str, str] = Field(default_factory=dict)
    sources_html: Dict[str, str] = Field(default_factory=dict)
    report: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    need_more: bool = False
    followups: List[str] = Field(default_factory=list)

class PlanSpec(BaseModel):
    search_terms: List[str] = Field(...); selection_hint: str = Field(...)
    fields: List[str] = Field(default_factory=list)
    author_candidates: List[str] = Field(default_factory=list)
    author_profiles: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    frontier: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # {name: {"seed_papers":[...]}}
    visited_authors: List[str] = Field(default_factory=list)
    engine_map: Dict[str, List[str]] = Field(default_factory=dict)     # NEW: {query: [engines]}
    @field_validator("search_terms")
    @classmethod
    def non_empty(cls, v):
        if not v: raise ValueError("search_terms cannot be empty")
        return v[:160]

class SelectSpec(BaseModel):
    urls: List[str] = Field(...)
    @field_validator("urls")
    @classmethod
    def limit_len(cls, v):
        seen, out = set(), []
        for u in v:
            nu = normalize_url(u)
            if nu.startswith("http") and nu not in seen: seen.add(nu); out.append(nu)
        return out[:SELECT_K]

class CandidateCard(BaseModel):
    name: str = Field(..., alias="Name")
    current_role_affiliation: str = Field(..., alias="Current Role & Affiliation")
    research_focus: List[str] = Field(default_factory=list, alias="Research Focus")
    profiles: Dict[str, str] = Field(default_factory=dict, alias="Profiles")
    notable: Optional[str] = Field(default=None, alias="Notable")
    evidence_notes: Optional[str] = Field(default=None, alias="Evidence Notes")
    model_config = ConfigDict(populate_by_name=True)

class CandidatesSpec(BaseModel):
    candidates: List[CandidateCard] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    need_more: bool = False
    followups: List[str] = Field(default_factory=list)

class AuthorListSpec(BaseModel):
    authors: List[str] = Field(default_factory=list)
    @field_validator("authors")
    @classmethod
    def limit_authors(cls, v):
        seen, out = set(), []
        for name in v:
            name = re.sub(r"\s+"," ",(name or "").strip())
            if 2 <= len(name) <= 80 and name not in seen: seen.add(name); out.append(name)
        return out[:25]

class QOptSpec(BaseModel):
    queries: List[str] = Field(default_factory=list)

# NEW: engine routing schema
class EngineRouteSpec(BaseModel):
    routes: List[Dict[str, Any]] = Field(default_factory=list)  # [{"q":"...", "engines":["google","arxiv"]}]

# ============================ SAFE STRUCTURED ============================

def strip_thinking(t: str) -> str:
    if not isinstance(t, str): return t
    return re.sub(r"<think>.*?</think>", "", t, flags=re.S|re.I).strip()

def extract_json_block(s: str) -> Optional[dict]:
    s = strip_thinking(s)
    try: return json.loads(s)
    except Exception: pass
    st = s.find("{")
    while st != -1:
        depth = 0
        for i in range(st, len(s)):
            ch = s[i]
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(s[st:i+1])
                    except Exception: break
        st = s.find("{", st+1)
    return None

def minimal_by_schema(schema_cls):
    if schema_cls is QuerySpec: return QuerySpec()
    if schema_cls is PlanSpec: return PlanSpec(search_terms=["accepted papers program proceedings schedule"], selection_hint="prefer accepted/program/proceedings")
    if schema_cls is SelectSpec: return SelectSpec(urls=[])
    if schema_cls is CandidatesSpec: return CandidatesSpec(candidates=[], citations=[], need_more=True, followups=["Need more sources"])
    if schema_cls is AuthorListSpec: return AuthorListSpec(authors=[])
    if schema_cls is QOptSpec: return QOptSpec(queries=[])
    if schema_cls is EngineRouteSpec: return EngineRouteSpec(routes=[])
    raise ValueError("Unknown schema class")

def safe_structured(llm: ChatOpenAI, prompt: str, schema_cls):
    try:
        return llm.with_structured_output(schema_cls).invoke(prompt)
    except Exception as e:
        if VERBOSE: print("[safe_structured] response_format failed:", repr(e))
    try:
        r = llm.invoke(prompt); txt = getattr(r, "content", "") if hasattr(r, "content") else str(r)
        data = extract_json_block(txt)
        if data is not None: return schema_cls.model_validate(data)
        if VERBOSE: print("[safe_structured] no valid JSON block, use minimal")
    except Exception as e:
        if VERBOSE: print("[safe_structured] invoke fallback failed:", repr(e))
    return minimal_by_schema(schema_cls)

# ============================ HELPERS & PATTERNS ============================

STUDENT_PAT = re.compile(r"\b(ph\.?d|phd (student|candidate)|doctoral|msc|master'?s|graduate student)\b", re.I)
EDU_DOM_PAT  = re.compile(r"\.(edu|ac\.[a-z]{2,})\b", re.I)

def _looks_student(text: str) -> bool:
    return bool(STUDENT_PAT.search((text or "").lower()))

def _profile_like_url(u: str) -> bool:
    dom = domain_of(u)
    if any(x in dom for x in ["openreview.net","semanticscholar.org","linkedin.com","twitter.com","x.com","github.io","github.com"]):
        return True
    if EDU_DOM_PAT.search(u): return True
    if re.search(r"/people/|/~|profile", u, flags=re.I): return True
    return False

HOMEPAGE_NEG_PAT = re.compile(r"(arxiv\.org|openreview\.net/pdf|/pdf$|/abs/|proceedings|paper|/eprint/|/doi/|acm\.org|ieee\.org|springer|elsevier)", re.I)
HOMEPAGE_POS_URL_PAT = re.compile(r"(\.edu|\.ac\.[a-z]{2,}|github\.io|/~|/people/|/faculty/|/staff/|/users/|/homepages?/|/~[A-Za-z0-9_-]+)", re.I)
HOMEPAGE_NAV_WORDS = ("publications","research","teaching","cv","bio","service","students","projects","talks")

def score_homepage_candidate(url: str, html_doc: str, author_name: str) -> float:
    u = (url or "").lower(); s = 0.0
    if HOMEPAGE_NEG_PAT.search(u): s -= 8.0
    if HOMEPAGE_POS_URL_PAT.search(u): s += 6.0
    if u.endswith(".pdf"): s -= 10.0
    soup = None
    with contextlib.suppress(Exception):
        soup = BeautifulSoup(html_doc or "", "html.parser")
    if soup:
        title = (soup.title.string if soup.title else "") or ""
        head = (title + " " + " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1","h2"])[:3])).lower()
        if any(w in head for w in ("home","homepage","bio","about")): s += 2.0
        nav = " ".join(a.get_text(" ", strip=True) for a in soup.find_all("a")[:60]).lower()
        s += sum(0.6 for w in HOMEPAGE_NAV_WORDS if w in nav)
        if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", soup.get_text(" ", strip=True)): s += 2.0
        an = re.sub(r"\s+"," ", author_name).lower()
        if an and an.split()[0] in (title.lower() + " " + nav): s += 1.0
    return s

def choose_best_homepage(cands: List[tuple[str, str]], author_name: str) -> Optional[str]:
    if not cands: return None
    scored = [(score_homepage_candidate(u, h, author_name), u) for (u, h) in cands]
    scored.sort(reverse=True); best_score, best_url = scored[0]
    return best_url if best_score >= 1.0 else None

def extract_profile_links_from_openreview(html_doc: str) -> dict:
    out = {}
    try:
        soup = BeautifulSoup(html_doc or "", "html.parser")
        for a in soup.find_all("a"):
            href = (a.get("href") or "").strip()
            label = (a.get_text(" ", strip=True) or "").lower()
            if not href: continue
            if "scholar.google.com" in href: out["Google Scholar"] = href
            elif "github.com" in href: out["GitHub"] = href
            elif "twitter.com" in href or "x.com" in href: out["Twitter"] = href
            elif "linkedin.com/in" in href: out["LinkedIn"] = href
            elif "http" in href and ("home" in label or "homepage" in label or "personal" in label or "site" in label): out["Homepage"] = href
    except Exception: pass
    return out

def parse_ss_affiliations_and_links(html_doc: str) -> tuple[List[str], Dict[str,str]]:
    affs, links = [], {}
    try:
        for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_doc, flags=re.S|re.I):
            blob = m.group(1)
            try:
                j = json.loads(blob)
                if isinstance(j, dict):
                    A = []
                    if "affiliations" in j:
                        a = j["affiliations"]
                        if isinstance(a, list):
                            for it in a:
                                if isinstance(it, dict) and it.get("name"): A.append(it["name"])
                                elif isinstance(it, str): A.append(it)
                    if "worksFor" in j:
                        wf = j["worksFor"]
                        if isinstance(wf, dict) and wf.get("name"): A.append(wf["name"])
                        elif isinstance(wf, list):
                            for it in wf:
                                if isinstance(it, dict) and it.get("name"): A.append(it["name"])
                    affs += A
                    if "sameAs" in j and isinstance(j["sameAs"], list):
                        for u in j["sameAs"]:
                            if "scholar.google.com" in u: links["Google Scholar"] = u
                            elif "github.com" in u: links["GitHub"] = u
                            elif "twitter.com" in u or "x.com" in u: links["Twitter"] = u
                            elif "linkedin.com/in" in u: links["LinkedIn"] = u
            except Exception:
                continue
    except Exception:
        pass
    return list(dict.fromkeys(affs)), links

# ============================ QUERY BUILDING ============================

def guess_fields_from_keywords(keywords: List[str]) -> List[str]:
    kw = " ".join(keywords).lower()
    hits = [f for f, spec in FIELD_ONTOLOGY.items() if any(s in kw for s in spec["synonyms"])]
    return hits or ["ml_general"]

def enrich_field_ontology(spec: QuerySpec) -> Dict[str, Any]:
    fields = guess_fields_from_keywords(spec.keywords or [])
    ven = set(spec.venues or [])
    for f in fields: ven.update(FIELD_ONTOLOGY.get(f, {}).get("venues", []))
    out = list(ven) or list(DEFAULT_CONFERENCES.keys())
    return {"venues": sorted(out)[:12], "fields": fields}

def build_conference_queries(spec: QuerySpec, default_confs: Dict[str, List[str]], cap: int = 160) -> List[str]:
    venues = spec.venues if spec.venues else sorted(default_confs.keys())
    aliases = []
    for v in venues: aliases += default_confs.get(v, [v])
    aliases = [a for a in aliases if a]
    years = spec.years if spec.years else DEFAULT_YEARS
    keywords = spec.keywords or []

    base = []
    for alias in aliases:
        for year in years:
            if keywords:
                for kw in keywords:
                    kw = kw.strip('"')
                    base.append(f'{alias} {year} "{kw}"')
                    for h in ACCEPT_HINTS: base.append(f'{alias} {year} "{kw}" {h}')
            else:
                for h in ACCEPT_HINTS: base.append(f'{alias} {year} {h}')

    if keywords:
        combo = " OR ".join(['"{}"'.format(k.strip('"')) for k in keywords])
        base += [f'site:openreview.net {combo}', f'site:semanticscholar.org {combo}', f'site:dblp.org {combo}', f'site:arxiv.org {combo}']

    seen, out = set(), []
    for q in base:
        if q not in seen: seen.add(q); out.append(q)
        if len(out) >= cap: break
    return out

# ============================ ENGINE ROUTER ============================

def engine_heuristic(q: str) -> List[str]:
    ql = q.lower()
    if "arxiv" in ql or "site:arxiv.org" in ql: return ["arxiv", "google"]
    if "crossref" in ql or "doi" in ql: return ["crossref", "google"]
    if "semantic scholar" in ql or "semanticscholar.org" in ql: return ["google"]  # S2 engine often not present
    if "openreview" in ql: return ["google", "startpage"]
    if "site:github" in ql or "github" in ql: return ["github", "google"]
    if "wikipedia" in ql or "wikidata" in ql: return ["wikipedia", "wikidata"]
    if "scholar" in ql or "site:scholar.google.com" in ql or "h-index" in ql: return ["google scholar", "google"]
    # default web search
    return ["google"]

def llm_choose_engines(queries: List[str]) -> Dict[str, List[str]]:
    """Return {query: [engine, ...]} using LLM, with heuristic fallback."""
    if not ENABLE_LLM_ENGINE_ROUTER or not queries:
        return {q: engine_heuristic(q) for q in queries}
    llm = get_llm("router", temperature=0.2)
    allow = ", ".join(ALLOWED_ENGINES)
    sample = queries[:60]  # cap context
    prompt = (
        "You are a search-engine router for SearXNG. "
        "For each query string, choose 1-2 ENGINES from this allowed set:\n"
        f"{allow}\n\n"
        "Guidelines:\n"
        "- paper database/citation queries → google scholar\n"
        "- preprint IDs or 'arxiv' → arxiv\n"
        "- DOIs/metadata → crossref\n"
        "- code repos → github\n"
        "- encyclopedia facts → wikipedia/wikidata\n"
        "- everything else → google/startpage/brave (prefer google)\n\n"
        "Return STRICT JSON:\n"
        "{ \"routes\": [ {\"q\": \"<query>\", \"engines\": [\"google\", \"arxiv\"] }, ... ] }\n\n"
        f"QUERIES:\n{json.dumps(sample, ensure_ascii=False, indent=2)}"
    )
    spec = safe_structured(llm, prompt, EngineRouteSpec)
    routes = {it.get("q",""): [e for e in (it.get("engines") or []) if e in ALLOWED_ENGINES][:2]
              for it in (spec.routes or []) if it.get("q")}
    # fill gaps with heuristics
    for q in sample:
        if q not in routes or not routes[q]:
            routes[q] = engine_heuristic(q)
    # if we truncated, fill rest heuristically
    for q in queries[len(sample):]:
        routes[q] = engine_heuristic(q)
    return routes

# ============================ HEURISTICS ============================

def _heuristic_pick_urls(serp: List[Dict[str, str]], keywords: List[str], need: int = SELECT_K, max_per_domain: int = 2) -> List[str]:
    count_by_dom, seen_url, cand = {}, set(), []
    kws_l = [k.lower() for k in keywords] if keywords else []
    for r in serp:
        u = normalize_url(r.get("url", "") or "")
        if not u.startswith("http") or u in seen_url: continue
        dom = domain_of(u); seen_url.add(u)
        cand.append((u, dom, (r.get("title") or ""), (r.get("snippet") or "")))
    def score(item):
        _u, dom, title, snip = item
        text = (title + " " + snip).lower(); s = 0
        s += sum(2 for k in ACCEPT_HINTS if k in text)
        s += sum(1 for k in kws_l if k and k in text)
        s += min(len(title)//40, 3)
        if _profile_like_url(_u): s += 2
        if any(x in dom for x in ["openreview.net","semanticscholar.org"]): s += 2
        if re.search(r"\.edu|\.ac\.", dom): s += 1
        return s
    cand.sort(key=score, reverse=True)
    out = []
    for u, dom, _t, _s in cand:
        if count_by_dom.get(dom, 0) >= max_per_domain: continue
        out.append(u); count_by_dom[dom] = count_by_dom.get(dom, 0) + 1
        if len(out) >= need: break
    return out

# ============================ ROUTING ============================

def _route_after_synthesize(state: ResearchState) -> str:
    if (state.round + 1) >= MAX_ROUNDS:
        if VERBOSE: print(f"[route] reached MAX_ROUNDS={MAX_ROUNDS} -> end")
        return "end"
    if state.need_more:
        if VERBOSE: print(f"[route] continue -> round {state.round + 1}")
        return "loop"
    if VERBOSE: print("[route] end"); return "end"

# ============================ NODES ============================

def node_parse_query(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("parse", temperature=0.3)
    conf_list = ", ".join(sorted(DEFAULT_CONFERENCES.keys()))
    prompt = (
        "Parse the user's talent-scouting request into a JSON spec.\n"
        "Extract: top_n (int), years (int[]), venues (string[]), keywords (string[]), must_be_current_student (bool), "
        "degree_levels (string[]), author_priority (string[]), extra_constraints (string[]).\n"
        f"Known venues include: {conf_list}.\n"
        "Defaults: top_n=10, years=[2025,2024], must_be_current_student=true, degree_levels=[PhD,MSc,Master,Graduate], author_priority=[first,last].\n"
        "Return STRICT JSON only.\n\n"
        f"User Query:\n{state.query}\n"
    )
    spec = safe_structured(llm, prompt, QuerySpec)
    if VERBOSE: print(f"[parse] spec: top_n={spec.top_n}, years={spec.years}, venues={spec.venues}, keywords={spec.keywords}")
    return {"query_spec": spec.model_dump()}

def node_enrich_field(state: ResearchState) -> Dict[str, Any]:
    spec = QuerySpec.model_validate(state.query_spec)
    enrich = enrich_field_ontology(spec)
    spec.venues = enrich["venues"]
    plan = dict(state.plan or {}); plan["fields"] = enrich["fields"]
    if "visited_authors" not in plan: plan["visited_authors"] = []
    if "frontier" not in plan: plan["frontier"] = {}
    return {"query_spec": spec.model_dump(), "plan": plan}

def node_plan(state: ResearchState) -> Dict[str, Any]:
    spec = QuerySpec.model_validate(state.query_spec)
    terms = build_conference_queries(spec, DEFAULT_CONFERENCES, cap=160)
    plan = PlanSpec(
        search_terms=terms,
        selection_hint="Prefer accepted/program/proceedings/schedule pages; then author profile pages (OpenReview, SemanticScholar, homepage, LinkedIn, Twitter).",
        fields=state.plan.get("fields", []),
        frontier=state.plan.get("frontier", {}),
        visited_authors=state.plan.get("visited_authors", []),
        engine_map=state.plan.get("engine_map", {})
    )
    if VERBOSE: print(f"[plan] round={state.round} search_terms={len(plan.search_terms)}")
    return {"plan": plan.model_dump()}

# NEW: choose engines per query (LLM + heuristic)
def node_choose_engines(state: ResearchState) -> Dict[str, Any]:
    plan = dict(state.plan)
    terms = plan.get("search_terms", [])
    routes = llm_choose_engines(terms)
    plan["engine_map"] = routes
    if VERBOSE:
        preview = {k: v for k, v in list(routes.items())[:6]}
        print(f"[router] sample routes: {json.dumps(preview, ensure_ascii=False)}")
    return {"plan": plan}

def node_search(state: ResearchState) -> Dict[str, Any]:
    serp = list(state.serp)
    plan = state.plan
    terms = plan.get("search_terms", []) or [state.query]
    engine_map: Dict[str, List[str]] = plan.get("engine_map", {})
    for term in terms:
        engines_list = engine_map.get(term, []) or [SEARXNG_ENGINES]
        engines_str = ",".join(engines_list)
        rows = searxng_search(term, engines=engines_str, pages=SEARXNG_PAGES, k_per_query=SEARCH_K)
        if VERBOSE: print(f"[search] ({engines_str}) {term} -> +{len(rows)}")
        for r in rows:
            r["term"] = term; r["url"] = normalize_url(r["url"])
            if r["url"].startswith("http"): serp.append(r)
        time.sleep(0.05)
    seen, uniq = set(), []
    for r in serp:
        u = r.get("url","")
        if u and u not in seen: seen.add(u); uniq.append(r)
    if VERBOSE: print(f"[search] got {len(uniq)} unique results")
    return {"serp": uniq}

def node_select(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("select", temperature=0.3)
    items = state.serp[:40]
    lines = []
    for i, r in enumerate(items, 1):
        t = r.get("title","")[:180]; s = r.get("snippet","")[:240]; u = r.get("url","")
        lines.append(f"{i}. {t}\n   URL: {u}\n   Snippet: {s}")
    serp_block = "\n".join(lines) if lines else "EMPTY"
    prompt = (
        "You are a selector for talent scouting.\n"
        f"Selection hint: {state.plan.get('selection_hint','')}\n\n"
        f"SERP (top {len(items)}):\n{serp_block}\n\n"
        "Return STRICT JSON: { \"urls\": string[] } with up to N items; no commentary."
    )
    sel = safe_structured(llm, prompt, SelectSpec)
    urls = [normalize_url(u) for u in (sel.urls or []) if u]
    if not urls:
        spec = QuerySpec.model_validate(state.query_spec)
        urls = _heuristic_pick_urls(state.serp, keywords=spec.keywords, need=SELECT_K, max_per_domain=2)
        if VERBOSE: print(f"[select] LLM empty → heuristic picked {len(urls)}")
    selected = list(state.selected_urls)
    for u in urls:
        if u not in selected: selected.append(u)
    if VERBOSE: print(f"[select] chose {len(urls)} urls (total selected={len(selected)})")
    return {"selected_urls": selected}

def node_fetch(state: ResearchState) -> Dict[str, Any]:
    sources, sources_html = dict(state.sources), dict(state.sources_html)
    to_fetch = [u for u in state.selected_urls if u not in sources][:SELECT_K]
    for u in to_fetch:
        txt = fetch_text(u, max_chars=FETCH_MAX_CHARS)
        if len(txt) >= 50:
            sources[u] = txt; 
            if VERBOSE: print(f"[fetch] TEXT {u} -> {len(txt)} chars")
        else:
            if VERBOSE: print(f"[skip-short] {u} -> {len(txt)} chars")
        html_doc = fetch_html(u)
        if html_doc: sources_html[u] = html_doc
        time.sleep(0.08)
    return {"sources": sources, "sources_html": sources_html}

# ---------- seed_from_sources: (title, authors) -> frontier ----------
def parse_papers_and_authors(text: str) -> List[Dict[str, Any]]:
    rows = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i in range(len(lines)-1):
        title = lines[i]
        authors_line = lines[i+1]
        if 6 <= len(title) <= 220 and ("," in authors_line or " and " in authors_line):
            if re.search(r"https?://|doi\.org|arxiv|openreview|acm\.org|ieee\.org", title, re.I):
                continue
            names = re.split(r",| and ", authors_line)
            names = [re.sub(r"[^A-Za-zÀ-ÿ' \-]", "", n).strip() for n in names]
            names = [n for n in names if 2 <= len(n) <= 80]
            if 1 <= len(names) <= 12:
                rows.append({"title": title, "authors": names})
    return rows[:200]

def node_seed_from_sources(state: ResearchState) -> Dict[str, Any]:
    spec = QuerySpec.model_validate(state.query_spec)
    texts = [t[:16000] for u,t in state.sources.items() if not _profile_like_url(u) and len(t) >= 300]
    papers = []
    for t in texts: papers += parse_papers_and_authors(t)
    frontier = dict(state.plan.get("frontier", {}))
    priority = spec.author_priority or ["first","last"]
    for p in papers:
        names = p["authors"]
        chosen = []
        if "first" in priority and names: chosen.append(names[0])
        if "last" in priority and len(names) >= 2: chosen.append(names[-1])
        for nm in chosen:
            if nm not in frontier:
                frontier[nm] = {"seed_papers": [p["title"]]}
            else:
                lst = frontier[nm].setdefault("seed_papers", [])
                if p["title"] not in lst: lst.append(p["title"])
    keys = list(frontier.keys())[:40]
    frontier = {k: frontier[k] for k in keys}
    if VERBOSE: print(f"[seed] frontier authors={len(frontier)}")
    plan = dict(state.plan); plan["frontier"] = frontier
    return {"plan": plan}

# ---------- LLM query optimizer per candidate ----------
def llm_query_optimize(name: str, seed_papers: List[str], existing_links: Dict[str,str]) -> List[str]:
    llm = get_llm("qopt", temperature=0.2)
    want = []
    for k in ["Homepage","OpenReview","Semantic Scholar","Google Scholar","GitHub","Twitter","LinkedIn","Advisor","CV"]:
        if k in existing_links: continue
        want.append(k)
    paper = seed_papers[0] if seed_papers else ""
    prompt = (
        "Given a candidate and missing profile fields, propose up to 6 very precise web search queries. "
        "Prioritize .edu/.ac.* homepages and pages that mention the paper title to confirm identity.\n"
        f'Candidate: "{name}"\n'
        f'Representative paper: "{paper}"\n'
        f"Missing fields: {want}\n"
        "Return STRICT JSON: {\"queries\": [\"...\"]}"
    )
    spec = safe_structured(llm, prompt, QOptSpec)
    qs = [q for q in (spec.queries or []) if q and len(q) <= 160][:6]
    if not qs:
        base = [f'"{name}" site:.edu', f'"{name}" homepage', f'"{name}" OpenReview', f'"{name}" Semantic Scholar author']
        if paper: base += [f'"{name}" "{paper}" site:.edu', f'"{paper}" "{name}" lab']
        qs = base[:6]
    return qs

def build_profile_queries_for_candidate(name: str, seed_papers: List[str]) -> List[str]:
    qs = [f'"{name}" OpenReview', f'"{name}" Semantic Scholar author', f'"{name}" site:github.io',
          f'"{name}" site:.edu', f'"{name}" site:.ac.*', f'"{name}" homepage', f'"{name}" site:linkedin.com/in', f'"{name}" Twitter OR X']
    if seed_papers:
        t = seed_papers[0]
        qs += [f'"{name}" "{t}" site:.edu', f'"{t}" "{name}" lab', f'"{t}" "{name}" homepage']
    return qs[:10]

def node_candidate_enrich(state: ResearchState) -> Dict[str, Any]:
    plan = dict(state.plan)
    frontier: Dict[str, Dict[str, Any]] = plan.get("frontier", {})
    visited = set(plan.get("visited_authors", []))
    serp = list(state.serp)

    to_visit = [a for a in frontier.keys() if a not in visited][:12]
    for name in to_visit:
        seed_papers = frontier.get(name, {}).get("seed_papers", [])
        qs = build_profile_queries_for_candidate(name, seed_papers)
        qs += llm_query_optimize(name, seed_papers, {})

        # NEW: choose engines for these qs
        engine_map = llm_choose_engines(qs)
        for q in qs:
            engines_list = engine_map.get(q, []) or engine_heuristic(q)
            engines_str = ",".join(engines_list)
            rows = searxng_search(q, engines=engines_str, pages=1, k_per_query=6)
            for r in rows:
                r["term"]=q; r["url"]=normalize_url(r["url"])
                if r["url"].startswith("http"): serp.append(r)
        visited.add(name)
    plan["visited_authors"] = list(visited)
    return {"plan": plan, "serp": serp}

# ---------- profile normalization / ranking ----------
def node_profile_normalize_and_rank(state: ResearchState) -> Dict[str, Any]:
    frontier: Dict[str, Dict[str, Any]] = state.plan.get("frontier", {})
    html_map: Dict[str,str] = state.sources_html or {}
    author_cards = state.plan.get("author_profiles", {}).copy()

    for author in list(frontier.keys())[:40]:
        cands = [(u,h) for u,h in html_map.items() if _profile_like_url(u)]
        homepage = choose_best_homepage(cands, author)
        profile_links: Dict[str,str] = author_cards.get(author, {}).get("Profiles", {}).copy()
        aff_hint: List[str] = author_cards.get(author, {}).get("AffiliationHint", [])
        for u, h in cands:
            if "openreview.net/profile" in u: profile_links.update(extract_profile_links_from_openreview(h))
            elif "semanticscholar.org/author" in u:
                affs, links = parse_ss_affiliations_and_links(h); aff_hint += affs; profile_links.update(links)
            elif "scholar.google.com/citations" in u: profile_links["Google Scholar"] = u
            elif "twitter.com" in u or "x.com" in u: profile_links["Twitter"] = u
            elif "linkedin.com/in" in u: profile_links["LinkedIn"] = u
            elif "github.com" in u and "/issues" not in u and "/pull" not in u: profile_links["GitHub"] = u
        if homepage: profile_links["Homepage"] = homepage
        author_cards[author] = {"Profiles": profile_links, "AffiliationHint": list(dict.fromkeys(aff_hint))}
    return {"plan": {**state.plan, "author_profiles": author_cards}}

# ---------- coauthor expansion ----------
def parse_coauthors_from_openreview_html(html_doc: str) -> List[str]:
    out = []
    try:
        soup = BeautifulSoup(html_doc or "", "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if "openreview.net/profile?id=" in href:
                nm = a.get_text(" ", strip=True)
                if 2 <= len(nm) <= 80: out.append(nm)
    except Exception: pass
    return list(dict.fromkeys(out))[:30]

def parse_coauthors_from_semanticscholar_html(html_doc: str) -> List[str]:
    out = []
    try:
        for m in re.finditer(r'"name"\s*:\s*"([^"]+)"\s*,\s*"@type"\s*:\s*"Person"', html_doc, flags=re.I):
            nm = m.group(1).strip()
            if 2 <= len(nm) <= 80: out.append(nm)
    except Exception: pass
    return list(dict.fromkeys(out))[:30]

def node_coauthor_expand(state: ResearchState) -> Dict[str, Any]:
    html_map: Dict[str,str] = state.sources_html or {}
    plan = dict(state.plan); frontier = plan.get("frontier", {}); visited = set(plan.get("visited_authors", []))
    new_names = []
    for u, h in html_map.items():
        if "openreview.net/profile" in u:
            new_names += parse_coauthors_from_openreview_html(h)
        elif "semanticscholar.org/author" in u:
            new_names += parse_coauthors_from_semanticscholar_html(h)
    for nm in list(dict.fromkeys(new_names)):
        if nm not in frontier and nm not in visited:
            frontier[nm] = {"seed_papers": []}
            if len(frontier) >= 80: break
    plan["frontier"] = frontier
    if VERBOSE: print(f"[coauthors] frontier size -> {len(frontier)}")
    return {"plan": plan}

# ---------- student gate ----------
def node_student_status_gate(state: ResearchState) -> Dict[str, Any]:
    spec = QuerySpec.model_validate(state.query_spec)
    author_profiles: Dict[str, Dict[str, Any]] = state.plan.get("author_profiles", {})
    html_map: Dict[str,str] = state.sources_html or {}
    kept = []
    for author, info in author_profiles.items():
        profiles = info.get("Profiles", {})
        aff_hint = info.get("AffiliationHint", [])
        hp = profiles.get("Homepage")
        html_doc = html_map.get(hp, "") if hp else ""
        if not html_doc:
            for _k,u in profiles.items():
                if u in html_map: html_doc = html_map[u]; break
        soup = BeautifulSoup(html_doc or "", "html.parser")
        text = soup.get_text(" ", strip=True)[:6000] if html_doc else ""
        email_match = re.search(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        email_domain = email_match.group(1).lower() if email_match else ""
        explicit_student = _looks_student(text)

        homepage_is_edu = bool(hp and EDU_DOM_PAT.search(hp))
        email_is_edu    = bool(EDU_DOM_PAT.search(email_domain))
        has_openreview  = any("openreview.net/profile" in (v or "") for v in profiles.values())
        has_semantic    = any("semanticscholar.org/author" in (v or "") for v in profiles.values())
        aff_text = " ".join(aff_hint)
        aff_has_univ = re.search(r"(University|Institute|College|School|Laboratory|Lab)", aff_text, re.I) is not None

        is_student_like = explicit_student or homepage_is_edu or email_is_edu or aff_has_univ
        strong_profile_combo = (homepage_is_edu and (has_openreview or has_semantic))
        if spec.must_be_current_student and not (is_student_like or strong_profile_combo):
            continue

        focus = []
        for kw in ["LLM agents","social simulation","multi-agent","reinforcement learning","reasoning","NLP","evaluation","alignment","behavior","planning"]:
            if kw.lower() in (text.lower() + " " + aff_text.lower()):
                focus.append(kw)
        affiliation = ""
        m = re.search(r"(University|Institute|Laboratory|Lab|College|School) of [A-Z][A-Za-z& \-]+", text)
        if m: affiliation = m.group(0)
        if not affiliation and aff_hint: affiliation = aff_hint[0]

        kept.append({
            "Name": author,
            "Current Role & Affiliation": f"PhD/MSc Student, {affiliation}".strip(", "),
            "Research Focus": list(dict.fromkeys(focus))[:6],
            "Profiles": profiles,
            "Notable": None,
            "Evidence Notes": "Student-like via homepage/email/affiliation signals" if not explicit_student else "Profile text contains student keywords",
            "_confidence": 0.55 + 0.2*bool(homepage_is_edu) + 0.1*bool(has_openreview) + 0.1*bool(has_semantic),
        })

    if not kept:
        scored = []
        for author, info in author_profiles.items():
            profs = info.get("Profiles", {})
            score = 0
            if EDU_DOM_PAT.search(profs.get("Homepage","")): score += 2
            score += sum(1 for k in ["OpenReview","Google Scholar","GitHub","Twitter","LinkedIn"] if profs.get(k))
            scored.append((score, author, profs))
        scored.sort(reverse=True)
        for sc, author, profs in scored[:8]:
            kept.append({
                "Name": author, "Current Role & Affiliation": "Student (assumed), Affiliation TBD",
                "Research Focus": [], "Profiles": profs, "Notable": None,
                "Evidence Notes": "Fallback kept: strong academic-profile signals", "_confidence": 0.45 + 0.05*sc,
            })
    if VERBOSE: print(f"[gate] kept {len(kept)} candidates after student-status gate (fallback if needed)")
    return {"candidates": kept}

# ---------- choose sources for synth ----------
def _choose_sources_for_synth(sources: Dict[str, str]) -> Dict[str, str]:
    items = sorted(list(sources.items()), key=lambda kv: len(kv[1]), reverse=True)[:SRC_MAX_FOR_SYNTH]
    return dict(items)

def _truncate(s: str, n: int) -> str:
    return s[:max(0, n)] + ("...[truncated]" if len(s) > n else "")

def node_synthesize(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("synthesize", temperature=0.5)
    spec = QuerySpec.model_validate(state.query_spec)

    pre = state.candidates or []
    pre.sort(key=lambda c: c.get("_confidence", 0.0), reverse=True)
    pre = pre[: max(2*spec.top_n, spec.top_n+5)]
    pre_json = _truncate(json.dumps(pre, ensure_ascii=False, indent=2), PRESELECT_JSON_CHAR_BUDGET)

    src = _choose_sources_for_synth(state.sources)
    parts, used = [], 0
    for u, t in src.items():
        chunk = f"[Source] {u}\n{_truncate(t, PER_SOURCE_CHAR_MAX)}\n"
        if used + len(chunk) > SRC_DUMP_CHAR_BUDGET: break
        parts.append(chunk); used += len(chunk)
    research_dump = "".join(parts)

    prompt = (
        "You are an HR talent scout. You are given a shortlist of preselected candidates and supporting sources.\n"
        f"Using ONLY this information, finalize up to {spec.top_n} candidate cards. Be conservative; do NOT fabricate links.\n\n"
        f"PRESELECTED:\n{pre_json}\n\nSOURCES (limited):\n{research_dump}\n\n"
        "Return STRICT JSON:\n"
        "{\n"
        '  "candidates": [ {"Name":"...","Current Role & Affiliation":"...","Research Focus":["..."],'
        '    "Profiles":{"Homepage":"...","Google Scholar":"...","Twitter":"...","OpenReview":"...","GitHub":"...","LinkedIn":"..."},'
        '    "Notable":"...", "Evidence Notes":"..."} ],\n'
        '  "citations": ["<used source url>", ...], "need_more": false, "followups": []\n'
        "}"
    )
    syn = safe_structured(llm, prompt, CandidatesSpec)

    def _valid_profile_url(u: str) -> bool:
        if not u: return False
        ul = u.lower()
        allow = ("openreview.net/profile","/author/","linkedin.com/in/","twitter.com/","x.com/","github.io","github.com","semanticscholar.org/author/")
        return any(a in ul for a in allow)

    final = []
    for c in syn.candidates:
        cc = c.model_dump(by_alias=True)
        role = cc.get("Current Role & Affiliation") or ""
        profs = cc.get("Profiles") or {}
        if spec.must_be_current_student and not (_looks_student(role) or EDU_DOM_PAT.search(profs.get("Homepage","") or "")):
            pass
        if not any(_valid_profile_url(v) for v in profs.values() if v): continue
        final.append(cc)

    final = final[: spec.top_n]

    lines = [f"Found candidates (after gate): {len(final)} (target {spec.top_n})\n"]
    for i, c in enumerate(final, 1):
        name = c.get("Name",""); role = c.get("Current Role & Affiliation","")
        focus = ", ".join(c.get("Research Focus",[]) or [])
        profs = c.get("Profiles") or {}; links = []
        for k in ["Homepage","Google Scholar","OpenReview","Twitter","GitHub","LinkedIn"]:
            if profs.get(k): links.append(f"[{k}]({profs[k]})")
        links_str = " · ".join(links) if links else "—"
        lines.append(f"### {i}. {name}\n- {role}\n- Focus: {focus}\n- Links: {links_str}\n")
        if c.get("Notable"): lines.append(f"- Notable: {c['Notable']}")
        if c.get("Evidence Notes"): lines.append(f"- Evidence: {c['Evidence Notes']}")
        lines.append("")
    cites, seen = [], set()
    for u in (syn.citations or []):
        nu = normalize_url(u)
        if nu and nu not in seen: seen.add(nu); cites.append(nu)
    if cites:
        lines.append("\n#### Sources (partial)")
        for j, u in enumerate(cites[:25], 1): lines.append(f"{j}. {u}")
    report_text = "\n".join(lines).strip()

    need_more_flag = bool(syn.need_more) or (len(final) < spec.top_n)
    return {"report": report_text, "candidates": final, "need_more": need_more_flag, "followups": syn.followups or []}

def node_inc_round(state: ResearchState) -> Dict[str, Any]:
    return {"round": state.round + 1}

# ============================ GRAPH ============================

def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("parse_query", node_parse_query)
    g.add_node("enrich_field", node_enrich_field)
    g.add_node("plan", node_plan)
    g.add_node("choose_engines", node_choose_engines)  # NEW
    g.add_node("search", node_search)
    g.add_node("select", node_select)
    g.add_node("fetch", node_fetch)
    g.add_node("seed_from_sources", node_seed_from_sources)
    g.add_node("candidate_enrich", node_candidate_enrich)
    g.add_node("profile_norm", node_profile_normalize_and_rank)
    g.add_node("coauthor_expand", node_coauthor_expand)
    g.add_node("student_gate", node_student_status_gate)
    g.add_node("synthesize", node_synthesize)
    g.add_node("inc_round", node_inc_round)

    g.set_entry_point("parse_query")
    g.add_edge("parse_query", "enrich_field")
    g.add_edge("enrich_field", "plan")
    g.add_edge("plan", "choose_engines")   # plan → router → search
    g.add_edge("choose_engines", "search")
    g.add_edge("search", "select")
    g.add_edge("select", "fetch")
    g.add_edge("fetch", "seed_from_sources")
    g.add_edge("seed_from_sources", "candidate_enrich")
    g.add_edge("candidate_enrich", "profile_norm")
    g.add_edge("profile_norm", "coauthor_expand")
    g.add_edge("coauthor_expand", "student_gate")
    g.add_edge("student_gate", "synthesize")
    g.add_conditional_edges("synthesize", lambda s: "loop" if (s.need_more and (s.round + 1) < MAX_ROUNDS) else "end", {"loop":"inc_round","end":END})
    g.add_edge("inc_round", "plan")
    return g.compile()

def _ensure_state(x) -> ResearchState:
    return ResearchState.model_validate(x) if isinstance(x, dict) else x

# ============================ ENTRY ============================

def talent_search(question: str, ts: Optional[str] = None) -> Dict[str, Any]:
    ts = ts or now_ts(); os.makedirs(SAVE_DIR, exist_ok=True); setup_tee_logging(SAVE_DIR, ts)
    print(f"[start] {question}")
    print(f"[cfg] SearXNG={SEARXNG_BASE_URL} (router={ENABLE_LLM_ENGINE_ROUTER})")
    print(f"[cfg] LLM={LOCAL_OPENAI_MODEL} base={LOCAL_OPENAI_BASE_URL}")
    print(f"[cfg] ROUNDS={MAX_ROUNDS} SELECT_K={SELECT_K} SEARCH_K={SEARCH_K}")

    app = build_graph(); init = ResearchState(query=question)
    config = RunnableConfig(recursion_limit=100)
    final = app.invoke(init, config); st = _ensure_state(final); spec = QuerySpec.model_validate(st.query_spec)

    md_path   = os.path.join(SAVE_DIR, f"{ts}_talent_report.md")
    json_path = os.path.join(SAVE_DIR, f"{ts}_candidates.json")
    plan_path = os.path.join(SAVE_DIR, f"{ts}_plan.json")
    qs_path   = os.path.join(SAVE_DIR, f"{ts}_query_spec.json")
    used_js   = os.path.join(SAVE_DIR, f"{ts}_used_sources.json")
    serp_path = os.path.join(SAVE_DIR, f"{ts}_serp_dump.json")

    with open(md_path, "w", encoding="utf-8") as f: f.write(st.report or "")
    with open(json_path,"w",encoding="utf-8") as f: json.dump(st.candidates, f, ensure_ascii=False, indent=2)
    with open(plan_path,"w",encoding="utf-8") as f: json.dump(st.plan, f, ensure_ascii=False, indent=2)
    with open(qs_path,"w",encoding="utf-8") as f: json.dump(spec.model_dump(), f, ensure_ascii=False, indent=2)
    with open(used_js,"w",encoding="utf-8") as f: json.dump(list(st.sources.keys()), f, ensure_ascii=False, indent=2)
    with open(serp_path,"w",encoding="utf-8") as f: json.dump(st.serp, f, ensure_ascii=False, indent=2)

    print("\n========== REPORT ==========\n"); print(st.report or "")
    print("\n========== CANDIDATES (JSON, first 3) ==========\n"); print(json.dumps(st.candidates[:3], ensure_ascii=False, indent=2))
    print("\n========== META ==========\n")
    meta = {
        "rounds": st.round + 1, "selected_urls": st.selected_urls, "num_sources": len(st.sources),
        "need_more": st.need_more, "followups": st.followups,
        "saved": {"report_md": md_path, "candidates_json": json_path, "plan_json": plan_path, "query_spec_json": qs_path,
                  "used_sources_json": used_js, "serp_dump_json": serp_path, "run_log": os.path.join(SAVE_DIR, f"{ts}_run.log")}
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return {
        "rounds": st.round + 1, "plan": st.plan, "query_spec": spec.model_dump(),
        "selected_urls": st.selected_urls, "num_sources": len(st.sources), "report": st.report or "",
        "candidates": st.candidates, "need_more": st.need_more, "followups": st.followups,
        "used_sources": list(st.sources.keys()), "saved_paths": meta["saved"],
    }

# ============================ CLI ============================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Talent Search via SearXNG + vLLM + LangGraph (v3, engine router)")
    parser.add_argument("question", nargs="*", help="your talent-scouting query")
    args = parser.parse_args()

    q = " ".join(args.question) if args.question else (
        "I am a recruiter from MSRA. Identify 10 rising-star interns who are current PhD or Master's students working on social simulation with LLMs or multi-agent systems. Focus on candidates with recent publications at ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML or on OpenReview."
    )
    ts = now_ts(); out = talent_search(q, ts=ts)
    print(f"\nFiles saved (ts={ts}):")
    for k, v in out["saved_paths"].items(): print(f"- {k}: {v}")
