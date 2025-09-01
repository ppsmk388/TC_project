"""
Search functionality for Talent Search System
Handles SearXNG searches, URL fetching, and content extraction
"""
import re, json, io, logging
import io
from typing import Optional, Tuple, List, Dict, Any, Union
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup
from trafilatura import extract

import config
from utils import normalize_url, domain_of, safe_sleep, clean_text, looks_like_profile_url

try:
    # 可选：若未安装 readability-lxml，会自动回退
    from readability import Document  # type: ignore
    HAS_READABILITY = True
except Exception:
    HAS_READABILITY = False

# ============================ SEARXNG SEARCH FUNCTIONS ============================

def searxng_search(query: str, engines: str = config.SEARXNG_ENGINES,
                   pages: int = config.SEARXNG_PAGES, k_per_query: int = config.SEARCH_K) -> List[Dict[str, str]]:
    """Search using SearXNG API"""
    out: List[Dict[str, str]] = []
    base = config.SEARXNG_BASE_URL.rstrip("/")
    url_set = set()
    for p in range(1, pages + 1):
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": engines,
                "pageno": p,
                "page": p,
            }
            
            if "google" in engines:
                params["gl"] = ""
            r = requests.get(f"{base}/search", params=params, timeout=35, headers=config.UA)
            r.raise_for_status()
            data = r.json() or {}
            rows = data.get("results") or []

            for it in rows[:k_per_query]:
                u = it.get("url") or ""
                if not u.startswith("http"):
                    continue
                if u in url_set:
                    continue
                url_set.add(u)
                
                # if arxiv search authors will contain a list of authors
                out.append({
                    "title": (it.get("title") or "").strip(),
                    "url": u,
                    "snippet": (it.get("content") or "").strip(),
                    "engine": it.get("engine") or "",
                    "authors": it.get("authors") or [],
                })
        except Exception as e:
            if config.VERBOSE:
                print(f"[searxng] error: {e!r} for query: {query} page={p}")
        safe_sleep(0.06)

    return out

# ============================ CONTENT FETCHING FUNCTIONS ============================


# ---- 通用：将 engines 既支持 str 也支持 list/tuple（修复你代码里传 ["bing"] 的用法）----
def _normalize_engines(engines: Union[str, List[str], Tuple[str, ...]]) -> str:
    if isinstance(engines, (list, tuple)):
        return ",".join(engines)
    return engines

# ---- URL 规范化：去除追踪参数，保留结构一致性 ----
_TRACKING_KEYS = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
                  "gclid","fbclid","mc_cid","mc_eid","oly_anon_id","oly_enc_id"}

def canonicalize_url(u: str) -> str:
    try:
        p = urlparse(u)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING_KEYS]
        p2 = p._replace(query=urlencode(q, doseq=True))
        # 某些纯 fragment 的“打印页”不稳定，去掉 fragment 更稳
        p2 = p2._replace(fragment="")
        return urlunparse(p2)
    except Exception:
        return u

# ---- HTTP 获取：带重试、合理头、编码处理 ----
def _http_get(url: str, timeout: int = 15) -> requests.Response:
    sess = requests.Session()
    # 比默认更像浏览器，提升可达性
    headers = dict(config.UA or {})
    headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    headers.setdefault("Cache-Control", "no-cache")
    r = sess.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    # 让 requests 自动以 apparent_encoding 回填（对 text/html 有帮助）
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or r.encoding
    return r

# ---- JSON-LD 标题提取（优先级最高，常见于新闻/学术/博客）----
def _title_from_jsonld(soup: BeautifulSoup) -> Optional[str]:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = tag.string or tag.get_text() or ""
            if not data.strip():
                continue
            obj = json.loads(data)
            items = obj if isinstance(obj, list) else [obj]
            for it in items:
                if not isinstance(it, dict):
                    continue
                # 常见类型
                typ = it.get("@type")
                if isinstance(typ, list):
                    types = [t.lower() for t in typ if isinstance(t, str)]
                else:
                    types = [typ.lower()] if isinstance(typ, str) else []
                if any(t in ("article","newsarticle","blogposting","webpage","scholarlyarticle","report") for t in types):
                    t1 = it.get("headline") or it.get("name") or it.get("alternativeHeadline")
                    if isinstance(t1, str) and t1.strip():
                        return t1.strip()
                # 某些站点把主体包到 mainEntity
                main = it.get("mainEntity")
                if isinstance(main, dict):
                    t2 = main.get("headline") or main.get("name")
                    if isinstance(t2, str) and t2.strip():
                        return t2.strip()
        except Exception:
            continue
    return None

# ---- Meta 标题：OpenGraph / Twitter ----
def _title_from_meta(soup: BeautifulSoup) -> Optional[str]:
    # og:title
    og = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    # twitter:title
    tw = soup.find("meta", attrs={"name": "twitter:title"})
    if tw and tw.get("content"):
        return tw["content"].strip()
    # dc.title
    dc = soup.find("meta", attrs={"name": "dc.title"})
    if dc and dc.get("content"):
        return dc["content"].strip()
    return None

# ---- 可见 <h1> 回退（过滤导航/登录等噪声）----
_NAV_WORDS = {"menu","navigation","nav","search","login","sign","home","about","contact","subscribe","cookie"}

def _title_from_headings(soup: BeautifulSoup) -> Optional[str]:
    # 优先找“像文章标题”的 h1
    for h in soup.find_all("h1"):
        txt = h.get_text(" ", strip=True)
        if 10 <= len(txt) <= 200 and not any(w in txt.lower() for w in _NAV_WORDS):
            return txt
    # 再尝试 h2（有些站标题在 h2）
    for h in soup.find_all("h2")[:3]:
        txt = h.get_text(" ", strip=True)
        if 10 <= len(txt) <= 200:
            return txt
    return None

# ---- <title> 标签兜底 ----
def _title_from_title_tag(soup: BeautifulSoup) -> Optional[str]:
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        # 去掉网站名常用分隔
        t = re.split(r"\s+[|-]\s+|\s+·\s+|\s+–\s+", t)[0].strip() or t
        return t
    return None

def extract_title_unified(html_doc: str) -> str:
    soup = BeautifulSoup(html_doc, "html.parser")
    for fn in (_title_from_jsonld, _title_from_meta, _title_from_headings, _title_from_title_tag):
        t = fn(soup)
        if t:
            return t
    return ""

# ---- 正文抽取：trafilatura → readability → 轻量回退 ----
def extract_main_text(html_doc: str, base_url: Optional[str] = None) -> str:
    from trafilatura import extract as t_extract
    try:
        # favor_recall=True 能从结构复杂页多拿点正文；不需要注释/表格
        text = t_extract(html_doc, include_comments=False, favor_recall=True, url=base_url) or ""
        if text.strip():
            return text
    except Exception:
        pass

    if HAS_READABILITY:
        try:
            doc = Document(html_doc)
            summary_html = doc.summary(html_partial=True)
            text = BeautifulSoup(summary_html, "html.parser").get_text("\n", strip=True)
            if text.strip():
                return text
        except Exception:
            pass

    # 轻量回退：取标题+前几段落
    soup = BeautifulSoup(html_doc, "html.parser")
    parts: List[str] = []
    if soup.title and soup.title.string:
        parts.append(soup.title.string.strip())
    # 取首屏可见段落
    for p in soup.find_all("p")[:8]:
        s = p.get_text(" ", strip=True)
        if len(s) >= 40:
            parts.append(s)
    return "\n\n".join(parts).strip() or "[Empty after parse]"

# ---- 受限/动态站点识别（不给你突破登录，只做优雅退化）----
_BLOCK_HINTS = (
    "please enable javascript", "sign in", "log in", "subscribe", "are you a robot",
    "access denied", "verify you are human", "captcha"
)

def looks_likely_blocked(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in _BLOCK_HINTS) or len(text.strip()) < 300

def _pick_snippet_for_url(url: str, snippet: str = "", prefer_same_domain: bool = True) -> str:
    """
    返回用于该 URL 的 snippet（优先使用调用方传入的 snippet；否则用 SearXNG 搜索结果里的一段预览文字）。
    - snippet（参数）通常来自你在 SERP 阶段拿到的 result["content"]。
    - 若未传入，则对 URL 本身做一次搜索，取同域命中或首条结果的 content 作为兜底。
    """
    if snippet:
        return snippet.strip()
    try:
        engines = getattr(config, "SNIPPET_ENGINES", "google,bing,brave")
        rows = searxng_search(url, engines=engines, pages=1, k_per_query=3) or []
        if not rows:
            return ""
        dom = domain_of(url)
        if prefer_same_domain:
            for it in rows:
                u = normalize_url(it.get("url") or "")
                if domain_of(u) == dom:
                    return (it.get("snippet") or "").strip()
        return (rows[0].get("snippet") or "").strip()
    except Exception:
        return ""


def fetch_text(url: str, max_chars: int = config.FETCH_MAX_CHARS, snippet: str = "") -> str:
    """
    Fetch & extract 主内容（HTML/PDF）。
    统一输出结构，**始终把 SNIPPET 放在最前**：
        SNIPPET: <来自搜索引擎的可见预览文字>
        TITLE:   <页面标题/推断标题>
        BODY:    <抽取到的正文，可能为空；若为受限/被拦截站点，此段可能缺失或极短>
        SOURCE:  <原始 URL>

    说明：
    - SNIPPET = search engine 结果页对该链接的简短预览文本（通常是标题+摘要片段），
      代表“用户在不点开网页时最能看到/认到的信息”。我们用它在被 403/登录墙 时兜底。
    """

    url_l = url.lower()

    # ---------- 1) 明确受限域：ResearchGate / X(Twitter) 等，直接走 snippet 预览 ----------
    if "researchgate.net/publication/" in url_l:
        # 只做“可公开识别”的摘要拼装：从 slug 推断标题 + snippet 置顶 + 源地址
        try:
            slug = url.split("/publication/")[1].split("/")[0]
        except Exception:
            slug = url.split("/publication/")[-1]
        # 从 slug 推断一个人类可读标题
        guessed_title = slug.replace("_", " ").strip()
        sn = _pick_snippet_for_url(url, snippet)

        parts = []
        if sn:
            parts.append(f"SNIPPET: {sn}")
        if guessed_title:
            parts.append(f"TITLE: {guessed_title}")
        parts.append(f"SOURCE: {url}")
        return clean_text("\n\n".join(parts), max_chars)

    if "x.com/" in url_l or "twitter.com/" in url_l or "researchgate.net/" in url_l or "scholar.google.com" in url_l:
        # 其它 RG/X 页面：同样不抓正文，直接走 snippet 兜底
        sn = _pick_snippet_for_url(url, snippet)
        parts = []
        if sn:
            parts.append(f"SNIPPET: {sn}")
        parts.append(f"SOURCE: {url}")
        return clean_text("\n\n".join(parts), max_chars)

    # ---------- 2) Scholar citations 页面直接跳过 ----------
    if "scholar.google.com/citations" in url_l:
        return "[Skip] Google Scholar citations page (JS-heavy)"

    # ---------- 3) 常规抓取（HTML/PDF），若 40x/429 则回退 snippet ----------
    try:
        r = requests.get(url, timeout=10, headers=config.UA)
        if not r.ok:
            # 403/401/429 等都走 snippet 兜底
            sn = _pick_snippet_for_url(url, snippet)
            parts = []
            if sn:
                parts.append(f"SNIPPET: {sn}")
            parts.append(f"[FetchError] HTTP {r.status_code} for {url}")
            parts.append(f"SOURCE: {url}")
            return clean_text("\n\n".join(parts), max_chars)

        ct = (r.headers.get("content-type") or "").lower()
        is_pdf = ("application/pdf" in ct) or url_l.endswith(".pdf")

        if is_pdf:
            try:
                from pdfminer.high_level import extract_text as pdf_extract
                text = pdf_extract(io.BytesIO(r.content)) or ""
                sn = _pick_snippet_for_url(url, snippet)
                parts = []
                if sn:
                    parts.append(f"SNIPPET: {sn}")
                if text.strip():
                    parts.append("TITLE: (from PDF)")
                    parts.append("BODY:\n" + text.strip())
                parts.append(f"SOURCE: {url}")
                return clean_text("\n\n".join(parts), max_chars)
            except Exception as e:
                sn = _pick_snippet_for_url(url, snippet)
                parts = []
                if sn:
                    parts.append(f"SNIPPET: {sn}")
                parts.append(f"[Skip] PDF extract failed: {e!r}")
                parts.append(f"SOURCE: {url}")
                return clean_text("\n\n".join(parts), max_chars)

        # HTML
        if ("text/html" not in ct) and ("application/xhtml" not in ct):
            sn = _pick_snippet_for_url(url, snippet)
            parts = []
            if sn:
                parts.append(f"SNIPPET: {sn}")
            parts.append(f"[Skip] Content-Type not HTML/PDF: {ct}")
            parts.append(f"SOURCE: {url}")
            return clean_text("\n\n".join(parts), max_chars)

        html_doc = r.text
        title = extract_title_unified(html_doc)  # 使用统一的标题提取函数
        body  = extract(html_doc) or ""  # trafilatura 主体抽取

        if not body.strip():
            # 轻量回退：取 <title> 与 h1/h2
            soup = BeautifulSoup(html_doc, "html.parser")
            heads = []
            if soup.title and soup.title.string:
                heads.append(soup.title.string.strip())
            for h in soup.find_all(["h1", "h2"])[:2]:
                heads.append(h.get_text(" ", strip=True))
            body = "\n".join(heads) or "[Empty after parse]"

        # ---- 统一拼装，**SNIPPET 始终放最前** ----
        sn = _pick_snippet_for_url(url, snippet)
        parts = []
        if sn:
            parts.append(f"SNIPPET: {sn}")
        if title:
            parts.append(f"TITLE: {title}")
        parts.append("BODY:\n" + body.strip())
        parts.append(f"SOURCE: {url}")

        return clean_text("\n\n".join(parts), max_chars)

    except Exception as e:
        sn = _pick_snippet_for_url(url, snippet)
        parts = []
        if sn:
            parts.append(f"SNIPPET: {sn}")
        parts.append(f"[FetchError] {e!r}")
        parts.append(f"SOURCE: {url}")
        return clean_text("\n\n".join(parts), max_chars)


# def extract_title(html_doc: str) -> str:
#     soup = BeautifulSoup(html_doc, "html.parser")

#     # 1. meta: dc.title
#     meta_title = soup.find("meta", attrs={"name": "dc.title"})
#     if meta_title and meta_title.get("content"):
#         return meta_title["content"].strip()

#     # 2. meta: og:title
#     og_title = soup.find("meta", property="og:title")
#     if og_title and og_title.get("content"):
#         return og_title["content"].strip()

#     # 3. meta: twitter:title
#     twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
#     if twitter_title and twitter_title.get("content"):
#         return twitter_title["content"].strip()

#     # 4. Specific patterns for academic/scientific sites
#     # Nature-specific (keeping for backward compatibility)
#     h1 = soup.find("h1", class_="c-article-title")
#     if h1:
#         return h1.get_text(" ", strip=True)

#     # ScienceDirect pattern
#     h1 = soup.find("h1", class_="svTitle")
#     if h1:
#         return h1.get_text(" ", strip=True)

#     # IEEE Xplore pattern
#     h1 = soup.find("h1", class_="document-title")
#     if h1:
#         return h1.get_text(" ", strip=True)

#     # ACM pattern
#     h1 = soup.find("h1", class_="citation__title")
#     if h1:
#         return h1.get_text(" ", strip=True)

#     # 5. Generic article title patterns (more common)
#     # Look for h1 with common article title classes/ids
#     for pattern in [
#         {"class": "article-title"},
#         {"class": "paper-title"},
#         {"class": "title"},
#         {"id": "title"},
#         {"class": "post-title"},
#         {"class": "entry-title"},
#         {"class": "headline"},
#         {"class": "article__title"},
#         {"class": "paper__title"}
#     ]:
#         h1 = soup.find("h1", pattern)
#         if h1:
#             return h1.get_text(" ", strip=True)

#     # 6. Look for any h1 if it seems like an article (contains keywords)
#     h1_candidates = soup.find_all("h1")
#     for h1 in h1_candidates:
#         text = h1.get_text(" ", strip=True)
#         # Skip navigation headers, menus, etc.
#         if len(text) > 10 and len(text) < 200 and not any(skip in text.lower() for skip in [
#             "menu", "navigation", "search", "login", "sign", "home", "about", "contact"
#         ]):
#             return text

#     # 7. Look for h2 titles if h1 is not suitable
#     h2_candidates = soup.find_all("h2", limit=3)
#     for h2 in h2_candidates:
#         text = h2.get_text(" ", strip=True)
#         if len(text) > 10 and len(text) < 200:
#             return text

#     # 8. Fallback to <title> tag
#     if soup.title and soup.title.string:
#         return soup.title.string.strip()

#     return ""

# def fetch_text(url: str, max_chars: int = config.FETCH_MAX_CHARS, snippet: str = "") -> str:
#     """Fetch and extract text content from URL"""
#     if "scholar.google.com/citations" in url:
#         return "[Skip] Google Scholar citations page (JS-heavy)"
    
    
#     if "https://www.researchgate.net/publication/" in url:
#         paper_name_link = url.split("/publication/")[1]
#         if snippet != "":
#             return f'{paper_name_link} {snippet}'
#         else:
#             searched_data = searxng_search(url, engines=["bing"], pages=1, k_per_query=1)
#             return f'ResearchGate Page Title: {paper_name_link} \n\n{searched_data[0]["snippet"]}'

#     if "x.com" in url or "researchgate.net" in url:
#         # use google search the x url to get the snippet as the x information as we can't use snscrape to get the x information
#         if snippet != "":
#             return f'{snippet}'
#         else:
#             searched_data = searxng_search(url, engines=["google"], pages=1, k_per_query=1)
#             return f'Snippet: {searched_data[0]["snippet"]}'
    
#     try:
#         r = requests.get(url, timeout=10, headers=config.UA)
#         if not r.ok:
#             return f"[FetchError] HTTP {r.status_code} for {url}"
#         ct = (r.headers.get("content-type") or "").lower()
#         is_pdf = ("application/pdf" in ct) or url.lower().endswith(".pdf")

#         if is_pdf:
#             try:
#                 from pdfminer.high_level import extract_text as pdf_extract
#                 text = pdf_extract(io.BytesIO(r.content)) or ""
#             except Exception as e:
#                 return f"[Skip] PDF extract failed: {e!r}"
#         else:
#             if ("text/html" not in ct) and ("application/xhtml" not in ct):
#                 return f"[Skip] Content-Type not HTML/PDF: {ct}"
#             html_doc = r.text
#             title = extract_title(html_doc)
#             print(f"HTML Page Title: {title}")
#             text = extract(html_doc) or ""
#             if not text:
#                 soup = BeautifulSoup(html_doc, "html.parser")
#                 heads = []
#                 if soup.title and soup.title.string:
#                     heads.append(soup.title.string.strip())
#                 for h in soup.find_all(["h1", "h2"])[:2]:
#                     heads.append(h.get_text(" ", strip=True))
#                 text = "\n".join(heads) or "[Empty after parse]"
            
#             if title:
#                 text = f"HTML Page Title: {title}\n\n{text}"
#         if snippet != "":
#             return f'HTML Page Snippet:{snippet} \n\n{clean_text(text, max_chars)}'
#         else:
#             return clean_text(text, max_chars)
#     except Exception as e:
#         return f"[FetchError] {e!r}"

# ============================ QUERY BUILDING FUNCTIONS ============================

def build_conference_queries(spec: Any, default_confs: Dict[str, List[str]], cap: int = 120) -> List[str]:
    """Build search queries for conferences"""
    import schemas

    if isinstance(spec, dict):
        spec = schemas.QuerySpec.model_validate(spec)

    venues = spec.venues if spec.venues else list(default_confs.keys())
    aliases = []
    for v in venues:
        if v in default_confs:
            aliases += default_confs[v]
        else:
            aliases.append(v)
    aliases = [a for a in aliases if a]

    keywords = spec.keywords or []
    years = spec.years if spec.years else config.DEFAULT_YEARS

    base = []
    for alias in aliases:
        for year in years:
            if keywords:
                for kw in keywords:
                    kw = kw.strip('"')
                    # Base query
                    base.append(f'{alias} {year} "{kw}"')
                    # Enhanced with acceptance hints
                    for h in config.ACCEPT_HINTS:
                        base.append(f'{alias} {year} "{kw}" {h}')
            else:
                # Scan acceptance pages even without keywords
                for h in config.ACCEPT_HINTS:
                    base.append(f'{alias} {year} {h}')

    # Add academic site searches if keywords exist
    if keywords:
        combo = " OR ".join([f'"{k.strip(chr(34))}"' for k in keywords])
        base += [
            f'site:openreview.net {combo}',
            f'site:semanticscholar.org {combo}',
            f'site:dblp.org {combo}',
            f'site:arxiv.org {combo}',
        ]

    # Deduplicate and limit
    seen = set()
    out = []
    for q in base:
        if q not in seen:
            seen.add(q)
            out.append(q)
            if len(out) >= cap:
                break
    return out

# ============================ URL SELECTION FUNCTIONS ============================

def heuristic_pick_urls(serp: List[Dict[str, str]], keywords: List[str],
                       need: int = 16, max_per_domain: int = 2) -> List[str]:
    """Heuristically pick URLs worth fetching"""

    count_by_dom: Dict[str, int] = {}
    seen_url = set()
    cand = []
    kws_l = [k.lower() for k in keywords] if keywords else []

    for r in serp:
        u = normalize_url(r.get("url", "") or "")
        if not u.startswith("http"):
            continue
        if u in seen_url:
            continue
        dom = domain_of(u)
        seen_url.add(u)
        cand.append((u, dom, (r.get("title") or ""), (r.get("snippet") or "")))

    def score(item):
        _u, dom, title, snip = item
        text = (title + " " + snip).lower()
        s = 0
        s += sum(2 for k in config.ACCEPT_HINTS if k in text)
        s += sum(1 for k in kws_l if k and k in text)
        s += min(len(title) // 40, 3)
        if looks_like_profile_url(_u):
            s += 1
        return s

    cand.sort(key=score, reverse=True)
    out = []
    for u, dom, _t, _s in cand:
        if count_by_dom.get(dom, 0) >= max_per_domain:
            continue
        out.append(u)
        count_by_dom[dom] = count_by_dom.get(dom, 0) + 1
        if len(out) >= need:
            break
    return out
