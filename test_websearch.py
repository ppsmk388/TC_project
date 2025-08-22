# agent_websearch.py
import os, json, re, time, requests, datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import trafilatura

# -------- LLM (OpenAI-compatible; bjqai) --------
from langchain_openai import ChatOpenAI
LLM = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-5"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.bjqai.com/v1"),
    temperature=0.1,
)

# -------- Web search (DuckDuckGo via ddgs) --------
try:
    from ddgs import DDGS
    USE_DDGS = True
except Exception:
    USE_DDGS = False

def ddg_search(query: str, k: int = 10) -> List[Dict[str,str]]:
    out = []
    if USE_DDGS:
        with DDGS() as d:
            for r in d.text(query, max_results=k, region="wt-wt", safesearch="off"):
                url = (r.get("href") or r.get("url") or "").strip()
                if not url.startswith("http"): continue
                out.append({
                    "title": (r.get("title") or "").strip(),
                    "url": url,
                    "snippet": (r.get("body") or "").strip()
                })
    return out

# -------- Scraper --------
UA = {"User-Agent": "Mozilla/5.0 (Talent-Copilot-ResearchAgent)"}
def fetch_page(url: str) -> str:
    try:
        r = requests.get(url, timeout=25, headers=UA)
        if not r.ok: return ""
        ct = r.headers.get("content-type","")
        if "text/html" not in ct and "application/xhtml" not in ct: return ""
        html = r.text
        text = trafilatura.extract(html) or ""
        # 兜底：取 <title> 和前 2 个 h1/h2
        if not text:
            soup = BeautifulSoup(html, "html.parser")
            heads = []
            if soup.title and soup.title.string: heads.append(soup.title.string.strip())
            for h in soup.find_all(["h1","h2"])[:2]:
                heads.append(h.get_text(" ", strip=True))
            text = "\n".join(heads)
        return text
    except Exception:
        return ""

# ========== Prompts (用你给的模板) ==========
planner_prompt_template = """
You are a planner. Your responsibility is to create a comprehensive plan to help your team answer a research question.
Questions may vary from simple to complex, multi-step queries. Your plan should provide appropriate guidance for your
team to use an internet search engine effectively.

Focus on highlighting the most relevant search term to start with, as another team member will use your suggestions
to search for relevant information.

If you receive feedback, you must adjust your plan accordingly. Here is the feedback received:
Feedback: {feedback}

Current date and time:
{datetime}

Your response must take the following json format:

"search_term": "The most relevant search term to start with",
"overall_strategy": "The overall strategy to guide the search process",
"additional_information": "Any additional information to guide the search including other search terms or filters"
"""

planner_guided_json = {
    "type": "object",
    "properties": {
        "search_term": {"type":"string"},
        "overall_strategy": {"type":"string"},
        "additional_information": {"type":"string"}
    },
    "required": ["search_term","overall_strategy","additional_information"]
}

selector_prompt_template = """
You are a selector. You will be presented with a search engine results page containing a list of potentially relevant
search results. Your task is to read through these results, select the most relevant one, and provide a comprehensive
reason for your selection.

here is the search engine results page:
{serp}

Return your findings in the following json format:

"selected_page_url": "The exact URL of the page you selected",
"description": "A brief description of the page",
"reason_for_selection": "Why you selected this page"

Adjust your selection based on any feedback received:
Feedback: {feedback}

Here are your previous selections:
{previous_selections}

Current date and time:
{datetime}
"""

selector_guided_json = {
    "type":"object",
    "properties":{
        "selected_page_url":{"type":"string"},
        "description":{"type":"string"},
        "reason_for_selection":{"type":"string"}
    },
    "required":["selected_page_url","description","reason_for_selection"]
}

reporter_prompt_template = """
You are a reporter. You will be presented with a webpage containing information relevant to the research question.
Your task is to provide a comprehensive answer to the research question based on the information found on the page.
Ensure to cite and reference your sources.

The research will be presented as a dictionary with the source as a URL and the content as the text on the page:
Research: {research}

The research question is:
{question}

Structure your response as follows (use bracketed numeric citations, e.g., [1], [2]):

Based on the information gathered, here is the comprehensive response to the query:
<your answer paragraph(s)>

Sources:
[1] <url 1>
[2] <url 2>

Adjust your response based on any feedback received:
Feedback: {feedback}

Here are your previous reports:
{previous_reports}

Current date and time:
{datetime}
"""

reviewer_prompt_template = """
You are a reviewer. Your task is to review the reporter's response to the research question and provide feedback.

Here is the reporter's response:
Report: {reporter}

Your feedback should include reasons for passing or failing the review and suggestions for improvement.

You should consider the previous feedback you have given when providing new feedback.
Feedback: {feedback}

Current date and time:
{datetime}

State of the agents (planner/selector/reporter in brief):
{state}

Your response must take the following json format:
"feedback": "If the response fails your review, provide precise feedback on what is required to pass the review.",
"pass_review": true/false,
"comprehensive": true/false,
"citations_provided": true/false,
"relevant_to_research_question": true/false
"""

reviewer_guided_json = {
    "type":"object",
    "properties":{
        "feedback":{"type":"string"},
        "pass_review":{"type":"boolean"},
        "comprehensive":{"type":"boolean"},
        "citations_provided":{"type":"boolean"},
        "relevant_to_research_question":{"type":"boolean"}
    },
    "required":["feedback","pass_review","comprehensive","citations_provided","relevant_to_research_question"]
}

router_prompt_template = """
You are a router. Your task is to route the conversation to the next agent based on the feedback provided by the reviewer.
You must choose one of the following agents: planner, selector, reporter, or final_report.

Feedback: {feedback}

Criteria:
- planner: If new information or different search directions are required.
- selector: If a different source should be selected from a SERP.
- reporter: If the report needs better formatting, clarity, or completeness.
- final_report: If pass_review is true.

Return ONLY JSON:  {"next_agent": "planner/selector/reporter/final_report"}
"""

router_guided_json = {"type":"object","properties":{"next_agent":{"type":"string"}},"required":["next_agent"]}

# -------- helpers --------
def now() -> str: return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def force_json(text: str) -> dict:
    """best-effort JSON parser"""
    text = text.strip()
    # try direct
    try: return json.loads(text)
    except Exception: pass
    # try to extract {...}
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    # fallback to key: value pairs (very weak)
    return {}

def serp_to_text(serp: List[Dict[str,str]]) -> str:
    lines = []
    for i, r in enumerate(serp, 1):
        lines.append(f"{i}. {r.get('title','').strip()}\n   URL: {r.get('url','')}\n   Snippet: {r.get('snippet','')}")
    return "\n".join(lines)

# -------- agent nodes --------
@dataclass
class AgentState:
    query: str
    feedback: str = ""
    planner: dict = field(default_factory=dict)
    serp: List[Dict[str,str]] = field(default_factory=list)
    selections: List[dict] = field(default_factory=list)
    research: Dict[str,str] = field(default_factory=dict)
    reports: List[str] = field(default_factory=list)
    final_report: Optional[str] = None

def agent_planner(st: AgentState):
    prompt = planner_prompt_template.format(
        feedback=st.feedback or "None",
        datetime=now()
    )
    out = LLM.invoke(prompt).content
    print(f'planner output: {out}')
    st.planner = force_json(out)
    # 如果 planner 没有 search_term，退化为用户 query
    if not st.planner.get("search_term"):
        st.planner["search_term"] = st.query

def agent_web_search(st: AgentState, k=10):
    term = st.planner.get("search_term", st.query)
    # 附加用户 query 里的限定
    st.serp = ddg_search(term, k=k)

def agent_selector(st: AgentState):
    prompt = selector_prompt_template.format(
        serp=serp_to_text(st.serp) if st.serp else "EMPTY",
        feedback=st.feedback or "None",
        previous_selections=json.dumps(st.selections, ensure_ascii=False),
        datetime=now()
    )
    out = LLM.invoke(prompt).content
    print(f'selector output: {out}')
    sel = force_json(out)
    if sel.get("selected_page_url"):
        st.selections.append(sel)

def agent_scrape(st: AgentState):
    if not st.selections: return
    url = st.selections[-1]["selected_page_url"]
    text = fetch_page(url)
    if text and len(text) > 250:
        st.research[url] = text

def agent_reporter(st: AgentState):
    prompt = reporter_prompt_template.format(
        research=json.dumps(st.research, ensure_ascii=False)[:120000],
        question=st.query,
        feedback=st.feedback or "None",
        previous_reports="\n\n---\n\n".join(st.reports[-2:]),
        datetime=now()
    )
    out = LLM.invoke(prompt).content
    print(f'reporter output: {out}')
    st.reports.append(out)

def agent_reviewer(st: AgentState) -> dict:
    prompt = reviewer_prompt_template.format(
        reporter=st.reports[-1] if st.reports else "",
        feedback=st.feedback or "None",
        datetime=now(),
        state=json.dumps({
            "planner": st.planner,
            "selector": st.selections[-1] if st.selections else {},
            "reports": len(st.reports)
        }, ensure_ascii=False)
    )
    out = LLM.invoke(prompt).content
    print(f'reviewer output: {out}')
    return force_json(out)

def force_json(text: str) -> dict:
    """best-effort JSON parser, tolerate non-JSON chatter."""
    if not text:
        return {}
    text = text.strip()
    # try direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to extract the first {...} block
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        chunk = m.group(0)
        # normalize common issues
        chunk = chunk.replace("True", "true").replace("False", "false")
        try:
            return json.loads(chunk)
        except Exception:
            pass
    return {}  # fall back to empty

def agent_router(review: dict) -> str:
    """Robust router: prefer LLM JSON; otherwise use deterministic fallback."""
    # 1) 如果评审通过，直接出栈
    if review.get("pass_review") is True:
        return "final_report"

    # 2) 让 LLM 试一次，拿不到就回退
    try:
        prompt = router_prompt_template.format(
            feedback=json.dumps(review, ensure_ascii=False)
        )
        out = LLM.invoke(prompt).content
        print(f"[router raw]: {out}")  # 调试：看 LLM 原样输出
        obj = force_json(out)
        nxt = obj.get("next_agent")
        if nxt in {"planner", "selector", "reporter", "final_report"}:
            return nxt
    except Exception as e:
        print(f"[router error]: {e}")

    # 3) 确定性回退逻辑（不依赖 LLM）
    #   - 不相关：让 planner 重新规划；
    #   - 没引文：回 reporter 补引文；
    #   - 不够全面：selector 换来源；
    #   - 其它默认回 planner。
    if review.get("relevant_to_research_question") is False:
        return "planner"
    if review.get("citations_provided") is False:
        return "reporter"
    if review.get("comprehensive") is False:
        return "selector"
    return "planner"


# -------- optional: candidate extraction to JSON (当 query 像“找人/实习生/候选人”) --------
CAND_SCHEMA = {
  "type":"object",
  "properties":{
    "candidates":{"type":"array","items":{
      "type":"object",
      "properties":{
        "name":{"type":"string"},
        "affiliation":{"type":"string"},
        "degree_status":{"type":"string"},
        "topics":{"type":"array","items":{"type":"string"}},
        "emails":{"type":"array","items":{"type":"string"}},
        "links":{"type":"array","items":{"type":"string"}}
      },
      "required":["name"]
    }}},
  "required":["candidates"]
}
def maybe_extract_candidates(st: AgentState) -> Optional[dict]:
    q = st.query.lower()
    if not any(k in q for k in ["intern","candidate","student","phd","master","实习","候选"]):
        return None
    # 让 LLM 从 research 文本里做结构化抽取（只这一处用到）
    sys = ("Extract potential current students (PhD/Master/Undergrad) relevant to the topic. "
           "Return STRICT JSON following the given schema.")
    content = json.dumps(st.research, ensure_ascii=False)[:120000]
    prompt = (sys + "\nSchema:\n" + json.dumps(CAND_SCHEMA) +
              "\n\nResearch dump (url->text):\n" + content)
    out = LLM.invoke(prompt).content
    return force_json(out)

# -------- main loop --------
def run_agent(query: str, max_rounds: int = 4) -> Dict[str,Any]:
    st = AgentState(query=query)
    next_agent = "planner"
    review = {}
    for _ in range(max_rounds):
        if next_agent == "planner":
            agent_planner(st)
            agent_web_search(st, k=12)
            next_agent = "selector"
            continue

        if next_agent == "selector":
            if not st.serp: agent_web_search(st, k=12)
            agent_selector(st)
            agent_scrape(st)
            next_agent = "reporter"
            continue

        if next_agent == "reporter":
            if not st.research:
                st.feedback = "No content retrieved. Please select a different result."
                next_agent = "selector"; continue
            agent_reporter(st)
            review = agent_reviewer(st)
            # 根据 review 路由
            st.feedback = review.get("feedback","")
            next_agent = agent_router(review)
            if next_agent == "final_report":
                st.final_report = st.reports[-1]
                break
            continue

        # 容错：默认回到 planner
        next_agent = "planner"

    result = {
        "plan": st.planner,
        "serp": st.serp,
        "selections": st.selections,
        "sources": list(st.research.keys()),
        "report": st.final_report or (st.reports[-1] if st.reports else ""),
        "review": review
    }
    # 可选：候选人 JSON 抽取
    cand = maybe_extract_candidates(st)
    if cand: result["candidates"] = cand.get("candidates", [])
    return result

# CLI demo
if __name__ == "__main__":
    import sys
    q = "MSRA social simulation rising star interns Singapore PhD student"
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    out = run_agent(q, max_rounds=5)
    print(json.dumps(out, ensure_ascii=False, indent=2))
