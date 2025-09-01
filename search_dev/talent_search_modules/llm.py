"""
LLM configuration and wrapper functions for Talent Search System
Handles vLLM setup, structured output, and safe LLM interactions
"""

import json
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import config
import utils
import schemas
from langchain_community.chat_models.tongyi import ChatTongyi

# ============================ LLM CONFIGURATION ============================

# def get_llm(role: str, temperature: float = 0.4) -> ChatOpenAI:
#     """Get configured LLM instance for specific role"""
#     max_tokens = config.LLM_OUT_TOKENS.get(role, 2048)
#     return ChatOpenAI(
#         model=config.LOCAL_OPENAI_MODEL,
#         api_key=config.LOCAL_OPENAI_API_KEY,
#         base_url=config.LOCAL_OPENAI_BASE_URL,
#         temperature=temperature,
#         max_tokens=max_tokens,
#     )
    
    
def get_llm(role: str, temperature: float = 0.4) -> ChatTongyi:
    """Get configured LLM instance for specific role"""
    max_tokens = config.LLM_OUT_TOKENS.get(role, 2048)
    return ChatTongyi(
        model=config.LOCAL_OPENAI_MODEL,
        api_key=config.LOCAL_OPENAI_API_KEY,
        streaming=False,
        temperature=temperature,
        max_tokens=max_tokens,
    )

# ============================ JSON EXTRACTION UTILITIES ============================

def extract_json_block(s: str) -> Optional[dict]:
    """Extract JSON block from text response"""
    s = utils.strip_thinking(s)
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

# ============================ MINIMAL FALLBACKS ============================

def minimal_by_schema(schema_cls):
    """Return minimal valid instance of schema class"""
    if schema_cls is schemas.QuerySpec:
        return schemas.QuerySpec()
    if schema_cls is schemas.PlanSpec:
        return schemas.PlanSpec(search_terms=["accepted papers program proceedings schedule"], selection_hint="Prefer accepted/program/proceedings pages")
    if schema_cls is schemas.SelectSpec:
        return schemas.SelectSpec(urls=[])
    if schema_cls is schemas.CandidatesSpec:
        return schemas.CandidatesSpec(candidates=[], citations=[], need_more=True, followups=["Need more/better sources."])
    if schema_cls is schemas.AuthorListSpec:
        return schemas.AuthorListSpec(authors=[])
    if schema_cls is schemas.LLMSelectSpec:
        return schemas.LLMSelectSpec(should_fetch=False)
    if schema_cls is schemas.LLMSelectSpecWithValue:
        return schemas.LLMSelectSpecWithValue(should_fetch=False, value_score=0.0, reason="Default")
    if schema_cls is schemas.LLMSelectSpecHasAuthorInfo:
        return schemas.LLMSelectSpecHasAuthorInfo(has_author_info=False, confidence=0.0, reason="Default")
    if schema_cls is schemas.LLMPaperNameSpec:
        return schemas.LLMPaperNameSpec(paper_name="", have_paper_name=False)
    if schema_cls is schemas.LLMAuthorProfileSpec:
        return schemas.LLMAuthorProfileSpec()
    raise ValueError(f"Unknown schema class: {schema_cls}")

# ============================ SAFE STRUCTURED OUTPUT ============================

def safe_structured(llm: ChatOpenAI | ChatTongyi, prompt: str, schema_cls):
    """Safely get structured output from LLM with fallbacks"""
    if isinstance(llm, ChatOpenAI):
        try:
            if isinstance(llm, ChatOpenAI):
                return llm.with_structured_output(schema_cls).invoke(prompt)
            else:
                raise ValueError("Invalid LLM type")
        except Exception as e:
            if config.VERBOSE:
                print("[safe_structured] response_format failed:", repr(e))
    try:
        if isinstance(llm, ChatOpenAI):
            resp = llm.invoke(prompt)
        elif isinstance(llm, ChatTongyi):
            resp = llm.invoke(prompt, enable_thinking = False)
        else:
            raise ValueError("Invalid LLM type")
        txt = getattr(resp, "content", "") if hasattr(resp, "content") else str(resp)
        data = extract_json_block(txt)
        if data is not None:
            return schema_cls.model_validate(data)
        if config.VERBOSE:
            print("[safe_structured] no valid JSON block, use minimal")
    except Exception as e:
        if config.VERBOSE:
            print("[safe_structured] invoke fallback failed:", repr(e))

    return minimal_by_schema(schema_cls)
