import re
import json
import pandas as pd
import streamlit as st

# from backend.semantic_scholar import targeted_search
from backend.reports import build_achievement_report
from backend.resume import extract_pdf_text, evaluate_resume
from backend.twitter import fetch_tweets, summarize_trends
from frontend.theme import inject_global_css, header
from frontend.navigation import create_sidebar_navigation, create_sidebar_settings, create_sidebar_export
from frontend.home import render_home_page
from frontend.targeted_search import render_targeted_search_page, apply_targeted_search_styles
from frontend.achievement_report import render_achievement_report_page, apply_achievement_report_styles
from frontend.trend_radar import render_trend_radar_page, apply_trend_radar_styles


st.set_page_config(page_title="Talent Copilot HR", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
inject_global_css()
header()

# Session defaults
st.session_state.setdefault("search_results", pd.DataFrame())
st.session_state.setdefault("current_report", {})
st.session_state.setdefault("evaluation_result", {})
st.session_state.setdefault("trends_data", [])
st.session_state.setdefault("trends_summary", "")

# Create sidebar components
page = create_sidebar_navigation()
openai_key, search_api_key, twitter_bearer = create_sidebar_settings()
create_sidebar_export()

# Store API keys in session state for use across the app
st.session_state.setdefault("openai_api_key", "")
st.session_state.setdefault("search_api_key", "")
st.session_state.setdefault("twitter_bearer", "")


# -----------------------------
# Rubric config (weights & anchors)
# -----------------------------
RUBRIC_WEIGHTS = {
    "academic_background": 0.15,
    "research_output": 0.30,
    "research_alignment": 0.20,
    "technical_skills": 0.15,
    "recognition_impact": 0.10,
    "communication_collaboration": 0.05,
    "initiative_independence": 0.05,
}

RUBRIC_ANCHORS = {
    # Use these anchors as mental reference; the UI below shows a compact version
    # 10 / 8 / 6 / 4 / 2 = outstanding / strong / solid / weak / poor
    "academic_background": {
        10: "Top lab/university, renowned advisor, MS/PhD stage, top 10% grades",
        8:  "Tier-1/strong Tier-2, solid advisor, top 25% grades",
        6:  "Mainstream program, adequate advisor/curriculum",
        4:  "Ordinary program or cross-domain weak match",
        2:  "Clear mismatch (program/advisor/coursework)",
    },
    "research_output": {
        10: "Recent 1st-author top-venue (Oral/Spotlight/Best) + active pipeline + reproducible assets",
        8:  "Top-venue author (not necessarily 1st) or multiple strong preprints",
        6:  "Workshops/2nd-tier or 1–2 solid preprints",
        4:  "Scattered reports; weak reproducibility",
        2:  "No meaningful outputs",
    },
    "research_alignment": {
        10: "Highly aligned with MSRA; original framing & convincing evidence",
        8:  "Good alignment; can extend frontier work; clear next steps",
        6:  "Broadly aligned; limited originality/focus",
        4:  "Weak alignment; vague problem/method",
        2:  "Off-track to team priorities",
    },
    "technical_skills": {
        10: "Independent E2E pipeline; multi-GPU/distributed; engineering (CI/containers) sound",
        8:  "Independent on most tasks; pragmatic efficiency know-how",
        6:  "Implements under guidance; can modify open-source",
        4:  "Mostly API-level usage; weak scripts/repro",
        2:  "Insufficient coding/experiment skills",
    },
    "recognition_impact": {
        10: "High-prestige awards; top-venue reviewer/organizer; impactful OSS/tutorials",
        8:  "Scholarships/contests; repeated reviewing; visible blog/docs",
        6:  "Some local awards; occasional reviewing",
        4:  "Sparse recognition",
        2:  "None",
    },
    "communication_collaboration": {
        10: "Clear writing; strong talks; organizes multi-party work",
        8:  "Good prose/slides; solid Q&A",
        6:  "Understandable but needs editing",
        4:  "Unclear or weak structure",
        2:  "Blocks collaboration",
    },
    "initiative_independence": {
        10: "Self-driven problem finding; consistent iteration & retrospectives",
        8:  "Pushes tasks quickly after light guidance",
        6:  "Executes plan; depends on external drive",
        4:  "Slow progress; stalls on blockers",
        2:  "Low initiative",
    },
}

BONUS_MALUS = {
    "spotlight_or_oral": 1,            # add to 100-point total
    "best_paper_or_nomination": 2,
    "high_quality_open_source": 1,
    "direct_project_fit": 1,
    "integrity_issue": -999,           # auto-reject
    "exaggeration_or_unreproducible": -2,
    "logistics_mismatch": -3,
}

DECISION_BANDS = [
    {"label": "A — Strong Recommend", "min": 85, "max": 100},
    {"label": "B — Recommend",         "min": 70, "max": 84},
    {"label": "C — Consider/Waitlist", "min": 55, "max": 69},
    {"label": "D — Decline",           "min": 0,  "max": 54},
]

def compute_weighted_score(scores: dict, weights: dict, bonus_points: int = 0) -> tuple[float, str]:
    """
    scores: dict of 1–10 integers per dimension
    returns (final_score_100_scale, decision_band_label)
    """
    base_10 = sum(scores[k] * weights[k] for k in weights)             # 0–10
    base_100 = base_10 * 10                                            # 0–100
    total_100 = base_100 + bonus_points
    # cap to [0,100]
    total_100 = max(0, min(100, total_100))

    band = next((b["label"] for b in DECISION_BANDS if b["min"] <= total_100 <= b["max"]), "Unclassified")
    return round(total_100, 1), band



# Update session state with current values
if openai_key:
    st.session_state.openai_api_key = openai_key
if search_api_key:
    st.session_state.search_api_key = search_api_key
if twitter_bearer:
    st.session_state.twitter_bearer = twitter_bearer

# Page content based on selection
if page == "🏠 Home":
    render_home_page()

elif page == "🔍 Targeted Search":
    apply_targeted_search_styles()
    render_targeted_search_page()

elif page == "📊 Achievement Report":
    apply_achievement_report_styles()
    render_achievement_report_page()

elif page == "📄 Resume Evaluation":
    import json
    import streamlit as st

    # =============================
    # Rubric config (weights & anchors)
    # =============================
    RUBRIC_WEIGHTS = {
        "academic_background": 0.15,
        "research_output": 0.30,
        "research_alignment": 0.20,
        "technical_skills": 0.15,
        "recognition_impact": 0.10,
        "communication_collaboration": 0.05,
        "initiative_independence": 0.05,
    }

    BONUS_MALUS = {
        "spotlight_or_oral": 1,            # add to 100-point total
        "best_paper_or_nomination": 2,
        "high_quality_open_source": 1,
        "direct_project_fit": 1,
        "integrity_issue": -999,           # auto-reject
        "exaggeration_or_unreproducible": -2,
        "logistics_mismatch": -3,
    }

    DECISION_BANDS = [
        {"label": "A — Strong Recommend", "min": 85, "max": 100},
        {"label": "B — Recommend",         "min": 70, "max": 84},
        {"label": "C — Consider/Waitlist", "min": 55, "max": 69},
        {"label": "D — Decline",           "min": 0,  "max": 54},
    ]

    DIM_LABELS = {
        "academic_background": "Academic Background (15%)",
        "research_output": "Research Output (30%)",
        "research_alignment": "Research Alignment (20%)",
        "technical_skills": "Technical Skills (15%)",
        "recognition_impact": "Recognition & Impact (10%)",
        "communication_collaboration": "Communication & Collaboration (5%)",
        "initiative_independence": "Initiative & Independence (5%)",
    }

    def compute_weighted_score(scores: dict, weights: dict, bonus_points: int = 0) -> tuple[float, str]:
        """Return (final_score_100_scale, decision_band_label)."""
        base_10 = sum(scores.get(k, 0) * weights[k] for k in weights)     # 0–10
        base_100 = base_10 * 10                                            # 0–100
        total_100 = base_100 + bonus_points
        total_100 = max(0, min(100, total_100))                            # clamp

        band = next((b["label"] for b in DECISION_BANDS if b["min"] <= total_100 <= b["max"]), "Unclassified")
        return round(total_100, 1), band

    # =============================
    # Header & rubric expander
    # =============================
    st.header("📄 Resume Evaluation")

    with st.expander("🎯 MSRA Research Internship Evaluation Criteria", expanded=False):
        st.markdown("""
**Scoring scale (per dimension, integers 1–10)**  
10 = outstanding · 8 = strong · 6 = solid · 4 = weak · 2 = poor

**Dimensions & weights**
- **Academic Background (15%)** — program/lab reputation, advisor standing, MS/PhD stage.
- **Research Output (30%)** — top-venue papers (NeurIPS/ICML/ICLR/ACL/CVPR…), Oral/Spotlight/Best, first/equal-first, active preprints, reproducibility.
- **Research Alignment (20%)** — closeness to MSRA focus; originality and precise problem framing.
- **Technical Skills (15%)** — end-to-end experimentation, multi-GPU/distributed, reproducible code, engineering hygiene.
- **Recognition & Impact (10%)** — fellowships/awards, reviewer/PC/organizer roles, open-source/community impact.
- **Communication & Collaboration (5%)** — clear writing/presentations; teamwork across groups.
- **Initiative & Independence (5%)** — self-driven progress, iteration, resilience.

**Bonus/Malus (applied to 100-point total)**
- +1 Oral/Spotlight; +2 Best Paper/Nomination  
- +1 High-quality open-source; +1 Direct project fit  
- −2 Unreproducible/exaggerated claims; −3 logistics mismatch  
- **Integrity issues → auto-reject**
""")

    # =============================
    # Left: input & params
    # =============================
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Input Method")
        input_method = st.radio("Choose input method:", ["PDF Upload", "Homepage URL"])

        resume_text = None
        if input_method == "PDF Upload":
            uploaded_file = st.file_uploader("Choose a PDF resume", type=["pdf"], help="Supports PDF resumes")
            if uploaded_file is not None:
                with st.spinner("Extracting text from PDF..."):
                    pdf_bytes = uploaded_file.read()
                    # assumes you have this helper
                    resume_text = extract_pdf_text(pdf_bytes)
        else:
            homepage_url = st.text_input(
                "Candidate Homepage URL",
                placeholder="https://example.com/~candidate",
                help="Enter the candidate's personal or lab homepage URL"
            )
            if homepage_url:
                st.info("Homepage URL input detected. This will be processed for candidate evaluation.")
                # fake backend for demo
                resume_text = f"Homepage: {homepage_url}"

        st.subheader("Evaluation Parameters")
        position_context = st.text_area(
            "Role requirements (optional):",
            placeholder="Describe the role to tailor the evaluation...",
            height=100,
            help="Provide specific role requirements to tailor the evaluation (optional)"
        )
        if (resume_text or input_method == "Homepage URL") and st.button("🔍 Evaluate Candidate", type="primary"):
            demo_mode = st.checkbox("Show demo result (Linxin Song example)", value=True, key="demo_mode")

            if not demo_mode:
                if not st.session_state.get("openai_api_key"):
                    st.error("⚠️ **OpenAI API Key Required**")
                    st.info("Please enter your OpenAI API key in the sidebar settings (🛠️ Settings → API Configuration) to use the AI-powered resume evaluation features.")
                    st.stop()

            if demo_mode:
                with st.spinner("Loading demo evaluation..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    for i, msg in enumerate([
                        "📚 Analyzing academic background...",
                        "📊 Reviewing research output...",
                        "🎯 Assessing research alignment...",
                        "🧪 Checking technical skills & community impact..."
                    ]):
                        progress_bar.progress(int((i + 1) * 25))
                        status_text.text(msg)

                    # ---- Demo result with numeric rubric & rationale ----
                    fake_evaluation_result = {
                        "candidate_name": "Linxin Song",
                        "scores": {
                            "academic_background": 8,
                            "research_output": 8,
                            "research_alignment": 9,
                            "technical_skills": 8,
                            "recognition_impact": 6,
                            "communication_collaboration": 7,
                            "initiative_independence": 8
                        },
                        "rationales": {
                            "academic_background": "Ph.D. @ USC (strong reputation). Advisor Jieyu Zhao is well-known in NLP fairness/LLMs. Prior M.Eng @ Waseda + RAs @ UMD/UTokyo → broad training.",
                            "research_output": "Publications across ICML/EMNLP/AISTATS/COLM/EACL/ICME Oral; 2025 preprints (CoAct-1, Reinforcement Finetuning, agents). Fewer Oral/Spotlight/Best than elite peers.",
                            "research_alignment": "LLM/VLM evaluation, RFT, multi-agent LLMs, synthetic data — tightly aligned with MSRA evaluation & agentic systems.",
                            "technical_skills": "End-to-end experimentation and iterative releases; credible codebases; pragmatic evaluation & agent frameworks.",
                            "recognition_impact": "Reviewer at NeurIPS/ICLR/EMNLP/ACL; Autogen (AG2) maintainer — visible community role; no major fellowships listed.",
                            "communication_collaboration": "Consistent paper writing, community posts, cross-group collaborations; effective teamwork signs.",
                            "initiative_independence": "Proposes timely, relevant problems (hallucination tax, agent collaboration), maintains active throughput."
                        },
                        "bonuses": ["high_quality_open_source", "direct_project_fit"],
                        "maluses": [],
                        "weights": RUBRIC_WEIGHTS
                    }

                    # Compute final score & decision band
                    bonus_points = sum(BONUS_MALUS[b] for b in fake_evaluation_result["bonuses"])
                    final_score, decision_band = compute_weighted_score(
                        scores=fake_evaluation_result["scores"],
                        weights=RUBRIC_WEIGHTS,
                        bonus_points=bonus_points
                    )
                    fake_evaluation_result["final_score"] = final_score
                    fake_evaluation_result["decision_band"] = decision_band

                    st.session_state.evaluation_result = fake_evaluation_result
                    status_text.text("✅ Evaluation complete!")
                    progress_bar.progress(100)

            else:
                # ---- Real evaluation path (your backend) ----
                if resume_text:
                    with st.spinner("Running MSRA evaluation..."):
                        from backend.resume import evaluate_resume_msra
                        result = evaluate_resume_msra(resume_text)
                        # ensure your backend returns the same schema keys used below
                        st.session_state.evaluation_result = result
                else:
                    st.error("Please provide resume text or PDF for real evaluation")

    # =============================
    # Right: results & rendering
    # =============================
    with col2:
        st.subheader("Evaluation Results")
        eval_result = st.session_state.get("evaluation_result")
        if eval_result:
            # Theme detection (optional)
            try:
                from streamlit_theme import st_theme
                theme = st_theme()
                current_theme = theme.get('base', 'light') if theme else 'light'
            except Exception:
                current_theme = 'light'

            # Container styling
            if current_theme == 'dark':
                container_style = "background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #334155; padding: 1rem; border-radius: 12px;"
                title_color = "#38bdf8"
                chip_bg = "#0b3a75"; chip_fg = "#dbeafe"
            else:
                container_style = "background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border: 2px solid #e1e5e9; padding: 1rem; border-radius: 12px;"
                title_color = "#1976d2"
                chip_bg = "#eff6ff"; chip_fg = "#1e40af"

            st.markdown(f"""
            <div id="msra-evaluation" style="{container_style}">
                <h1 style="text-align: center; color: {title_color}; margin-bottom: 1rem;">
                    🔍 Candidate Evaluation (Example: {eval_result.get('candidate_name', 'Candidate')})
                </h1>
            """, unsafe_allow_html=True)

            # Summary row: final score & decision band & bonuses
            s_col1, s_col2 = st.columns([1, 1])
            with s_col1:
                st.metric(label="Final Score (0–100)", value=eval_result.get("final_score", "—"))
            with s_col2:
                st.metric(label="Decision Band", value=eval_result.get("decision_band", "—"))

            # Bonuses & maluses chips
            bonuses = eval_result.get("bonuses", [])
            maluses = eval_result.get("maluses", [])
            if bonuses or maluses:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                st.write("**Bonus/Malus Applied**")
                chips = []
                for b in bonuses:
                    chips.append(f"<span style='display:inline-block;margin:2px;padding:4px 8px;border-radius:999px;background:{chip_bg};color:{chip_fg};font-size:12px;'>+ {b.replace('_',' ')}</span>")
                for m in maluses:
                    chips.append(f"<span style='display:inline-block;margin:2px;padding:4px 8px;border-radius:999px;background:#fee2e2;color:#991b1b;font-size:12px;'>− {m.replace('_',' ')}</span>")
                st.markdown(" ".join(chips), unsafe_allow_html=True)

            st.markdown("---")

            # Per-dimension breakdown
            scores = eval_result.get("scores", {})
            rationales = eval_result.get("rationales", {})
            for key in RUBRIC_WEIGHTS.keys():
                pretty = DIM_LABELS.get(key, key)
                sc = scores.get(key, None)
                rz = rationales.get(key, "—")

                # progress bar mapped to 0–10 → 0–100
                if sc is not None:
                    st.write(f"**{pretty}** — Score: {sc}/10")
                    st.progress(int(sc * 10))
                else:
                    st.write(f"**{pretty}** — Score: —")

                st.caption(rz)
                st.markdown("")

            # Show input context
            if 'Homepage:' in (eval_result.get('resume_excerpt', '') or ''):
                st.info("📡 Evaluation based on homepage URL input")
            elif 'resume_text' in eval_result:
                with st.expander("📄 Resume preview"):
                    txt = eval_result.get('resume_text', '')
                    st.text(txt[:800] + ("..." if len(txt) > 800 else ""))

            st.markdown("---")
            # Export
            e1, e2 = st.columns(2)
            with e1:
                json_data = json.dumps(eval_result, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name=f"msra_evaluation_{eval_result.get('candidate_name','candidate').replace(' ', '_')}.json",
                    mime="application/json"
                )
            with e2:
                # Markdown export
                lines = [f"# MSRA Candidate Evaluation: {eval_result.get('candidate_name','Candidate')}",
                         f"**Final Score**: {eval_result.get('final_score','—')}  ",
                         f"**Decision Band**: {eval_result.get('decision_band','—')}  ",
                         "", "## Dimension Scores & Rationales"]
                for key in RUBRIC_WEIGHTS.keys():
                    lines.append(f"### {DIM_LABELS.get(key, key)}")
                    lines.append(f"- **Score**: {scores.get(key,'—')}/10")
                    lines.append(f"- **Rationale**: {rationales.get(key,'—')}")
                    lines.append("")
                if bonuses or maluses:
                    lines.append("## Bonus / Malus")
                    if bonuses:
                        lines.append(f"- Bonuses: {', '.join(bonuses)}")
                    if maluses:
                        lines.append(f"- Maluses: {', '.join(maluses)}")
                md_content = "\n".join(lines)
                st.download_button(
                    label="📄 Download Markdown",
                    data=md_content,
                    file_name=f"msra_evaluation_{eval_result.get('candidate_name','candidate').replace(' ','_')}.md",
                    mime="text/markdown"
                )

            st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.info("Choose an input method and click **Evaluate Candidate** to start")

elif page == "📈 Trend Radar":
    apply_trend_radar_styles()
    render_trend_radar_page()


