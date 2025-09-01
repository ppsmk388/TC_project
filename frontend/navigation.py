import streamlit as st
import pandas as pd
import json


def create_sidebar_navigation():
    """Create the sidebar navigation with attractive buttons"""
    st.sidebar.title("🎯 Talent Copilot HR")
    st.sidebar.markdown("---")

    # Page selection with attractive buttons
    st.sidebar.markdown("### 🧭 Navigation")

    # Initialize current page if not set
    if "current_page" not in st.session_state:
        st.session_state.current_page = "🏠 Home"

    # Get current page for button styling and determine the main page
    current_page = st.session_state.current_page

    # Map sub-pages to main pages for sidebar highlighting
    main_page_mapping = {
        "research_groups": "📊 Achievement Report",
        "edit_group": "📊 Achievement Report",
        "generate_report": "📊 Achievement Report",
        "view_reports": "📊 Achievement Report",
        "view_single_report": "📊 Achievement Report",
        "trend_groups": "📈 Trend Radar",
        "edit_trend_group": "📈 Trend Radar",
        "generate_trend_report": "📈 Trend Radar",
        "view_trend_reports": "📈 Trend Radar",
        "view_single_trend_report": "📈 Trend Radar"
    }

    # Determine which main page should be highlighted in sidebar
    sidebar_highlight_page = main_page_mapping.get(current_page, current_page)

    # Track if any button was clicked to trigger rerun
    should_rerun = False
    new_page = current_page

    # Create navigation buttons with proper state management
    col1, col2 = st.columns(2)

    with col1:
        if st.sidebar.button("🏠 Home", use_container_width=True,
                     type="primary" if sidebar_highlight_page == "🏠 Home" else "secondary",
                     key="nav_home"):
            new_page = "🏠 Home"
            should_rerun = True

        if st.sidebar.button("🔍 Targeted Search", use_container_width=True,
                     type="primary" if sidebar_highlight_page == "🔍 Targeted Search" else "secondary",
                     key="nav_search"):
            new_page = "🔍 Targeted Search"
            should_rerun = True

        if st.sidebar.button("📊 Achievement Report", use_container_width=True,
                     type="primary" if sidebar_highlight_page == "📊 Achievement Report" else "secondary",
                     key="nav_report"):
            new_page = "research_groups"  # Use the sub-page directly
            should_rerun = True

    with col2:
        if st.sidebar.button("📄 Resume Evaluation", use_container_width=True,
                     type="primary" if sidebar_highlight_page == "📄 Resume Evaluation" else "secondary",
                     key="nav_resume"):
            new_page = "📄 Resume Evaluation"
            should_rerun = True

        if st.sidebar.button("📈 Trend Radar", use_container_width=True,
                     type="primary" if sidebar_highlight_page == "📈 Trend Radar" else "secondary",
                     key="nav_trend"):
            new_page = "trend_groups"  # Use the sub-page directly
            should_rerun = True

    # Update session state and rerun if needed
    if should_rerun and new_page != current_page:
        st.session_state.current_page = new_page
        st.session_state.page_changed = True
        st.rerun()

    # Return the main page for app.py routing
    return sidebar_highlight_page


def create_sidebar_settings():
    """Create the sidebar settings section"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🛠️ Settings")
    with st.sidebar.expander("API Configuration"):
        openai_key = st.text_input("OpenAI API Key", type="password")
        search_api_key = st.text_input("Search API Key", type="password")
        twitter_bearer = st.text_input("Twitter Bearer Token", type="password")
    
    return openai_key, search_api_key, twitter_bearer


def create_sidebar_export():
    """Create the sidebar export section"""
    st.sidebar.markdown("### 📤 Export")
    
    if st.sidebar.button("Export search results"):
        df = st.session_state.get("search_results")
        if isinstance(df, pd.DataFrame) and not df.empty:
            csv = df.to_csv(index=False)
            st.sidebar.download_button("Download CSV", csv, "candidates.csv", "text/csv")
    
    if st.sidebar.button("Export achievement report"):
        report_obj = st.session_state.get("current_report")
        if report_obj:
            report_json = json.dumps(report_obj, indent=2, ensure_ascii=False)
            st.sidebar.download_button("Download JSON", report_json, "achievement_report.json", "application/json")
