# -*- coding: utf-8 -*-
"""
talent_search_langgraph_searxng_vllm.py  (SearXNG + vLLM + LangGraph, Pydantic v2)

改动要点：
- 只用一个 CLI 参数：用户 query；其他配置全部在代码中定义（可在代码顶部修改）。
- 先解析用户 query -> QuerySpec（关键词/会议/年份/TopN/角色偏好等），据此构造搜索。
- 先搜各大顶会（或用户指定会议/年份）的 accepted/program/proceedings/schedule，再抽作者（优先一作/末作），
  再对作者进行定向档案搜索（OpenReview / Semantic Scholar / 主页 / LinkedIn / Twitter），最后结构化候选卡片。
- SearXNG 默认只用 google 引擎。
- node_fetch 中抓取文本“太短跳过”阈值从 400 改为 50 字符。
- 所有产物带时间戳保存在固定目录，并把完整运行日志 tee 到 *_run.log。
"""

import os
import re
import io
import sys
import json
import time
import html
import datetime
from typing import List, Dict, Any, Optional

import requests
import trafilatura
from bs4 import BeautifulSoup

from pydantic import BaseModel, Field, ConfigDict, field_validator
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# ============================ 固定配置（按需改这里） ============================

# 输出目录（固定）
SAVE_DIR = "/home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/deep_research/example3_HR_intern_serxng/result_save"

# SearXNG（固定）
SEARXNG_BASE_URL = "http://127.0.0.1:8888"
SEARXNG_ENGINES  = "google"   # 只用 Google
SEARXNG_PAGES    = 3          # 每个查询翻页数

# 本地 vLLM（固定）
LOCAL_OPENAI_BASE_URL = "http://localhost:8000/v1"
LOCAL_OPENAI_MODEL    = "Qwen3-8B"
LOCAL_OPENAI_API_KEY  = "sk-local"

# 迭代与抓取参数（固定）
MAX_ROUNDS       = 3
SEARCH_K         = 8           # 每条查询每页取多少条
SELECT_K         = 16          # 每轮最多抓取多少 URL
FETCH_MAX_CHARS  = 30000
VERBOSE          = True
DEFAULT_TOP_N    = 10          # 若 query 没说，就用它

UA = {"User-Agent": "Mozilla/5.0 (TalentSearch-LangGraph-vLLM)"}

# 默认会议库（若用户没指定，用这些）
DEFAULT_CONFERENCES = {
    "ICLR": ["ICLR"],
    "ICML": ["ICML"],
    "NeurIPS": ["NeurIPS", "NIPS"],
    "ACL": ["ACL"],
    "EMNLP": ["EMNLP"],
    "NAACL": ["NAACL"],
    "KDD": ["KDD"],
    "WWW": ["WWW", "The Web Conference", "WebConf"],
    "AAAI": ["AAAI"],
    "IJCAI": ["IJCAI"],
    "CVPR": ["CVPR"],
    "ECCV": ["ECCV"],
    "ICCV": ["ICCV"],
    "SIGIR": ["SIGIR"],
}
DEFAULT_YEARS = [2025, 2024]

ACCEPT_HINTS = [
    "accepted papers", "accept", "acceptance", "program",
    "proceedings", "schedule", "paper list", "main conference", "research track",
]

# ============================ 工具：时间戳 & tee 日志 ============================

def now_ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

class Tee:
    def __init__(self, stream, file_obj):
        self.stream = stream
        self.file_obj = file_obj
    def write(self, data):
        self.stream.write(data)
        self.file_obj.write(data)
    def flush(self):
        self.stream.flush()
        self.file_obj.flush()

def setup_tee_logging(save_dir: str, ts: str):
    os.makedirs(save_dir, exist_ok=True)
    log_path = os.path.join(save_dir, f"{ts}_run.log")
    f = open(log_path, "a", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, f)
    sys.stderr = Tee(sys.stderr, f)
    print(f"[log] tee to: {log_path}")
    return log_path

# ============================ LLM 统一配置 ============================

LLM_OUT_TOKENS = {
    "parse":       2048,
    "plan":        2048,
    "select":      2048,
    "authors":     2048,
    "synthesize":  3072,
}

def get_llm(role: str, temperature: float = 0.4):
    max_tokens = LLM_OUT_TOKENS.get(role, 2048)
    return ChatOpenAI(
        model=LOCAL_OPENAI_MODEL,
        api_key=LOCAL_OPENAI_API_KEY,
        base_url=LOCAL_OPENAI_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )

# ============================ HTTP & 解析工具 ============================

def normalize_url(u: str) -> str:
    u = (u or "").strip()
    u = re.sub(r"#.*$", "", u)
    if len(u) > 1 and u.endswith("/"):
        u = u[:-1]
    return u

def domain_of(u: str) -> str:
    try:
        return re.sub(r"^www\.", "", re.split(r"/+", u)[1])
    except Exception:
        return ""

def fetch_text(url: str, max_chars: int = FETCH_MAX_CHARS) -> str:
    if "scholar.google.com/citations" in url:
        return "[Skip] Google Scholar citations page (JS-heavy)"
    try:
        r = requests.get(url, timeout=30, headers=UA)
        if not r.ok:
            return f"[FetchError] HTTP {r.status_code} for {url}"
        ct = (r.headers.get("content-type") or "").lower()
        is_pdf = ("application/pdf" in ct) or url.lower().endswith(".pdf")
        if is_pdf:
            try:
                from pdfminer.high_level import extract_text as pdf_extract
                text = pdf_extract(io.BytesIO(r.content)) or ""
            except Exception as e:
                return f"[Skip] PDF extract failed: {e!r}"
        else:
            if ("text/html" not in ct) and ("application/xhtml" not in ct):
                return f"[Skip] Content-Type not HTML/PDF: {ct}"
            html_doc = r.text
            text = trafilatura.extract(html_doc) or ""
            if not text:
                soup = BeautifulSoup(html_doc, "html.parser")
                heads = []
                if soup.title and soup.title.string:
                    heads.append(soup.title.string.strip())
                for h in soup.find_all(["h1", "h2"])[:2]:
                    heads.append(h.get_text(" ", strip=True))
                text = "\n".join(heads) or "[Empty after parse]"
        text = html.unescape(text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        return text
    except Exception as e:
        return f"[FetchError] {e!r}"

# ============================ SearXNG 搜索（JSON API） ============================

def searxng_search(query: str, engines: str = SEARXNG_ENGINES, pages: int = SEARXNG_PAGES, k_per_query: int = SEARCH_K) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    base = SEARXNG_BASE_URL.rstrip("/")
    for p in range(1, pages + 1):
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": engines,
                "pageno": p,
                "page": p,
            }
            r = requests.get(f"{base}/search", params=params, timeout=35, headers=UA)
            r.raise_for_status()
            data = r.json() or {}
            rows = data.get("results") or []
            for it in rows[:k_per_query]:
                u = normalize_url(it.get("url") or "")
                if not u.startswith("http"):
                    continue
                out.append({
                    "title": (it.get("title") or "").strip(),
                    "url": u,
                    "snippet": (it.get("content") or "").strip(),
                    "engine": it.get("engine") or "",
                })
        except Exception as e:
            if VERBOSE:
                print(f"[searxng] error: {e!r} for query: {query} page={p}")
        time.sleep(0.06)
    return out

# ============================ Pydantic v2 Schemas ============================

class QuerySpec(BaseModel):
    """从用户 query 解析得到的结构化意图"""
    top_n: int = DEFAULT_TOP_N
    years: List[int] = Field(default_factory=lambda: DEFAULT_YEARS)
    venues: List[str] = Field(default_factory=list)     # e.g., ["ICLR","ICML","NeurIPS",...]
    keywords: List[str] = Field(default_factory=list)   # e.g., ["social simulation","multi-agent",...]
    must_be_current_student: bool = True
    degree_levels: List[str] = Field(default_factory=lambda: ["PhD","MSc","Master","Graduate"])
    author_priority: List[str] = Field(default_factory=lambda: ["first","last"])
    extra_constraints: List[str] = Field(default_factory=list)  # 其它限制（地域/领域子方向等）
    @field_validator("years")
    @classmethod
    def keep_ints(cls, v):
        out = []
        for x in v:
            try:
                out.append(int(x))
            except:
                pass
        return out[:5]
    @field_validator("keywords", "venues", "degree_levels", "author_priority", "extra_constraints")
    @classmethod
    def trim_list(cls, v):
        # 去重保序 + 限制长度
        seen = set(); out = []
        for s in v:
            s = re.sub(r"\s+", " ", (s or "").strip())
            if s and s not in seen:
                seen.add(s); out.append(s)
        return out[:32]

class ResearchState(BaseModel):
    query: str
    round: int = 0
    query_spec: QuerySpec = Field(default_factory=QuerySpec)
    plan: Dict[str, Any] = Field(default_factory=dict)
    serp: List[Dict[str, str]] = Field(default_factory=list)
    selected_urls: List[str] = Field(default_factory=list)
    sources: Dict[str, str] = Field(default_factory=dict)   # url -> text
    report: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    need_more: bool = False
    followups: List[str] = Field(default_factory=list)
    expanded_authors: bool = False

class PlanSpec(BaseModel):
    search_terms: List[str] = Field(..., description="Initial search queries.")
    selection_hint: str = Field(..., description="Preferred sources to select.")
    @field_validator("search_terms")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("search_terms cannot be empty")
        return v[:120]

class SelectSpec(BaseModel):
    urls: List[str] = Field(..., description="Up to N URLs worth fetching (http/https).")
    @field_validator("urls")
    @classmethod
    def limit_len(cls, v):
        seen = set(); out = []
        for u in v:
            nu = normalize_url(u)
            if nu.startswith("http") and nu not in seen:
                seen.add(nu); out.append(nu)
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
        seen = set(); out = []
        for name in v:
            name = re.sub(r"\s+", " ", (name or "").strip())
            if 2 <= len(name) <= 80 and name not in seen:
                seen.add(name); out.append(name)
        return out[:25]

# ============================ LLM 结构化安全封装 ============================

def strip_thinking(text: str) -> str:
    if not isinstance(text, str):
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

def extract_json_block(s: str) -> Optional[dict]:
    s = strip_thinking(s)
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            ch = s[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i+1])
                    except Exception:
                        break
        start = s.find("{", start + 1)
    return None

def minimal_by_schema(schema_cls):
    if schema_cls is QuerySpec:
        return QuerySpec()
    if schema_cls is PlanSpec:
        return PlanSpec(search_terms=["accepted papers program proceedings schedule"], selection_hint="Prefer accepted/program/proceedings pages")
    if schema_cls is SelectSpec:
        return SelectSpec(urls=[])
    if schema_cls is CandidatesSpec:
        return CandidatesSpec(candidates=[], citations=[], need_more=True, followups=["Need more/better sources."])
    if schema_cls is AuthorListSpec:
        return AuthorListSpec(authors=[])
    raise ValueError("Unknown schema class")

def safe_structured(llm: ChatOpenAI, prompt: str, schema_cls):
    try:
        return llm.with_structured_output(schema_cls).invoke(prompt)
    except Exception as e:
        if VERBOSE:
            print("[safe_structured] response_format failed:", repr(e))
    try:
        resp = llm.invoke(prompt)
        txt = getattr(resp, "content", "") if hasattr(resp, "content") else str(resp)
        data = extract_json_block(txt)
        if data is not None:
            return schema_cls.model_validate(data)
        if VERBOSE:
            print("[safe_structured] no valid JSON block, use minimal")
    except Exception as e:
        if VERBOSE:
            print("[safe_structured] invoke fallback failed:", repr(e))
    return minimal_by_schema(schema_cls)

# ============================ 规则/过滤 ============================

def _looks_student(text: str) -> bool:
    text = (text or "").lower()
    pats = [
        r"\bph\.?d\b", r"\bphd student\b", r"\bdoctoral\b",
        r"\bmsc\b", r"\bmaster'?s\b", r"\bgraduate student\b",
    ]
    return any(re.search(p, text) for p in pats)

def _valid_profile_url(u: str) -> bool:
    if not u:
        return False
    ul = u.lower()
    allow = (
        "openreview.net/profile", "/author/", "linkedin.com/in/",
        "twitter.com/", "x.com/", "github.io", "github.com", "semanticscholar.org/author/"
    )
    return any(a in ul for a in allow)

def postfilter_candidates(cands: List[Dict[str, Any]], must_be_student: bool = True) -> List[Dict[str, Any]]:
    out = []
    for c in cands:
        role = (c.get("Current Role & Affiliation") or "")
        notes = (c.get("Evidence Notes") or "")
        profs = c.get("Profiles") or {}
        if must_be_student and not (_looks_student(role) or _looks_student(notes)):
            continue
        if not any(_valid_profile_url(v) for v in profs.values() if v):
            continue
        out.append(c)
    return out

def _profile_like_url(u: str) -> bool:
    dom = domain_of(u)
    if any(x in dom for x in ["openreview.net", "semanticscholar.org",
                              "linkedin.com", "twitter.com", "x.com",
                              "github.io", "github.com"]):
        return True
    if re.search(r"/people/|/~|profile", u, flags=re.I):
        return True
    return False

# ============================ 查询构造 ============================

def build_conference_queries(spec: QuerySpec, default_confs: Dict[str, List[str]], cap: int = 120) -> List[str]:
    venues = spec.venues if spec.venues else sorted(default_confs.keys())
    aliases = []
    for v in venues:
        # 若在默认库里，用它的别名；否则用原词
        if v in default_confs:
            aliases += default_confs[v]
        else:
            aliases.append(v)
    aliases = [a for a in aliases if a]

    keywords = spec.keywords or []  # 完全来自用户解析
    years = spec.years if spec.years else DEFAULT_YEARS

    base = []
    for alias in aliases:
        for year in years:
            if keywords:
                for kw in keywords:
                    kw = kw.strip('"')
                    # 基础词
                    base.append(f'{alias} {year} "{kw}"')
                    # 强化“接收/程序/论文集”
                    for h in ACCEPT_HINTS:
                        base.append(f'{alias} {year} "{kw}" {h}')
            else:
                # 即使没有关键词也能扫接收页
                for h in ACCEPT_HINTS:
                    base.append(f'{alias} {year} {h}')

    # 若用户没给会议/年份且关键词存在，再补一批“学术站点”广搜
    if keywords:
        # combo = " OR ".join([f'"{k.strip(\'"\')}"' for k in keywords])
        combo = " OR ".join(['"{}"'.format(k.strip('"')) for k in keywords])

        base += [
            f'site:openreview.net {combo}',
            f'site:semanticscholar.org {combo}',
            f'site:dblp.org {combo}',
            f'site:arxiv.org {combo}',
        ]

    # 去重保序 + 截断
    seen = set(); out = []
    for q in base:
        if q not in seen:
            seen.add(q); out.append(q)
        if len(out) >= cap:
            break
    return out

# ============================ 选择启发 & 路由（含关键词打分） ============================

def _heuristic_pick_urls(serp: List[Dict[str, str]], keywords: List[str], need: int = SELECT_K, max_per_domain: int = 2) -> List[str]:
    count_by_dom: Dict[str, int] = {}
    seen_url: set[str] = set()
    cand = []
    kws_l = [k.lower() for k in keywords] if keywords else []
    for r in serp:
        u = normalize_url(r.get("url", "") or "")
        if not u.startswith("http"): continue
        if u in seen_url:          continue
        dom = domain_of(u)
        seen_url.add(u)
        cand.append((u, dom, (r.get("title") or ""), (r.get("snippet") or "")))

    def score(item):
        _u, dom, title, snip = item
        text = (title + " " + snip).lower()
        s = 0
        s += sum(2 for k in ACCEPT_HINTS if k in text)
        s += sum(1 for k in kws_l if k and k in text)
        s += min(len(title) // 40, 3)
        if _profile_like_url(_u): s += 1
        return s

    cand.sort(key=score, reverse=True)
    out: List[str] = []
    for u, dom, _t, _s in cand:
        if count_by_dom.get(dom, 0) >= max_per_domain:
            continue
        out.append(u)
        count_by_dom[dom] = count_by_dom.get(dom, 0) + 1
        if len(out) >= need:
            break
    return out

def _route_after_fetch(state: ResearchState) -> str:
    if state.expanded_authors:
        return "synthesize"
    links = state.selected_urls
    prof_cnt = sum(1 for u in links if _profile_like_url(u))
    if VERBOSE:
        print(f"[route] profile-like links ≈ {prof_cnt}")
    return "expand" if prof_cnt < 5 else "synthesize"

def _route_after_synthesize(state: ResearchState) -> str:
    nxt = state.round + 1
    if state.need_more and nxt < MAX_ROUNDS:
        if VERBOSE: print(f"[route] continue -> round {nxt}")
        return "loop"
    if VERBOSE: print("[route] end")
    return "end"

# ============================ LangGraph 节点实现 ============================

def node_parse_query(state: ResearchState) -> Dict[str, Any]:
    """把用户的自然语言 query 解析为 QuerySpec"""
    llm = get_llm("parse", temperature=0.3)
    conf_list = ", ".join(sorted(DEFAULT_CONFERENCES.keys()))
    prompt = (
        "Parse the user's talent-scouting request into a JSON spec.\n"
        "Extract: top_n (int), years (int[]), venues (string[]), keywords (string[]), "
        "must_be_current_student (bool), degree_levels (string[]), author_priority (string[]), extra_constraints (string[]).\n"
        f"Known venues include (not exhaustive): {conf_list}.\n"
        "If the user didn't specify some fields, infer sensible defaults (top_n=10, years=[2025,2024], "
        "must_be_current_student=true, degree_levels ~ [PhD, MSc, Master, Graduate], author_priority=[first,last]).\n"
        "Return STRICT JSON only."
        "\n\nUser Query:\n"
        f"{state.query}\n"
    )
    spec = safe_structured(llm, prompt, QuerySpec)
    if VERBOSE:
        print(f"[parse] spec: top_n={spec.top_n}, years={spec.years}, venues={spec.venues}, keywords={spec.keywords}")
    return {"query_spec": spec.model_dump()}

def node_plan(state: ResearchState) -> Dict[str, Any]:
    """据 QuerySpec 生成搜索词列"""
    spec = QuerySpec.model_validate(state.query_spec)
    terms = build_conference_queries(spec, DEFAULT_CONFERENCES, cap=120)
    plan = PlanSpec(
        search_terms=terms,
        selection_hint="Prefer accepted/program/proceedings/schedule pages; then author profile pages (OpenReview, SemanticScholar, homepage, LinkedIn, Twitter)."
    )
    if VERBOSE:
        print(f"[plan] round={state.round} search_terms={len(plan.search_terms)}")
    return {"plan": plan.model_dump()}

def node_search(state: ResearchState) -> Dict[str, Any]:
    serp = list(state.serp)
    terms = state.plan.get("search_terms", []) or [state.query]
    for term in terms:
        rows = searxng_search(term, engines=SEARXNG_ENGINES, pages=SEARXNG_PAGES, k_per_query=SEARCH_K)
        if VERBOSE:
            print(f"[search] {term} -> +{len(rows)}")
        for r in rows:
            r["term"] = term
            r["url"] = normalize_url(r["url"])
            if not r["url"].startswith("http"):
                continue
            serp.append(r)
        time.sleep(0.05)
    # 去重
    seen = set(); uniq = []
    for r in serp:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u); uniq.append(r)
    if VERBOSE:
        print(f"[search] got {len(uniq)} unique results")
    return {"serp": uniq}

def node_select(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("select", temperature=0.3)
    items = state.serp[:40]
    lines = []
    for i, r in enumerate(items, 1):
        t = r.get("title", "")[:180]
        s = r.get("snippet", "")[:240]
        u = r.get("url", "")
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
        if VERBOSE:
            print(f"[select] LLM empty → heuristic picked {len(urls)}")

    selected = list(state.selected_urls)
    for u in urls:
        if u not in selected:
            selected.append(u)
    if VERBOSE:
        print(f"[select] chose {len(urls)} urls (total selected={len(selected)})")
    return {"selected_urls": selected}

def node_fetch(state: ResearchState) -> Dict[str, Any]:
    sources = dict(state.sources)
    to_fetch = [u for u in state.selected_urls if u not in sources][:SELECT_K]
    for u in to_fetch:
        txt = fetch_text(u, max_chars=FETCH_MAX_CHARS)
        if len(txt) < 50:  # <<< 按你的要求改：小于 50 字符才跳过
            if VERBOSE:
                print(f"[skip-short] {u} -> {len(txt)} chars (too short)")
            continue
        sources[u] = txt
        if VERBOSE:
            print(f"[fetch] {u} -> {len(txt)} chars")
        time.sleep(0.08)
    return {"sources": sources}

def node_expand_authors(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("authors", temperature=0.4)
    spec = QuerySpec.model_validate(state.query_spec)
    topic_hint = ", ".join(spec.keywords) if spec.keywords else "the target topics mentioned in the request"

    blobs = []
    limit = 140_000
    total = 0
    for u, t in state.sources.items():
        if _profile_like_url(u):  # 档案页跳过
            continue
        if len(t) < 600:
            continue
        seg = f"[Source] {u}\n{t[:14000]}\n"
        if total + len(seg) > limit:
            break
        total += len(seg); blobs.append(seg)
    if not blobs:
        return {"expanded_authors": True}

    dump = "\n\n".join(blobs)
    prompt = (
        f"From the sources below, extract up to 25 author names working on {topic_hint}. "
        f"Prioritize {', '.join(spec.author_priority) if spec.author_priority else 'first, last'} authors. "
        "Return STRICT JSON {\"authors\": [\"Name1\", ...]}.\n\n"
        f"{dump}\n==== END ===="
    )
    alist = safe_structured(llm, prompt, AuthorListSpec)
    if VERBOSE:
        print(f"[expand] extracted authors: {alist.authors}")

    # 生成作者定向搜索 queries（去重 + 限制总量）
    qset = list(dict.fromkeys(state.plan.get("search_terms", [])))
    add_queries: List[str] = []
    for name in alist.authors:
        name_q = re.sub(r"\s+", " ", name).strip()
        if not name_q:
            continue
        add_queries.extend([
            f'"{name_q}" OpenReview',
            f'"{name_q}" Semantic Scholar',
            f'"{name_q}" Twitter OR X',
            f'"{name_q}" LinkedIn',
            f'"{name_q}" homepage OR personal site OR github.io OR GitHub',
        ])
    add_queries = add_queries[:80]
    new_terms = list(dict.fromkeys(qset + add_queries))
    if VERBOSE:
        print(f"[expand] add queries: {len(add_queries)} (total terms={len(new_terms)})")

    new_plan = dict(state.plan)
    new_plan["search_terms"] = new_terms

    return {
        "plan": new_plan,
        "expanded_authors": True,
    }

def _choose_sources_for_synth(sources: Dict[str, str], cap: int = 20) -> Dict[str, str]:
    items = list(sources.items())
    items.sort(key=lambda kv: len(kv[1]), reverse=True)
    return dict(items[:cap])

def node_synthesize(state: ResearchState) -> Dict[str, Any]:
    llm = get_llm("synthesize", temperature=0.6)
    spec = QuerySpec.model_validate(state.query_spec)
    src = _choose_sources_for_synth(state.sources, cap=20)
    if not src:
        if VERBOSE:
            print("[synth] no sources yet")
        return {"need_more": True, "followups": ["Need more accepted/program/proceedings pages and author profiles."]}

    parts = []
    total = 0
    limit = 240_000
    for u, t in src.items():
        t = t[:16_000]
        blob = f"[Source] {u}\n{t}\n"
        if total + len(blob) > limit:
            break
        total += len(blob)
        parts.append(blob)
    research_dump = "\n\n".join(parts)

    # 角色过滤规则
    degree_hint = ", ".join(spec.degree_levels) if spec.degree_levels else "PhD/Master students"
    must_line = "They MUST be current students." if spec.must_be_current_student else "They CAN be current students or recent graduates."
    topic_hint = ", ".join(spec.keywords) if spec.keywords else "the target topics mentioned in the request"

    prompt = (
        "You are an HR talent scout. Using ONLY the sources below, extract up to "
        f"{spec.top_n} candidates who are {degree_hint} working on {topic_hint}. {must_line}\n"
        "For each candidate, return a JSON object with EXACT keys:\n"
        ' - "Name"\n'
        ' - "Current Role & Affiliation" (e.g., "PhD Student, UC Berkeley EECS")\n'
        ' - "Research Focus" (array of short keywords)\n'
        ' - "Profiles" (object with any of: "Homepage", "Google Scholar", "Twitter", "OpenReview", "GitHub", "LinkedIn")\n'
        ' - "Notable" (1 short line, optional)\n'
        ' - "Evidence Notes" (where you saw the info)\n\n'
        "STRICT rules:\n"
        "- Only include candidates if the student-status is stated or strongly implied when required.\n"
        "- Do NOT fabricate links; only include profile links that appear in sources.\n"
        "- Deduplicate the same person across multiple links.\n\n"
        "Return STRICT JSON:\n"
        "{\n"
        '  "candidates": [ { ... }, ... ],\n'
        '  "citations": ["<used source url>", ...],\n'
        '  "need_more": false,\n'
        '  "followups": []\n'
        "}\n\n"
        "==== SOURCES (url -> text) ====\n"
        f"{research_dump}\n==== END SOURCES ====\n"
    )
    syn = safe_structured(llm, prompt, CandidatesSpec)

    candidates_json = [cc.model_dump(by_alias=True) for cc in syn.candidates]
    candidates_json = postfilter_candidates(candidates_json, must_be_student=spec.must_be_current_student)

    lines = [f"Found candidates (deduped): {len(candidates_json)} (target {spec.top_n})\n"]
    for i, c in enumerate(candidates_json[:spec.top_n], 1):
        name = c.get("Name", "")
        role = c.get("Current Role & Affiliation", "")
        focus = ", ".join(c.get("Research Focus", []) or [])
        profs = c.get("Profiles") or {}
        links = []
        for k in ["Homepage", "Google Scholar", "OpenReview", "Twitter", "GitHub", "LinkedIn"]:
            if profs.get(k):
                links.append(f"[{k}]({profs[k]})")
        links_str = " · ".join(links)
        lines.append(f"### {i}. {name}\n- {role}\n- Focus: {focus}\n- Links: {links_str or '—'}\n")
        if c.get("Notable"):
            lines.append(f"- Notable: {c['Notable']}")
        if c.get("Evidence Notes"):
            lines.append(f"- Evidence: {c['Evidence Notes']}")
        lines.append("")
    cites = []
    seen = set()
    for u in (syn.citations or []):
        nu = normalize_url(u)
        if nu and nu not in seen:
            seen.add(nu); cites.append(nu)
    if cites:
        lines.append("\n#### Sources (partial)")
        for j, u in enumerate(cites[:25], 1):
            lines.append(f"{j}. {u}")
    report_text = "\n".join(lines).strip()
    if VERBOSE:
        print(f"[synth] candidates(after filter)={len(candidates_json)} need_more={syn.need_more}")

    return {
        "report": report_text,
        "candidates": candidates_json,
        "need_more": bool(syn.need_more),
        "followups": syn.followups or [],
    }

def node_inc_round(state: ResearchState) -> Dict[str, Any]:
    return {"round": state.round + 1}

# ============================ 构图 ============================

def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("parse_query", node_parse_query)
    g.add_node("plan", node_plan)
    g.add_node("search", node_search)
    g.add_node("select", node_select)
    g.add_node("fetch", node_fetch)
    g.add_node("expand_authors", node_expand_authors)
    g.add_node("synthesize", node_synthesize)
    g.add_node("inc_round", node_inc_round)

    g.set_entry_point("parse_query")
    g.add_edge("parse_query", "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "select")
    g.add_edge("select", "fetch")
    g.add_conditional_edges("fetch", _route_after_fetch, {"expand": "expand_authors", "synthesize": "synthesize"})
    g.add_edge("expand_authors", "search")
    g.add_conditional_edges("synthesize", _route_after_synthesize, {"loop": "inc_round", "end": END})
    g.add_edge("inc_round", "plan")
    return g.compile()

def _ensure_state(x) -> ResearchState:
    return ResearchState.model_validate(x) if isinstance(x, dict) else x

# ============================ 顶层入口 ============================

def talent_search(question: str, ts: Optional[str] = None) -> Dict[str, Any]:
    ts = ts or now_ts()
    os.makedirs(SAVE_DIR, exist_ok=True)
    log_path = setup_tee_logging(SAVE_DIR, ts)

    print(f"[start] {question}")
    print(f"[cfg] SearXNG={SEARXNG_BASE_URL} engines={SEARXNG_ENGINES} pages={SEARXNG_PAGES}")
    print(f"[cfg] LLM={LOCAL_OPENAI_MODEL} base={LOCAL_OPENAI_BASE_URL}")
    print(f"[cfg] ROUNDS={MAX_ROUNDS} SELECT_K={SELECT_K} SEARCH_K={SEARCH_K}")

    app = build_graph()
    init = ResearchState(query=question)
    final = app.invoke(init)
    st = _ensure_state(final)
    spec = QuerySpec.model_validate(st.query_spec)

    # 保存所有产物（带时间戳）
    md_path    = os.path.join(SAVE_DIR, f"{ts}_talent_report.md")
    json_path  = os.path.join(SAVE_DIR, f"{ts}_candidates.json")
    plan_path  = os.path.join(SAVE_DIR, f"{ts}_plan.json")
    qs_path    = os.path.join(SAVE_DIR, f"{ts}_query_spec.json")
    sources_js = os.path.join(SAVE_DIR, f"{ts}_used_sources.json")
    serp_path  = os.path.join(SAVE_DIR, f"{ts}_serp_dump.json")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(st.report or "")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(st.candidates, f, ensure_ascii=False, indent=2)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(st.plan, f, ensure_ascii=False, indent=2)
    with open(qs_path, "w", encoding="utf-8") as f:
        json.dump(spec.model_dump(), f, ensure_ascii=False, indent=2)
    with open(sources_js, "w", encoding="utf-8") as f:
        json.dump(list(st.sources.keys()), f, ensure_ascii=False, indent=2)
    with open(serp_path, "w", encoding="utf-8") as f:
        json.dump(st.serp, f, ensure_ascii=False, indent=2)

    print("\n========== REPORT ==========\n")
    print(st.report or "")
    print("\n========== CANDIDATES (JSON, first 3) ==========\n")
    print(json.dumps(st.candidates[:3], ensure_ascii=False, indent=2))
    print("\n========== META ==========\n")
    meta = {
        "rounds": st.round + 1,
        "selected_urls": st.selected_urls,
        "num_sources": len(st.sources),
        "need_more": st.need_more,
        "followups": st.followups,
        "saved": {
            "report_md": md_path,
            "candidates_json": json_path,
            "plan_json": plan_path,
            "query_spec_json": qs_path,
            "used_sources_json": sources_js,
            "serp_dump_json": serp_path,
            "run_log": os.path.join(SAVE_DIR, f"{ts}_run.log"),
        }
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return {
        "rounds": st.round + 1,
        "plan": st.plan,
        "query_spec": spec.model_dump(),
        "selected_urls": st.selected_urls,
        "num_sources": len(st.sources),
        "report": st.report or "",
        "candidates": st.candidates,
        "need_more": st.need_more,
        "followups": st.followups,
        "used_sources": list(st.sources.keys()),
        "saved_paths": meta["saved"],
    }

# ============================ CLI ============================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Talent Search via SearXNG (Google) + Author Expansion + vLLM (LangGraph, Pydantic v2)")
    parser.add_argument("question", nargs="*", help="your talent-scouting query")
    args = parser.parse_args()

    q = " ".join(args.question) if args.question else (
        "Find 10 current PhD/MSc candidates in social simulation / multi-agent simulation; prioritize first authors from ICLR/ICML/NeurIPS/ACL/EMNLP/NAACL/KDD/WWW 2025/2024."
    )
    ts = now_ts()
    out = talent_search(q, ts=ts)
    print(f"\nFiles saved (ts={ts}):")
    for k, v in out["saved_paths"].items():
        print(f"- {k}: {v}")
