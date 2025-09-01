"""
LangGraph nodes and workflow for Talent Search System
Defines the main processing pipeline using LangGraph
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
import config
import utils
import schemas
import llm
import search
import extraction
from schemas import SelectSpec, QuerySpec, PlanSpec, LLMSelectSpec
from search import fetch_text, heuristic_pick_urls
from extraction import extract_authors_from_sources, synthesize_candidates
from utils import normalize_url, safe_sleep, looks_like_profile_url
from config import VERBOSE, DEFAULT_CONFERENCES, SEARCH_K, FETCH_MAX_CHARS, MIN_TEXT_LENGTH, MAX_ROUNDS, SELECT_K
from llm import safe_structured


# ============================ NODE IMPLEMENTATIONS ============================

def node_parse_query(state: schemas.ResearchState) -> Dict[str, Any]:
    """Parse user's natural language query into QuerySpec"""
    llm_instance = llm.get_llm("parse", temperature=0.3)
    conf_list = ", ".join(config.DEFAULT_CONFERENCES.keys())
    prompt = (
        "You are a professional talent recruitment analysis assistant responsible for parsing recruitment queries and extracting structured information.\n\n"
        "=== PARSING TASK INSTRUCTIONS ===\n"
        "Please carefully analyze the user's recruitment query and extract the following key information:\n\n"
        "1. **top_n** (int): Number of candidates needed. Look for numbers in the query like '10 candidates', '20 people', etc.\n\n"
        "2. **years** (int[]): Years to focus on for papers. Prioritize recent years like [2024,2025]. Default to [2025,2024] if not specified.\n\n"
        "3. **venues** (string[]): Target conferences/journals. Users will explicitly mention venues like 'ACL', 'NeurIPS', etc.\n"
        f"   Known venues include (not exhaustive): {conf_list}\n"
        "   Recognition rules:\n"
        "   - Direct conference names: ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML\n"
        "   - Conference variants: NIPS→NeurIPS, The Web Conference→WWW\n"
        "   - Platforms: OpenReview (counts as a venue)\n\n"
        "4. **keywords** (string[]): Research areas and technical keywords. Focus on identifying:\n"
        "   Technical keywords: LLM, large language models, transformer, attention, multi-agent, multi-agent systems, reinforcement learning, RL, graph neural networks, GNN, foundation model, social simulation, computer vision, CV, natural language processing, NLP\n"
        "   Research areas: machine learning, deep learning, AI alignment, robotics, computer vision, NLP, speech recognition, recommendation systems\n"
        "   Application areas: autonomous driving, medical AI, finance, social simulation, game theory, human-AI interaction\n\n"
        "5. **must_be_current_student** (bool): Whether candidates must be current students. Look for:\n"
        "   - Explicit requirements: current student, currently enrolled, active student\n"
        "   - Degree phases: PhD student, Master's student, graduate student\n"
        "   - Default: true (unless explicitly stated otherwise)\n\n"
        "6. **degree_levels** (string[]): Acceptable degree levels.\n"
        "   Recognition: PhD, MSc, Master, Graduate, Undergraduate, Bachelor, Postdoc\n"
        "   Default: ['PhD', 'MSc', 'Master', 'Graduate']\n\n"
        "7. **author_priority** (string[]): Author position preferences.\n"
        "   Recognition: first author, last author, corresponding author\n"
        "   Default: ['first', 'last']\n\n"
        "8. **extra_constraints** (string[]): Other constraints.\n"
        "   Recognition: geographic requirements (e.g., 'Asia', 'North America')\n"
        "   institutional requirements (e.g., 'top universities', 'Ivy League')\n"
        "   language requirements, experience requirements, etc.\n\n"
        "=== PARSING STRATEGY TIPS ===\n"
        "• Prioritize explicitly mentioned information, then make reasonable inferences\n"
        "• For technical keywords, identify specific models, methods, and research areas\n"
        "• Distinguish between different recruitment goals: interns vs researchers vs postdocs\n"
        "• Pay attention to time-sensitive information: recent publications, accepted papers, upcoming deadlines\n\n"
        "Return STRICT JSON format only, no additional text.\n\n"
        "User Query:\n"
        f"{state.query}\n"
    )
    spec = llm.safe_structured(llm_instance, prompt, schemas.QuerySpec)
    if config.VERBOSE:
        print(f"[parse] spec: top_n={spec.top_n}, years={spec.years}, venues={spec.venues}, keywords={spec.keywords}")
    return {"query_spec": spec.model_dump()}

def node_plan(state: schemas.ResearchState) -> Dict[str, Any]:
    """Generate search terms based on QuerySpec"""
    spec = schemas.QuerySpec.model_validate(state.query_spec)
    terms = search.build_conference_queries(spec, config.DEFAULT_CONFERENCES, cap=120)
    plan = schemas.PlanSpec(
        search_terms=terms,
        selection_hint="Prefer accepted/program/proceedings/schedule pages; then author profile pages (OpenReview, SemanticScholar, homepage, LinkedIn, Twitter)."
    )
    if config.VERBOSE:
        print(f"[plan] round={state.round} search_terms={len(plan.search_terms)}")
    return {"plan": plan.model_dump()}

def node_search(state: schemas.ResearchState) -> Dict[str, Any]:
    """Search using the generated terms"""
    serp = list(state.serp)
    terms = state.plan.get("search_terms", []) or [state.query]
    for term in terms:
        rows = search.searxng_search(term, pages=3, k_per_query=config.SEARCH_K)
        if config.VERBOSE:
            print(f"[search] {term} -> +{len(rows)}")
        for r in rows:
            r["term"] = term
            if not r["url"].startswith("http"):
                continue
            serp.append(r)
        utils.safe_sleep(0.05)

    # Deduplicate
    seen = set()
    uniq = []
    for r in serp:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            uniq.append(r)
    if config.VERBOSE:
        print(f"[search] got {len(uniq)} unique results")
    return {"serp": uniq}

def node_select_potential_papers(state: schemas.ResearchState) -> Dict[str, Any]:
    """Select URLs that potentially contain papers and author information"""
    llm_instance = llm.get_llm("select", temperature=0.3)
    
    # Get SERP items
    items = state.serp
    if not items:
        if config.VERBOSE:
            print("[select] No SERP items to select from")
        return {"selected_urls": list(state.selected_urls), "selected_serp": list(state.selected_serp)}
    
    selected_urls = []
    selected_serp = []
    
    # More strict URL filtering - remove low-quality domains
    not_allowed_domains = [
        "x.com", "twitter.com", "github.com", "linkedin.com", "facebook.com",
        "youtube.com", "reddit.com", "medium.com", "substack.com"
    ]
    
    # Also filter out news sites and general forums
    low_quality_domains = [
        "news", "blog", "forum", "discussion", "comment", "review"
    ]
    
    filtered_items = []
    for item in items:
        url = item.get("url", "").lower()
        
        # Check if URL contains any blocked domains
        if any(domain in url for domain in not_allowed_domains):
            continue
            
        # Check if URL contains low-quality indicators
        if any(indicator in url for indicator in low_quality_domains):
            continue
            
        filtered_items.append(item)
    
    if config.VERBOSE:
        print(f"[select] Filtered {len(items)} -> {len(filtered_items)} items after domain filtering")
    
    # Judge each filtered URL individually
    for i, item in enumerate(filtered_items):
        title = item.get("title", "")[:150]
        snippet = item.get("snippet", "")[:200]
        url = item.get("url", "")
        
        # More intelligent prompt with query context as filtering criteria
        query_context = ""
        if state.query_spec.venues:
            query_context += f"Target conferences: {', '.join(state.query_spec.venues)}\n"
        if state.query_spec.years:
            query_context += f"Target years: {', '.join(map(str, state.query_spec.years))}\n"
        if state.query_spec.keywords:
            query_context += f"Research keywords: {', '.join(state.query_spec.keywords)}\n"
        
        prompt = (
            f"Look at this search result and decide if it's worth fetching for academic talent search.\n\n"
            f"Query Context:\n{query_context}\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Snippet: {snippet}\n\n"
            f"SELECT this URL if it contains ANY of these valuable information:\n"
            f"1. **Paper details**: Paper titles, author names, abstracts, or paper content\n"
            f"2. **Academic lists**: Accepted papers lists, conference programs, workshop papers\n"
            f"3. **Researcher info**: Academic profiles, university pages, research institutions\n"
            f"4. **Conference content**: Proceedings, accepted papers, research tracks\n\n"
            f"PRIORITY: URLs that match the query context (conferences, years, keywords) are preferred.\n\n"
            f"REJECT only if it's clearly:\n"
            f"- Pure social media posts (x.com, facebook, linkedin)\n"
            f"- General news without academic content\n"
            f"- Personal blogs with no research information\n"
            f"- Spam or irrelevant content\n\n"
            f"Be reasonable - if it looks like it might contain academic/research info, select it.\n"
            f"Should I fetch this URL? Return JSON: {{ \"should_fetch\": true/false }}"
        )
        
        try:
            # Get LLM decision for this URL
            result = llm.safe_structured(llm_instance, prompt, schemas.LLMSelectSpec)
            
            if result and result.should_fetch:
                url = item.get("url", "")
                selected_urls.append(url)
                selected_serp.append(item) # Save the full SERP item
                if config.VERBOSE:
                    print(f"[select] URL {i+1} selected: {url[:50]}...")
            else:
                if config.VERBOSE:
                    print(f"[select] URL {i+1} rejected: {url[:50]}...") # TODO: add the reason why it is rejected
                    
        except Exception as e:
            if config.VERBOSE:
                print(f"[select] URL {i+1} error: {e}")
            continue
    
    # Update state with new selections
    current_selected = list(state.selected_urls)
    current_selected_serp = list(state.selected_serp)
    
    for url in selected_urls:
        if url not in current_selected:
            current_selected.append(url)
    
    for serp_item in selected_serp:
        if serp_item not in current_selected_serp:
            current_selected_serp.append(serp_item)
    
    if config.VERBOSE:
        print(f"[select] Final selection: {len(selected_urls)} URLs (total selected={len(current_selected)})")
    
    return {
        "selected_urls": current_selected,
        "selected_serp": current_selected_serp
    }

def node_fetch(state: schemas.ResearchState) -> Dict[str, Any]:
    """Fetch content from selected URLs"""
    sources = dict(state.sources)
    to_fetch = [u for u in state.selected_urls if u not in sources][:config.SELECT_K]
    
    if not to_fetch:
        if config.VERBOSE:
            print("[fetch] No new URLs to fetch")
        return {"sources": sources}
    
    if config.VERBOSE:
        print(f"[fetch] Fetching {len(to_fetch)} URLs")
    
    for u in to_fetch:
        try:
            txt = search.fetch_text(u, max_chars=config.FETCH_MAX_CHARS)
            
            if len(txt) < config.MIN_TEXT_LENGTH:
                if config.VERBOSE:
                    print(f"[skip-short] {u} -> {len(txt)} chars (too short)")
                continue
            
            sources[u] = txt
            
            if config.VERBOSE:
                print(f"[fetch] {u} -> {len(txt)} chars")
            
            # Rate limiting
            utils.safe_sleep(0.08)
            
        except Exception as e:
            if config.VERBOSE:
                print(f"[fetch-error] {u} -> {e}")
            continue
    
    if config.VERBOSE:
        print(f"[fetch] Completed, total sources: {len(sources)}")
    
    return {"sources": sources}

def node_expand_authors(state: schemas.ResearchState) -> Dict[str, Any]:
    """Extract and expand author searches"""
    spec = QuerySpec.model_validate(state.query_spec)
    authors = extract_authors_from_sources(state.sources, spec)

    # Generate author-specific search queries
    qset = list(dict.fromkeys(state.plan.get("search_terms", [])))
    add_queries = []
    for name in authors:
        name_q = name.strip()
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

def node_synthesize(state: schemas.ResearchState) -> Dict[str, Any]:
    """Synthesize final candidate information"""
    spec = QuerySpec.model_validate(state.query_spec)
    result = synthesize_candidates(state.sources, spec)

    # Generate report
    lines = [f"Found candidates (deduped): {len(result['candidates'])} (target {spec.top_n})\n"]
    for i, c in enumerate(result['candidates'][:spec.top_n], 1):
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

    # Add sources
    seen = set()
    cites = []
    for u in result['citations']:
        
        # NOTE: THIs maybe wrong
        nu = normalize_url(u)
        if nu and nu not in seen:
            seen.add(nu)
            cites.append(nu)
    if cites:
        lines.append("\n#### Sources (partial)")
        for j, u in enumerate(cites[:25], 1):
            lines.append(f"{j}. {u}")

    report_text = "\n".join(lines).strip()

    return {
        "report": report_text,
        "candidates": result['candidates'],
        "need_more": result['need_more'],
        "followups": result['followups'],
    }

def node_inc_round(state: schemas.ResearchState) -> Dict[str, Any]:
    """Increment round counter"""
    return {"round": state.round + 1}

# ============================ ROUTING FUNCTIONS ============================

def _route_after_fetch(state: schemas.ResearchState) -> str:
    """Route decision after fetching content"""
    if state.expanded_authors:
        return "synthesize"
    links = state.selected_urls
    prof_cnt = sum(1 for u in links if looks_like_profile_url(u))
    if VERBOSE:
        print(f"[route] profile-like links ≈ {prof_cnt}")
    return "expand" if prof_cnt < 5 else "synthesize"

def _route_after_synthesize(state: schemas.ResearchState) -> str:
    """Route decision after synthesizing candidates"""
    nxt = state.round + 1
    if state.need_more and nxt < MAX_ROUNDS:
        if VERBOSE:
            print(f"[route] continue -> round {nxt}")
        return "loop"
    if VERBOSE:
        print("[route] end")
    return "end"

# ============================ GRAPH CONSTRUCTION ============================

def build_graph():
    """Build the main LangGraph workflow"""
    g = StateGraph(schemas.ResearchState)

    # Add nodes
    g.add_node("parse_query", node_parse_query)
    g.add_node("plan", node_plan)
    g.add_node("search", node_search)
    g.add_node("select", node_select_potential_papers)
    g.add_node("fetch", node_fetch)
    g.add_node("expand_authors", node_expand_authors)
    g.add_node("synthesize", node_synthesize)
    g.add_node("inc_round", node_inc_round)

    # Set entry point
    g.set_entry_point("parse_query")

    # Add edges
    g.add_edge("parse_query", "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "select")
    g.add_edge("select", "fetch")
    g.add_conditional_edges("fetch", _route_after_fetch, {"expand": "expand_authors", "synthesize": "synthesize"})
    g.add_edge("expand_authors", "search")
    g.add_conditional_edges("synthesize", _route_after_synthesize, {"loop": "inc_round", "end": END})
    g.add_edge("inc_round", "plan")

    return g.compile()

def _ensure_state(x) -> schemas.ResearchState:
    """Ensure object is ResearchState instance"""
    return schemas.ResearchState.model_validate(x) if isinstance(x, dict) else x
