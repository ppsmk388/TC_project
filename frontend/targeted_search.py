import streamlit as st
import json
import pandas as pd
from pathlib import Path

def load_demo_data():
    """Load demo data from JSON file"""
    try:
        demo_file = Path(__file__).parent.parent / "backend" / "demo_data.json"
        with open(demo_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading demo data: {e}")
        return []

def render_targeted_search_page():
    """Render the enhanced targeted search page with MSRA demo"""
    
    # Theme detection
    try:
        from streamlit_theme import st_theme
        theme = st_theme()
        current_theme = theme.get('base', 'light') if theme else 'light'
    except ImportError:
        current_theme = 'light'
    
    # Theme-specific styling
    if current_theme == 'dark':
        header_style = "background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%); color: white;"
        card_style = "background: #1e293b; border: 2px solid #334155; color: #f1f5f9;"
        tag_style = "background: #1e40af; color: #dbeafe; border: 1px solid #3b82f6;"
        text_color = "#f1f5f9"
        success_bg = "#065f46"
        success_border = "#10b981"
    else:
        header_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;"
        card_style = "background: white; border: 2px solid #e1e5e9; color: #000000;"
        tag_style = "background: #e3f2fd; color: #1976d2; border: 1px solid #bbdefb;"
        text_color = "#495057"
        success_bg = "#d4edda"
        success_border = "#28a745"
    
    # Page header
    st.markdown(f"""
    <div style="
        {header_style}
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">🔍 Targeted Talent Search</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Find rising stars in AI research with precision targeting
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Main layout
    col1, col2 = st.columns([1, 1.2])

    with col1:
        # Search Parameters Section - using native Streamlit styling
        st.markdown("### 🎯 Search Parameters")
        
        # Default MSRA search query
        default_query = """I am a recruiter from Microsoft Research Asia (MSRA). Please help me identify 10 potential rising star interns who are currently PhD or Master's students and are actively working on social simulation with large language models or multi-agent systems. Focus on candidates who have recent publications or accepted papers at top conferences (e.g., ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML) or on OpenReview."""
        
        search_query = st.text_area(
            "Search Query",
            value=default_query,
            height=200,
            help="Describe your ideal candidate profile and requirements"
        )
        
        # Additional search parameters
        st.markdown("#### 🔧 Additional Filters")
        
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            location = st.selectbox(
                "Location Focus",
                ["Global", "Asia", "North America", "Europe", "Singapore"],
                index=0
            )
            
            role_type = st.selectbox(
                "Target Role",
                ["Research Intern", "Collaborator", "Employee", "Postdoc"],
                index=0
            )
        
        with col1_2:
            experience_level = st.selectbox(
                "Experience Level",
                ["PhD Student", "Master Student", "Both Phd and Master", "Postdoc"],
                index=2
            )
            
            candidate_count = st.slider(
                "Number of Candidates",
                min_value=5,
                max_value=20,
                value=10,
                step=1
            )
        
        # Research areas (multi-select)
        research_areas = st.multiselect(
            "Research Areas",
            [
                "Social Simulation",
                "Multi-Agent Systems", 
                "Large Language Models",
                "Computational Social Science",
                "AI Agents",
                "Natural Language Processing",
                "Machine Learning",
                "Human Behavior Modeling"
            ],
            default=["Social Simulation", "Multi-Agent Systems", "Large Language Models"]
        )
        
        # Search button
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🔍 **Run Targeted Search**", type="primary", use_container_width=True):
            with st.spinner("🔄 Running targeted search..."):
                # Simulate search progress
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                import time
                for i in range(4):
                    progress_bar.progress((i + 1) * 25)
                    if i == 0:
                        status_text.text("🔍 Analyzing search parameters...")
                    elif i == 1:
                        status_text.text("📚 Searching academic databases...")
                    elif i == 2:
                        status_text.text("🎯 Filtering candidates...")
                    elif i == 3:
                        status_text.text("📊 Ranking results...")
                    time.sleep(0.5)
                
                # Load demo data
                demo_data = load_demo_data()
                st.session_state.search_results = demo_data
                status_text.text("✅ Search complete!")
                progress_bar.progress(100)
                time.sleep(0.5)
                status_text.empty()
                progress_bar.empty()

    with col2:
        # Results Section - using native Streamlit styling
        st.markdown("### 📊 Search Results")
        
        # Display results
        results = st.session_state.get("search_results", [])
        
        # Handle both DataFrame and list types
        if isinstance(results, pd.DataFrame):
            results = results.to_dict('records') if not results.empty else []
        
        if results and len(results) > 0:
            # Results summary
            st.success(f"Found {len(results)} candidates matching your criteria")
            
            # Display each candidate
            for i, candidate in enumerate(results, 1):
                name = candidate.get("Name", "Unknown")
                role = candidate.get("Current Role & Affiliation", "N/A")
                research_focus = candidate.get("Research Focus", [])
                profiles = candidate.get("Profiles", {})
                notable = candidate.get("Notable", "")
                
                                # Create a simple candidate card using only Streamlit components
                # Use expander to create a card-like appearance
                with st.expander(f"#{i} {name}", expanded=True):
                    # Header with name and badge
                    col_info, col_badge = st.columns([4, 1])
                    
                    with col_info:
                        st.markdown(f"### #{i} {name}")
                    
                    with col_badge:
                        st.markdown("""
                        <div style="
                            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                            color: white;
                            padding: 0.3rem 0.8rem;
                            border-radius: 20px;
                            font-size: 0.8rem;
                            font-weight: bold;
                            text-align: center;
                            margin-top: 0.5rem;
                        ">
                            Rising Star
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Current position
                    st.markdown(f"**📍 Current Position:** {role}")
                    
                    # Research focus with tags
                    if research_focus:
                        st.markdown("**🔬 Research Focus:**")
                        # Create columns for tags
                        tag_cols = st.columns(min(4, len(research_focus)))
                        for idx, focus in enumerate(research_focus[:4]):
                            with tag_cols[idx % len(tag_cols)]:
                                st.markdown(f"""
                                <div style="
                                    {tag_style}
                                    padding: 0.3rem 0.8rem;
                                    border-radius: 20px;
                                    font-size: 0.85rem;
                                    text-align: center;
                                    margin: 0.3rem 0.2rem;
                                    font-weight: 500;
                                    display: inline-block;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    {focus}
                                </div>
                                """, unsafe_allow_html=True)
                    
                    # Notable achievements with theme-specific styling
                    if notable:
                        st.markdown(f"""
                        <div style="
                            background: {success_bg};
                            color: {'#dbeafe' if current_theme == 'dark' else '#155724'};
                            padding: 0.8rem;
                            border-radius: 8px;
                            border-left: 4px solid {success_border};
                            margin: 1rem 0;
                        ">
                            🌟 <strong>Notable:</strong> {notable}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Profile links
                    if profiles:
                        st.markdown("**🔗 Profiles:**")
                        profile_cols = st.columns(min(3, len([v for v in profiles.values() if v])))
                        col_idx = 0
                        for platform, url in profiles.items():
                            if url and url.strip():
                                with profile_cols[col_idx % len(profile_cols)]:
                                    st.markdown(f"[🔗 {platform}]({url})")
                                col_idx += 1
            
            # Export options
            st.markdown("### 📤 Export Results")
            
            col2_1, col2_2 = st.columns(2)
            
            with col2_1:
                if st.button("📊 Export as CSV", type="secondary", use_container_width=True):
                    # Convert to DataFrame for CSV export
                    df_data = []
                    for candidate in results:
                        df_data.append({
                            'Name': candidate.get('Name', ''),
                            'Current Role & Affiliation': candidate.get('Current Role & Affiliation', ''),
                            'Research Focus': ', '.join(candidate.get('Research Focus', [])),
                            'Notable': candidate.get('Notable', ''),
                            'Homepage': candidate.get('Profiles', {}).get('Homepage', ''),
                            'Google Scholar': candidate.get('Profiles', {}).get('Google Scholar', ''),
                            'GitHub': candidate.get('Profiles', {}).get('GitHub', ''),
                            'LinkedIn': candidate.get('Profiles', {}).get('LinkedIn', '')
                        })
                    
                    df = pd.DataFrame(df_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="💾 Download CSV",
                        data=csv,
                        file_name="msra_targeted_search_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            with col2_2:
                if st.button("📋 Export as JSON", type="secondary", use_container_width=True):
                    json_data = json.dumps(results, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="💾 Download JSON",
                        data=json_data,
                        file_name="msra_targeted_search_results.json",
                        mime="application/json",
                        use_container_width=True
                    )
        else:
            # Empty state
            st.info("🔍 Click 'Run Targeted Search' to find candidates matching your criteria")
            st.markdown("""
            <div style="text-align: center; padding: 2rem;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🎯</div>
                <p style="color: #6c757d;">This demo will show example results from our MSRA talent database</p>
            </div>
            """, unsafe_allow_html=True)

    # Additional features section
    # Ensure results is a list for processing
    if isinstance(results, pd.DataFrame):
        results = results.to_dict('records') if not results.empty else []
    
    if results and len(results) > 0:
        st.markdown("---")
        
        # Analytics section
        st.markdown("### 📈 Search Analytics")
        
        col3_1, col3_2, col3_3, col3_4 = st.columns(4)
        
        with col3_1:
            st.metric("Total Candidates", len(results))
        
        with col3_2:
            # Count PhD candidates
            phd_count = sum(1 for r in results if 'PhD' in r.get('Current Role & Affiliation', ''))
            st.metric("PhD Candidates", phd_count)
        
        with col3_3:
            # Count candidates with GitHub
            github_count = sum(1 for r in results if r.get('Profiles', {}).get('GitHub', ''))
            st.metric("With GitHub", github_count)
        
        with col3_4:
            # Count candidates with publications
            pub_count = sum(1 for r in results if r.get('Notable', ''))
            st.metric("With Notable Work", pub_count)
        
        # Research focus distribution based on actual demo data
        st.markdown("#### 🔬 Research Focus Distribution")
        
        focus_counts = {}
        for candidate in results:
            for focus in candidate.get('Research Focus', []):
                focus_counts[focus] = focus_counts.get(focus, 0) + 1
        
        if focus_counts:
            # Create a more readable chart
            focus_df = pd.DataFrame(list(focus_counts.items()), columns=['Research Area', 'Count'])
            focus_df = focus_df.sort_values('Count', ascending=False)
            
            # Display as both chart and table
            col_chart, col_table = st.columns([2, 1])
            
            with col_chart:
                st.bar_chart(focus_df.set_index('Research Area'))
            
            with col_table:
                st.markdown("**Top Research Areas:**")
                for area, count in focus_df.head(8).values:
                    st.markdown(f"• **{area}**: {count} candidates")
        else:
            st.info("No research focus data available")

def apply_targeted_search_styles():
    """Apply custom CSS for targeted search page"""
    st.markdown("""
    <style>
    /* Enhanced button styling for targeted search */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(0,0,0,0.2) !important;
    }
    
    /* Primary button with gradient */
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    /* Secondary button styling */
    .stButton > button[data-testid="baseButton-secondary"] {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
        color: white !important;
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    }
    
    /* Text area styling */
    .stTextArea > div > div > textarea {
        border-radius: 10px !important;
        border: 2px solid #e1e5e9 !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)
