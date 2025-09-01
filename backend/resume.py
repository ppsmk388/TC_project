from typing import Dict
import io
import json
from PyPDF2 import PdfReader



def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(texts)


def process_homepage_url(url: str) -> str:
    """
    Process a candidate's homepage URL to extract relevant information.
    This is a placeholder function that would typically:
    1. Scrape the webpage content
    2. Extract key information (publications, bio, awards, etc.)
    3. Parse and structure the data
    
    For now, returns a placeholder text indicating the URL was processed.
    """
    # TODO: Implement actual web scraping and content extraction
    return f"Homepage processed: {url}\n\nThis function would extract:\n- Publications list\n- Academic background\n- Awards and recognition\n- Research interests\n- Professional experience"


def evaluate_resume_msra(text: str, role_type: str, research_area: str) -> Dict:
    """
    Evaluate resume using MSRA Research Internship criteria.
    Returns a structured evaluation following the MSRA rubric.
    """
    rubric = f"""
You are a senior MSRA hiring panelist evaluating a candidate for: {role_type}
Target research area: {research_area}

Evaluate using these MSRA criteria:

1. Academic Background (0-5):
   - University/research lab reputation
   - Advisor's recognition in the field  
   - Degree stage (MS/PhD preferred)

2. Research Output (0-5):
   - Publications at top-tier venues (NeurIPS, ICML, ICLR, ACL, CVPR, etc.)
   - Oral/Spotlight/Best Paper awards
   - First-author or equal contribution papers
   - Preprints showing an active pipeline

3. Research Alignment (0-5):
   - Topics closely match MSRA directions
   - Evidence of originality and problem definition ability

4. Recognition & Impact (0-5):
   - Fellowships, rising star awards, scholarships
   - Reviewer/PC/organizer roles in major conferences
   - Visible leadership in research community

Return JSON with:
- scores: dict with each criterion scored 0-5
- academic_background: detailed assessment
- research_output: detailed assessment  
- research_alignment: detailed assessment
- recognition_impact: detailed assessment
- overall_impression: strengths, weaknesses, verdict
"""
    
    data = {"resume_text": text[:40000]}
    prompt = rubric + "\n" + json.dumps(data)[:40000]
    
    try:
        raw = "Fake"
        obj = json.loads(raw)
        return obj
    except Exception:
        # Fallback to structured format if LLM fails
        return {
            "scores": {"academic_background": 3, "research_output": 3, "research_alignment": 3, "recognition_impact": 3},
            "academic_background": {"assessment": "Unable to parse - LLM evaluation failed"},
            "research_output": {"assessment": "Unable to parse - LLM evaluation failed"},
            "research_alignment": {"assessment": "Unable to parse - LLM evaluation failed"},
            "recognition_impact": {"assessment": "Unable to parse - LLM evaluation failed"},
            "overall_impression": {"verdict": "Evaluation failed - manual review required"}
        }


def evaluate_resume(text: str, role_type: str, topic: str) -> str:
    """
    Legacy function - now redirects to MSRA evaluation.
    Kept for backward compatibility.
    """
    result = evaluate_resume_msra(text, role_type, topic)
    return json.dumps(result, ensure_ascii=False, indent=2)


