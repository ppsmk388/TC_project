import os
from typing import Optional

OPENAI_MODEL_DEFAULT: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SEMANTIC_SCHOLAR_API_KEY: Optional[str] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

S2_BASE: str = "https://api.semanticscholar.org/graph/v1"
S2_HEADERS = {}
if SEMANTIC_SCHOLAR_API_KEY:
    S2_HEADERS["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY


