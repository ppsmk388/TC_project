from typing import Optional
import json

from .config import OPENAI_MODEL_DEFAULT

try:
    from openai import OpenAI
    _openai_client = OpenAI()
except Exception:  # pragma: no cover
    _openai_client = None


def llm_chat(system: str, user: str, model: Optional[str] = None, temperature: float = 0.2) -> str:
    model = model or OPENAI_MODEL_DEFAULT
    if _openai_client is None:
        return "[LLM unavailable] Configure OPENAI_API_KEY to enable analysis.\n\n" + user[:1500]
    try:
        resp = _openai_client.responses.create(
            model=model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
        )
        return getattr(resp, "output_text", "").strip() or json.dumps(resp.model_dump(), indent=2)[:5000]
    except Exception:
        try:
            resp = _openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"[LLM error] {e}"


