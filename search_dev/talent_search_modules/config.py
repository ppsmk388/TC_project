"""
Configuration module for Talent Search System
Contains all constants, configurations, and default values
"""

import os
from typing import Dict, List

# ============================ OUTPUT & STORAGE CONFIG ============================

# Output directory (fixed)
SAVE_DIR = "/home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/deep_research/example3_HR_intern_serxng/result_save"

# ============================ SEARXNG CONFIG ============================

# SearXNG configuration (fixed)
SEARXNG_BASE_URL = "http://127.0.0.1:8888"
SEARXNG_ENGINES = "google"   # Only use Google
SEARXNG_PAGES = 3          # Pages per query

# ============================ LOCAL VLLM CONFIG ============================

# Local vLLM configuration (fixed)
# LOCAL_OPENAI_URL = "http://localhost:6006/v1"
# LOCAL_OPENAI_MODEL = "/root/autodl-tmp/model_folder/Qwen/Qwen3-8B-Base/"
LOCAL_OPENAI_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LOCAL_OPENAI_MODEL = "qwen3-14b"
LOCAL_OPENAI_API_KEY = "sk-a713f7ae790d4ed086eff706e1cc0bb4"

# ============================ SEARCH & PROCESSING PARAMETERS ============================

# Iteration and crawling parameters (fixed)
MAX_ROUNDS = 3
SEARCH_K = 8           # Results per page per query
SELECT_K = 16          # Max URLs to fetch per round
FETCH_MAX_CHARS = 15000
VERBOSE = True
DEFAULT_TOP_N = 10     # Default if query doesn't specify

# User Agent
UA = {"User-Agent": "Mozilla/5.0 (TalentSearch-LangGraph-vLLM)"}

# ============================ LLM TOKEN LIMITS ============================

LLM_OUT_TOKENS = {
    "parse": 2048,
    "plan": 2048,
    "select": 2048,
    "authors": 2048,
    "synthesize": 3072,
    "paper_name": 2048,
}

# ============================ DEFAULT CONFERENCES & YEARS ============================

# Default conference library (used if user doesn't specify)
DEFAULT_CONFERENCES: Dict[str, List[str]] = {
    # 人工智能与机器学习
    "NeurIPS": ["NeurIPS"], "AAAI": ["AAAI"], "IJCAI": ["IJCAI"], "ICML": ["ICML"], "ICLR": ["ICLR"], 
    "KDD": ["KDD"], "ACL": ["ACL"], "EMNLP": ["EMNLP"], "NAACL": ["NAACL"],
    "AE": ["AE"], "IJCAR": ["IJCAR"],
    "CVPR": ["CVPR"], "ICCV": ["ICCV"], "ECCV": ["ECCV"],
    "COLING": ["COLING"],
    # 图形与可视化
    "SIGGRAPH": ["SIGGRAPH"], "ACM-MM": ["ACM MM"], "VIS": ["VIS"],
    # 数据与Web
    "SIGMOD": ["SIGMOD"], "VLDB": ["VLDB"], "SIGIR": ["SIGIR"],
    # 系统与并行计算
    "PODC": ["PODC"],
    # 网络与通信（从其他 CCF 分类）
    "SIGCOMM": ["SIGCOMM"],  # CCF A 类（已知网络顶级会议）
    "INFOCOM": ["INFOCOM"],  # CCF A 类（通信网络顶级会议）
    "NSDI": ["NSDI"],        # CCF A 类（系统设计与实现领域）
    # 人机交互
    "CHI": ["CHI"],
}

DEFAULT_YEARS = [2025, 2024, 2026]

# Acceptance hints for conference papers
ACCEPT_HINTS = [
    "accepted papers", "accept", "acceptance", "program",
    "proceedings", "schedule", "paper list", "main conference", "research track",
]

# ============================ VALIDATION CONSTANTS ============================

# Maximum lengths for various fields
MAX_AUTHORS = 25
MAX_KEYWORDS = 32
MAX_VENUES = 32
MAX_DEGREE_LEVELS = 32
MAX_AUTHOR_PRIORITY = 32
MAX_EXTRA_CONSTRAINTS = 32
MAX_SEARCH_TERMS = 120
MAX_URLS = 16

# Text length thresholds
MIN_TEXT_LENGTH = 50
MIN_AUTHOR_NAME_LENGTH = 2
MAX_AUTHOR_NAME_LENGTH = 80
