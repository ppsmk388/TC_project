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
    
    # Get current page for button styling
    current_page = st.session_state.current_page
    
    # Create navigation buttons with proper state management
    col1, col2 = st.columns(2)
    
    with col1:
        if st.sidebar.button("🏠 Home", use_container_width=True, 
                     type="primary" if current_page == "🏠 Home" else "secondary",
                     key="nav_home"):
            st.session_state.current_page = "🏠 Home"
            st.rerun()
        
        if st.sidebar.button("🔍 Targeted Search", use_container_width=True, 
                     type="primary" if current_page == "🔍 Targeted Search" else "secondary",
                     key="nav_search"):
            st.session_state.current_page = "🔍 Targeted Search"
            st.rerun()
        
        if st.sidebar.button("📊 Achievement Report", use_container_width=True, 
                     type="primary" if current_page == "📊 Achievement Report" else "secondary",
                     key="nav_report"):
            st.session_state.current_page = "📊 Achievement Report"
            st.rerun()
    
    with col2:
        if st.sidebar.button("📄 Resume Evaluation", use_container_width=True, 
                     type="primary" if current_page == "📄 Resume Evaluation" else "secondary",
                     key="nav_resume"):
            st.session_state.current_page = "📄 Resume Evaluation"
            st.rerun()
        
        if st.sidebar.button("📈 Trend Radar", use_container_width=True, 
                     type="primary" if current_page == "📈 Trend Radar" else "secondary",
                     key="nav_trend"):
            st.session_state.current_page = "📈 Trend Radar"
            st.rerun()
    
    return st.session_state.current_page


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
