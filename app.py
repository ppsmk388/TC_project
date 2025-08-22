import re
import json
import pandas as pd
import streamlit as st

from backend.semantic_scholar import targeted_search
from backend.reports import build_achievement_report
from backend.resume import extract_pdf_text, evaluate_resume
from backend.twitter import fetch_tweets, summarize_trends
from frontend.theme import inject_global_css, header
from frontend.navigation import create_sidebar_navigation, create_sidebar_settings, create_sidebar_export
from frontend.home import render_home_page
from frontend.targeted_search import render_targeted_search_page, apply_targeted_search_styles


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
create_sidebar_settings()
create_sidebar_export()

# Page content based on selection
if page == "🏠 Home":
    render_home_page()

elif page == "🔍 Targeted Search":
    apply_targeted_search_styles()
    render_targeted_search_page()

elif page == "📊 Achievement Report":
    st.header("📊 Researcher Achievement Report")
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Generate Report")
        person_name = st.text_input("Person name", value="", placeholder="Enter a researcher name")
        report_type = st.selectbox("Report type", ["Full report", "Recent achievements", "Publication stats", "Collaboration network"])
        time_range = st.selectbox("Time range", ["Last 6 months", "Last year", "Last 2 years", "All time"])
        if st.button("📊 Generate report", type="primary") and person_name:
            with st.spinner("Generating achievement report..."):
                summary_md = build_achievement_report(person_name)
                st.session_state.current_report = {"name": person_name, "summary": summary_md}

    with col2:
        st.subheader("Report")
        report_obj = st.session_state.get("current_report")
        if report_obj and report_obj.get("summary"):
            st.markdown(report_obj["summary"])
        else:
            st.info("Enter a name and click Generate report")

elif page == "📄 Resume Evaluation":
    st.header("📄 Resume Evaluation")
    
    # MSRA Evaluation Criteria Display
    with st.expander("🎯 MSRA Research Internship Evaluation Criteria", expanded=False):
        st.markdown("""
        **1. Academic Background**
        - University/research lab reputation
        - Advisor's recognition in the field
        - Degree stage (MS/PhD preferred)
        
        **2. Research Output**
        - Publications at top-tier venues (NeurIPS, ICML, ICLR, ACL, CVPR, etc.)
        - Oral/Spotlight/Best Paper awards
        - First-author or equal contribution papers
        - Preprints showing an active pipeline
        
        **3. Research Alignment**
        - Topics closely match MSRA directions
        - Evidence of originality and problem definition ability
        
        **4. Recognition & Impact**
        - Fellowships, rising star awards, scholarships
        - Reviewer/PC/organizer roles in major conferences
        - Visible leadership in research community
        """)
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Input Method")
        input_method = st.radio("Choose input method:", ["PDF Upload", "Homepage URL"])
        
        if input_method == "PDF Upload":
            uploaded_file = st.file_uploader("Choose a PDF resume", type=["pdf"], help="Supports PDF resumes")
            resume_text = None
            if uploaded_file is not None:
                with st.spinner("Extracting text from PDF..."):
                    pdf_bytes = uploaded_file.read()
                    resume_text = extract_pdf_text(pdf_bytes)
        else:
            homepage_url = st.text_input("Candidate Homepage URL", placeholder="https://example.com/~candidate", help="Enter the candidate's personal or lab homepage URL")
            resume_text = None
            if homepage_url:
                st.info("Homepage URL input detected. This will be processed for candidate evaluation.")
                # For now, we'll use a placeholder text since we're faking the backend
                resume_text = f"Homepage: {homepage_url}"
        
        st.subheader("Evaluation Parameters")
        evaluation_criteria = st.multiselect(
            "Evaluation criteria", 
            ["Academic Background", "Research Output", "Research Alignment", "Recognition & Impact"], 
            default=["Academic Background", "Research Output", "Research Alignment", "Recognition & Impact"]
        )
        position_context = st.text_area("Role requirements (optional)", placeholder="Describe the role to tailor the evaluation...")
        target_role = st.selectbox("Target role", ["Research Intern", "Collaborator", "Employee"], index=0)
        target_area = st.text_input("Target research area", value="LLM evaluation, multi-agent systems, synthetic data")
        
        if (resume_text or input_method == "Homepage URL") and st.button("🔍 Evaluate Candidate", type="primary"):
            # Show demo mode option
            demo_mode = st.checkbox("Show demo result (Linxin Song example)", value=True, key="demo_mode")
            
            if demo_mode:
                with st.spinner("Loading demo evaluation..."):
                    # Progress bar for demo
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Simulate evaluation progress
                    for i in range(4):
                        progress_bar.progress((i + 1) * 25)
                        if i == 0:
                            status_text.text("📚 Analyzing academic background...")
                        elif i == 1:
                            status_text.text("📊 Reviewing research output...")
                        elif i == 2:
                            status_text.text("🎯 Assessing research alignment...")
                        elif i == 3:
                            status_text.text("🏆 Evaluating recognition & impact...")
                    
                    # Fake backend function - always returns the example result
                    fake_evaluation_result = {
                        "candidate_name": "Linxin Song",
                        "academic_background": {
                            "institution": "Ph.D. @ USC (strong but not top-5 like MIT/Stanford; still solid reputation)",
                            "advisor": "Jieyu Zhao (well-known in NLP fairness/gender bias + growing recognition in LLMs)",
                            "prior_training": "M.Eng @ Waseda, research assistant @ Univ. of Maryland, Univ. of Tokyo → international, diverse research background",
                            "assessment": "Strong academic preparation, good advisor pedigree, diverse training"
                        },
                        "research_output": {
                            "publications": "Multiple at top venues (ICML 2024, EMNLP 2025, AISTATS 2023, EMNLP 2022, NeurIPS workshop, COLM 2025, ICME 2025 Oral, EACL 2024)",
                            "roles": "Several equal-contribution and first-author papers",
                            "pipeline": "Very active — several 2025 preprints (CoAct-1, Reinforcement Finetuning, etc.), covering evaluation + agents",
                            "assessment": "Solid publication record, though fewer Oral/Spotlight/Best Paper distinctions compared to top-tier peers"
                        },
                        "research_alignment": {
                            "focus_areas": "LLM/VLM evaluation, reinforcement finetuning, multi-agent LLMs, synthetic data",
                            "fit_to_msra": "Highly relevant (MSRA invests in data-centric AI, evaluation, multi-modal agents)",
                            "originality": "Tackles timely research questions (hallucination tax, knowledge deficiencies of LMs, agent collaboration)",
                            "assessment": "Very strong alignment with MSRA research themes"
                        },
                        "recognition_impact": {
                            "reviewer_service": "Reviewer for NeurIPS, ICLR, EMNLP, ACL, etc. → active in community",
                            "workshop_community": "Maintainer of AG2 (Autogen) → visible contribution in open-source/agent frameworks",
                            "awards_fellowship": "None listed (no Apple/OpenAI/NSF-style fellowship)",
                            "assessment": "Recognition is good but not elite — community engagement strong, but lacks high-prestige fellowships"
                        },
                        "overall_impression": {
                            "strengths": [
                                "Excellent alignment with MSRA research (LLMs, evaluation, agents, synthetic data)",
                                "Consistent pipeline of publications and preprints",
                                "Community contribution (AG2 maintainer, extensive reviewing)"
                            ],
                            "weaknesses": [
                                "No top-tier fellowships/major awards",
                                "Strong publication record, but fewer breakthrough recognitions (Oral/Spotlight/Best Paper)"
                            ],
                            "verdict": "Very promising research-oriented intern candidate; likely to co-author papers during internship"
                        }
                    }
                    st.session_state.evaluation_result = fake_evaluation_result
                    status_text.text("✅ Evaluation complete!")
                    progress_bar.progress(100)
            else:
                # Real evaluation using the MSRA criteria
                if resume_text:
                    with st.spinner("Running MSRA evaluation..."):
                        from backend.resume import evaluate_resume_msra
                        result = evaluate_resume_msra(resume_text, target_role, target_area)
                        st.session_state.evaluation_result = result
                else:
                    st.error("Please provide resume text or PDF for real evaluation")

    with col2:
        st.subheader("Evaluation Results")
        eval_result = st.session_state.get("evaluation_result")
        if eval_result:
            # Theme detection using st-theme component (must be first!)
            try:
                from streamlit_theme import st_theme
                theme = st_theme()
                current_theme = theme.get('base', 'light') if theme else 'light'
            except ImportError:
                current_theme = 'light'
                st.warning("Install st-theme: `pip install st-theme` for better theme detection")
            
            print(f'current theme: {current_theme}')
            
            # Display the MSRA-style evaluation result with enhanced styling
            # Apply theme-specific inline styles immediately
            if current_theme == 'dark':
                container_style = "background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #334155;"
                title_color = "#38bdf8"
            else:
                container_style = "background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border: 2px solid #e1e5e9;"
                title_color = "#1976d2"
            
            st.markdown(f"""
            <div class="msra-evaluation" id="msra-evaluation" style="{container_style}">
                <h1 style="text-align: center; color: {title_color}; margin-bottom: 2rem;">
                    🔍 Candidate Evaluation (Example: {eval_result.get('candidate_name', 'Candidate')})
                </h1>
            """, unsafe_allow_html=True)
            
            # Apply theme-specific styling
            theme_class = f"theme-{current_theme}"
            st.markdown(f"""
            <script>
            // Apply theme class to the evaluation container
            document.addEventListener('DOMContentLoaded', function() {{
                const msraElement = document.getElementById('msra-evaluation');
                if (msraElement) {{
                    msraElement.setAttribute('data-theme', '{current_theme}');
                    msraElement.classList.add('{theme_class}');
                    console.log('Theme applied:', '{current_theme}', 'Class:', '{theme_class}');
                    console.log('Element classes:', msraElement.className);
                    console.log('Element data-theme:', msraElement.getAttribute('data-theme'));
                }}
            }});
            </script>
            """, unsafe_allow_html=True)
            
            # Academic Background
            bg = eval_result.get("academic_background", {})
            if current_theme == 'dark':
                section_style = "background: #1e293b; border: 1px solid #334155; color: #f1f5f9;"
                content_style = "background: #0f172a; border: 1px solid #334155; color: #f1f5f9;"
                heading_style = "color: #38bdf8; border-bottom: 2px solid #334155; background: #0f172a;"
                assessment_style = "background: #1e40af; color: #dbeafe;"
            else:
                section_style = "background: #ffffff; border: 1px solid #e1e5e9; color: #000000;"
                content_style = "background: #f8fafc; border: 1px solid #e2e8f0; color: #000000;"
                heading_style = "color: #1e40af; border-bottom: 2px solid #dbeafe; background: #f8fafc;"
                assessment_style = "background: #eff6ff; color: #1e40af;"
            
            st.markdown(f"""
            <div class="msra-section" style="{section_style}">
                <h3 style="{heading_style}">1. Academic Background</h3>
                <div class="msra-section-content" style="{content_style}">
                    <ul style="color: #000000 !important;">
                        <li style="color: #000000 !important;"><strong>Institution</strong>: {bg.get('institution', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Advisor</strong>: {bg.get('advisor', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Prior Training</strong>: {bg.get('prior_training', '—')}</li>
                    </ul>
                </div>
                <div class="msra-assessment" style="{assessment_style}">
                    ✅ {bg.get('assessment', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Research Output
            ro = eval_result.get("research_output", {})
            st.markdown(f"""
            <div class="msra-section" style="{section_style}">
                <h3 style="{heading_style}">2. Research Output</h3>
                <div class="msra-section-content" style="{content_style}">
                    <ul style="color: #000000 !important;">
                        <li style="color: #000000 !important;"><strong>Publications</strong>: {ro.get('publications', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Roles</strong>: {ro.get('roles', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Pipeline</strong>: {ro.get('pipeline', '—')}</li>
                    </ul>
                </div>
                <div class="msra-assessment" style="{assessment_style}">
                    ✅ {ro.get('assessment', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Research Alignment
            ra = eval_result.get("research_alignment", {})
            st.markdown(f"""
            <div class="msra-section" style="{section_style}">
                <h3 style="{heading_style}">3. Research Alignment</h3>
                <div class="msra-section-content" style="{content_style}">
                    <ul style="color: #000000 !important;">
                        <li style="color: #000000 !important;"><strong>Focus Areas</strong>: {ra.get('focus_areas', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Originality</strong>: {ra.get('originality', '—')}</li>
                    </ul>
                </div>
                <div class="msra-assessment" style="{assessment_style}">
                    ✅ {ra.get('assessment', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Recognition & Impact
            ri = eval_result.get("recognition_impact", {})
            st.markdown(f"""
            <div class="msra-section" style="{section_style}">
                <h3 style="{heading_style}">4. Recognition & Impact</h3>
                <div class="msra-section-content" style="{content_style}">
                    <ul style="color: #000000 !important;">
                        <li style="color: #000000 !important;"><strong>Reviewer Service</strong>: {ri.get('reviewer_service', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Workshop/Community</strong>: {ri.get('workshop_community', '—')}</li>
                        <li style="color: #000000 !important;"><strong>Awards/Fellowship</strong>: {ri.get('awards_fellowship', '—')}</li>
                    </ul>
                </div>
                <div class="msra-assessment" style="{assessment_style}">
                    ⚠️ {ri.get('assessment', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Overall Impression
            oi = eval_result.get("overall_impression", {})
            if current_theme == 'dark':
                verdict_style = "background: #1e40af; color: #dbeafe; border: 1px solid #334155;"
            else:
                verdict_style = "background: #eff6ff; color: #1e40af; border: 1px solid #dbeafe;"
            
            st.markdown(f"""
            <div class="msra-section" style="{section_style}">
                <h3 style="{heading_style}">📌 Overall Impression</h3>
                <div class="msra-section-content" style="{content_style}">
                    <div style="margin-bottom: 1rem;">
                        <strong>Strengths:</strong>
                        <ul style="color: #000000 !important;">
                            {''.join([f'<li style="color: #000000 !important;">{strength}</li>' for strength in oi.get("strengths", [])])}
                        </ul>
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <strong>Weaknesses:</strong>
                        <ul style="color: #000000 !important;">
                            {''.join([f'<li style="color: #000000 !important;">{weakness}</li>' for weakness in oi.get("weaknesses", [])])}
                        </ul>
                    </div>
                </div>
                <div class="msra-verdict" style="{verdict_style}">
                    🎯 <strong>Verdict</strong><br/>
                    {oi.get('verdict', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show input method used
            if input_method == "Homepage URL":
                st.info(f"📡 Evaluation based on homepage URL input")
            elif resume_text:
                with st.expander("📄 Resume preview"):
                    st.text(resume_text[:800] + ("..." if len(resume_text) > 800 else ""))
            
            # Export functionality
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Export as JSON", type="secondary"):
                    import json
                    json_data = json.dumps(eval_result, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="Download JSON",
                        data=json_data,
                        file_name=f"msra_evaluation_{eval_result.get('candidate_name', 'candidate').replace(' ', '_')}.json",
                        mime="application/json"
                    )
            
            with col2:
                if st.button("📄 Export as Markdown", type="secondary"):
                    # Generate markdown report
                    md_content = f"""# MSRA Candidate Evaluation: {eval_result.get('candidate_name', 'Candidate')}

## 1. Academic Background
- **Institution**: {eval_result.get('academic_background', {}).get('institution', '—')}
- **Advisor**: {eval_result.get('academic_background', {}).get('advisor', '—')}
- **Prior Training**: {eval_result.get('academic_background', {}).get('prior_training', '—')}
- **Assessment**: {eval_result.get('academic_background', {}).get('assessment', '—')}

## 2. Research Output
- **Publications**: {eval_result.get('research_output', {}).get('publications', '—')}
- **Roles**: {eval_result.get('research_output', {}).get('roles', '—')}
- **Pipeline**: {eval_result.get('research_output', {}).get('pipeline', '—')}
- **Assessment**: {eval_result.get('research_output', {}).get('assessment', '—')}

## 3. Research Alignment
- **Focus Areas**: {eval_result.get('research_alignment', {}).get('focus_areas', '—')}
- **Fit to MSRA**: {eval_result.get('research_alignment', {}).get('fit_to_msra', '—')}
- **Originality**: {eval_result.get('research_alignment', {}).get('originality', '—')}
- **Assessment**: {eval_result.get('research_alignment', {}).get('assessment', '—')}

## 4. Recognition & Impact
- **Reviewer Service**: {eval_result.get('recognition_impact', {}).get('reviewer_service', '—')}
- **Workshop/Community**: {eval_result.get('recognition_impact', {}).get('workshop_community', '—')}
- **Awards/Fellowship**: {eval_result.get('recognition_impact', {}).get('awards_fellowship', '—')}
- **Assessment**: {eval_result.get('recognition_impact', {}).get('assessment', '—')}

## Overall Impression
**Strengths:**
{chr(10).join([f"- {s}" for s in eval_result.get('overall_impression', {}).get('strengths', [])])}

**Weaknesses:**
{chr(10).join([f"- {w}" for w in eval_result.get('overall_impression', {}).get('weaknesses', [])])}

**Verdict**: {eval_result.get('overall_impression', {}).get('verdict', '—')}
"""
                    st.download_button(
                        label="Download Markdown",
                        data=md_content,
                        file_name=f"msra_evaluation_{eval_result.get('candidate_name', 'candidate').replace(' ', '_')}.md",
                        mime="text/markdown"
                    )
            
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Choose an input method and click 'Evaluate Candidate' to start")

elif page == "📈 Trend Radar":
    st.header("📈 Trend Radar")
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Monitoring Setup")
        default_accounts = ["https://x.com/mtmoonyi", "https://x.com/ManlingLi_"]
        twitter_accounts = st.text_area("Twitter account list", value="\n".join(default_accounts), height=100, help="One account URL per line")
        trend_categories = st.multiselect("Trend categories", ["AI Research", "Social Simulation", "Multi-Agent Systems", "Computational Social Science", "Machine Learning"], default=["AI Research", "Social Simulation"])
        time_range = st.selectbox("Time range", ["Last 7 days", "Last 30 days", "Last 90 days"])
        if st.button("📈 Fetch Trends", type="primary"):
            with st.spinner("Fetching and analyzing social trends..."):
                raw_list = [acc.strip() for acc in twitter_accounts.split("\n") if acc.strip()]
                usernames = []
                for acc in raw_list:
                    m = re.findall(r"(?:https?://)?(?:www\.)?x\.com/([^/?#]+)", acc)
                    if m:
                        usernames.append(m[0])
                    else:
                        usernames.append(acc.lstrip("@"))
                tweets = fetch_tweets(usernames, n_per_user=20)
                st.session_state.trends_data = tweets
                st.session_state.trends_summary = summarize_trends(tweets) if tweets else ""

    with col2:
        st.subheader("Trend Analysis")
        tweets = st.session_state.get("trends_data") or []
        if tweets:
            with st.expander("Raw tweets"):
                st.dataframe(pd.DataFrame(tweets), use_container_width=True)
            if st.session_state.get("trends_summary"):
                st.markdown("### Trend Summary")
                st.markdown(st.session_state.get("trends_summary"))
        else:
            st.info("Click 'Fetch Trends' to start")


