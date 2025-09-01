import streamlit as st
import json
import pandas as pd
from pathlib import Path
import sys

# Import the backend module
import sys
from pathlib import Path

# Add the backend module to the path
sys.path.append(str(Path(__file__).parent.parent / "backend" / "talent_search_module"))

try:
    import agents
    from schemas import QuerySpec
    backend_available = True
except ImportError as e:
    backend_available = False

# Default values
DEFAULT_CONFERENCES = {
    "ICLR": "International Conference on Learning Representations",
    "ICML": "International Conference on Machine Learning", 
    "NeurIPS": "Neural Information Processing Systems",
    "ACL": "Association for Computational Linguistics",
    "EMNLP": "Empirical Methods in Natural Language Processing",
    "NAACL": "North American Chapter of the Association for Computational Linguistics"
}
DEFAULT_YEARS = [2025, 2024, 2023]

def load_demo_data():
    """Load demo data from JSON file"""
    try:
        demo_file = Path(__file__).parent.parent / "backend" / "demo_data.json"
        with open(demo_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        # Don't call st.error here as it's at module level
        print(f"Error loading demo data: {e}")
        return []

def create_editable_years(years, key_prefix):
    """Create an editable years input component with improved UI"""
    st.markdown("**📅 Target Years:**")
    
    # Display existing years as removable tags with better styling
    if years:
        # Create a grid layout for years
        year_cols = st.columns(min(4, len(years)))
        for idx, year in enumerate(years):
            with year_cols[idx % len(year_cols)]:
                # Year tag with improved styling
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: 2px solid #4facfe;
                    padding: 0.5rem 1rem;
                    border-radius: 25px;
                    font-size: 0.9rem;
                    text-align: center;
                    margin: 0.5rem 0.2rem;
                    font-weight: 600;
                    display: inline-block;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                    position: relative;
                ">
                    {year}
                </div>
                """, unsafe_allow_html=True)
                
                # Remove button with better styling
                if st.button("🗑️ Remove", key=f"remove_year_{key_prefix}_{idx}", type="secondary", use_container_width=True):
                    # Create a copy to avoid modification during iteration
                    years_copy = years.copy()
                    years_copy.pop(idx)
                    # Update the session state
                    st.session_state.query_spec["years"] = years_copy
                    st.rerun()
    
    # Add new year input with improved styling
    st.markdown("**➕ Add New Year:**")
    col_year1, col_year2 = st.columns([3, 1])
    with col_year1:
        new_year = st.text_input(
            "Enter year", 
            key=f"new_year_{key_prefix}", 
            placeholder="e.g., 2019",
            help="Enter a year between 2020-2030"
        )
    with col_year2:
        if st.button("Add Year", key=f"add_year_{key_prefix}", type="primary", use_container_width=True):
            if new_year and new_year.strip().isdigit():
                year_int = int(new_year.strip())
                if 1800 <= year_int <= 2030:  # Reasonable year range
                    if year_int not in years:
                        # Create a copy to avoid modification issues
                        years_copy = years.copy()
                        years_copy.append(year_int)
                        # Update the session state
                        st.session_state.query_spec["years"] = years_copy
                        st.rerun()
                    else:
                        st.warning(f"Year {year_int} is already in the list!")
                else:
                    st.error("Please enter a year between 1800-2030")
            else:
                st.error("Please enter a valid year number")
    
    return years

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
        header_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;"
        card_style = "background: #1e293b; border: 2px solid #334155; color: #f1f5f9;"
        tag_style = "background: #1e40af; color: #dbeafe; border: 1px solid #3b82f6;"
        text_color = "#f1f5f9"
        success_bg = "#065f46"
        success_border = "#10b981"
        preview_bg = "#1e293b"
        preview_border = "#334155"
    else:
        header_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;"
        card_style = "background: white; border: 2px solid #e1e5e9; color: #000000;"
        tag_style = "background: #e3f2fd; color: #1976d2; border: 1px solid #bbdefb;"
        text_color = "#495057"
        success_bg = "#d4edda"
        success_border = "#28a745"
        preview_bg = "#f8f9fa"
        preview_border = "#dee2e6"
    
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

    # Main layout - Left side for search and preview, right side for results
    col1, col2 = st.columns([1, 1.2])

    with col1:
        # Search Parameters Section
        st.markdown("### 🎯 Search Parameters")
        
        # Default MSRA search query
        default_query = """I am a recruiter from Microsoft Research Asia (MSRA). Please help me identify 4 potential rising star interns who are currently PhD or Master's students and are actively working on social simulation with large language models or multi-agent systems. Focus on candidates who have recent publications or accepted papers at top conferences (e.g., ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML) or on OpenReview."""
        
        search_query = st.text_area(
            "Search Query",
            value=default_query,
            height=200,
            help="Describe your ideal candidate profile and requirements"
        )
        
        # Search Preview Button
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🔍 **Run Search Preview**", type="primary", use_container_width=True):
            # Check if OpenAI API key is set
            if not st.session_state.get("openai_api_key"):
                st.error("⚠️ **OpenAI API Key Required**")
                st.info("Please enter your OpenAI API key in the sidebar settings (🛠️ Settings → API Configuration) to use the AI-powered search features.")
                st.stop()
            
            with st.spinner("🔄 Analyzing search query..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    if backend_available:
                        # Use backend module
                        status_text.text("🔍 Parsing search intent...")
                        progress_bar.progress(33)
                        
                        # Parse the query using backend module
                        query_spec = agents.agent_parse_search_query(search_query)
                        
                        if query_spec:
                            status_text.text("📊 Extracting parameters...")
                            progress_bar.progress(66)
                            
                            # Store the parsed query spec
                            st.session_state.query_spec = query_spec.dict()
                            st.session_state.show_preview = True
                            st.session_state.search_query = search_query
                            st.session_state.candidate_count = query_spec.top_n
                            
                            status_text.text("✅ Preview ready!")
                            progress_bar.progress(100)
                            st.rerun()
                        else:
                            st.error("Failed to parse search query. Please try again.")
                            progress_bar.empty()
                            status_text.empty()
                    else:
                        # Fallback to mock data
                        import time
                        for i in range(3):
                            progress_bar.progress((i + 1) * 33)
                            if i == 0:
                                status_text.text("🔍 Parsing search intent...")
                            elif i == 1:
                                status_text.text("📊 Extracting parameters...")
                            elif i == 2:
                                status_text.text("✅ Preview ready!")
                            time.sleep(0.5)
                        
                        # Create mock QuerySpec
                        mock_spec = {
                            "top_n": 10,
                            "years": [2025, 2024, 2023],
                            "venues": ["ICLR", "ICML", "NeurIPS", "ACL", "EMNLP", "NAACL"],
                            "keywords": ["social simulation", "multi-agent systems", "large language models"],
                            "must_be_current_student": True,
                            "degree_levels": ["PhD", "Master"],
                            "author_priority": ["first", "last"],
                            "extra_constraints": ["Asia", "research intern"]
                        }
                        
                        st.session_state.query_spec = mock_spec
                        st.session_state.show_preview = True
                        st.session_state.search_query = search_query
                        st.session_state.candidate_count = mock_spec["top_n"]
                        
                        status_text.text("✅ Preview ready!")
                        progress_bar.progress(100)
                        time.sleep(0.5)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error during search preview: {e}")
                    progress_bar.empty()
                    status_text.empty()

        # Search Preview Section (appears after clicking Run Search Preview)
        if st.session_state.get("show_preview", False) and st.session_state.get("query_spec"):
            st.markdown("---")
            
            # Preview Header
            st.markdown(f"""
            <div style="
                background: {preview_bg};
                border: 2px solid {preview_border};
                border-radius: 15px;
                padding: 1.5rem;
                margin: 1rem 0;
            ">
                <h3 style="margin: 0 0 1rem 0; color: {text_color};">🔍 Search Preview & Configuration</h3>
                <p style="margin: 0; color: {text_color}; opacity: 0.8;">
                    Review and customize the extracted search parameters before running the actual search.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Back to query button
            if st.button("🔄 Start New Query", type="secondary"):
                st.session_state.show_preview = False
                st.session_state.query_spec = None
                st.session_state.search_query = None
                # Clear the candidate count state
                if "candidate_count" in st.session_state:
                    del st.session_state.candidate_count
                st.rerun()
            
            # Get current QuerySpec
            query_spec = st.session_state.query_spec
            
            # Ensure all necessary fields exist to prevent errors
            if "keywords" not in query_spec:
                query_spec["keywords"] = []
            if "venues" not in query_spec:
                query_spec["venues"] = []
            if "years" not in query_spec:
                query_spec["years"] = []
            if "degree_levels" not in query_spec:
                query_spec["degree_levels"] = []
            if "author_priority" not in query_spec:
                query_spec["author_priority"] = []
            if "extra_constraints" not in query_spec:
                query_spec["extra_constraints"] = []
            if "must_be_current_student" not in query_spec:
                query_spec["must_be_current_student"] = False
            
            # Create simplified configuration interface - only show essential parameters
            st.markdown("#### 📊 Essential Parameters")
            
            # Number of candidates - using prettier input box and button
            st.markdown("**👥 Number of Candidates:**")
            
            # Initialize value in session state if not exists
            if "candidate_count" not in st.session_state:
                st.session_state.candidate_count = query_spec["top_n"]
            
            # Create a prettier input interface
            col_top_n1, col_top_n2 = st.columns([3, 1])
            with col_top_n1:
                new_top_n = st.number_input(
                    "Number of candidates to find",
                    min_value=1,
                    max_value=500,
                    value=st.session_state.candidate_count,
                    step=1,
                    key="edit_top_n_input",
                    help="Choose how many candidates you want to find"
                )
            with col_top_n2:
                if st.button("Update", key="update_top_n", type="primary", use_container_width=True):
                    if new_top_n != st.session_state.candidate_count:
                        st.session_state.candidate_count = new_top_n
                        query_spec["top_n"] = new_top_n
                        st.rerun()
            
          
            # Keywords/Research Areas section
            st.markdown("**🔬 Research Areas:**")
            
            # Ensure keywords list exists
            if "keywords" not in query_spec:
                query_spec["keywords"] = []
            
            if query_spec["keywords"]:
                # Show existing keywords with Research Area labels
                keyword_cols = st.columns(min(3, len(query_spec["keywords"])))
                for idx, keyword in enumerate(query_spec["keywords"]):
                    with keyword_cols[idx % len(keyword_cols)]:
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: 2px solid #667eea;
                            padding: 0.5rem 1rem;
                            border-radius: 25px;
                            font-size: 0.9rem;
                            text-align: center;
                            margin: 0.5rem 0.2rem;
                            font-weight: 600;
                            display: inline-block;
                            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                        ">
                            🧬 {keyword}
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("🗑️ Remove", key=f"remove_keyword_{idx}", type="secondary", use_container_width=True):
                            # Create a copy to avoid modification during iteration
                            keyword_copy = query_spec["keywords"].copy()
                            keyword_copy.pop(idx)
                            st.session_state.query_spec["keywords"] = keyword_copy
                            st.rerun()
            
            # Add new keyword/Research Area
            st.markdown("**➕ Add New Research Area:**")
            col_keyword1, col_keyword2 = st.columns([3, 1])
            with col_keyword1:
                new_keyword = st.text_input(
                    "Enter research area", 
                    key="new_keyword", 
                    placeholder="e.g., machine learning, computer vision",
                    help="Enter a research area or technical keyword"
                )
            with col_keyword2:
                if st.button("Add Area", key="add_keyword", type="primary", use_container_width=True):
                    if new_keyword and new_keyword.strip():
                        keyword_value = new_keyword.strip()
                        if keyword_value not in query_spec["keywords"]:
                            # Create a copy to avoid modification issues
                            keyword_copy = query_spec["keywords"].copy()
                            keyword_copy.append(keyword_value)
                            st.session_state.query_spec["keywords"] = keyword_copy
                            st.rerun()
                        else:
                            st.warning(f"Research area '{keyword_value}' is already in the list!")
                    else:
                        st.error("Please enter a research area")
            
            # Degree levels with custom input option
            st.markdown("**🎓 Degree of Talent:**")
            degree_options = ["PhD", "MSc", "Master", "Graduate", "Postdoc", "Undergraduate"]
            
            # Ensure degree_levels list exists
            if "degree_levels" not in query_spec:
                query_spec["degree_levels"] = []
            
            # Show existing selections
            if query_spec["degree_levels"]:
                degree_cols = st.columns(min(3, len(query_spec["degree_levels"])))
                for idx, degree in enumerate(query_spec["degree_levels"]):
                    with degree_cols[idx % len(degree_cols)]:
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                            color: white;
                            border: 2px solid #4facfe;
                            padding: 0.5rem 1rem;
                            border-radius: 25px;
                            font-size: 0.9rem;
                            text-align: center;
                            margin: 0.5rem 0.2rem;
                            font-weight: 600;
                            display: inline-block;
                            box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
                        ">
                            {degree}
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("🗑️ Remove", key=f"remove_degree_{idx}", type="secondary", use_container_width=True):
                            # Create a copy to avoid modification during iteration
                            degree_copy = query_spec["degree_levels"].copy()
                            degree_copy.pop(idx)
                            st.session_state.query_spec["degree_levels"] = degree_copy
                            st.rerun()
            
            # Add new degree level
            st.markdown("**➕ Add New Degree Level:**")
            col_degree1, col_degree2 = st.columns([3, 1])
            with col_degree1:
                new_degree = st.text_input(
                    "Enter degree level", 
                    key="new_degree", 
                    placeholder="e.g., Bachelor",
                    help="Enter a custom degree level"
                )
            with col_degree2:
                if st.button("Add Degree", key="add_degree", type="primary", use_container_width=True):
                    if new_degree and new_degree.strip():
                        degree_value = new_degree.strip()
                        if degree_value not in query_spec["degree_levels"]:
                            # Create a copy to avoid modification issues
                            degree_copy = query_spec["degree_levels"].copy()
                            degree_copy.append(degree_value)
                            st.session_state.query_spec["degree_levels"] = degree_copy
                            st.rerun()
                        else:
                            st.warning(f"Degree level '{degree_value}' is already in the list!")
                    else:
                        st.error("Please enter a degree level")
            
            # Run Targeted Search Button
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🚀 **Run Targeted Search**", type="primary", use_container_width=True):
                # Check if OpenAI API key is set
                if not st.session_state.get("openai_api_key"):
                    st.error("⚠️ **OpenAI API Key Required**")
                    st.info("Please enter your OpenAI API key in the sidebar settings (🛠️ Settings → API Configuration) to use the AI-powered search features.")
                    st.stop()
                
                with st.spinner("🔄 Running targeted search..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        if backend_available:
                            # Use backend module
                            status_text.text("🔍 Analyzing search parameters...")
                            progress_bar.progress(25)
                            
                            # covert to QuerySpec
                            cp_query_spec = query_spec.copy()
                            search_query_spec = QuerySpec(**cp_query_spec)
                            # Execute search using backend module
                            results = agents.agent_execute_search(search_query_spec)
                            
                            if results is not None:
                                status_text.text("📊 Ranking results...")
                                progress_bar.progress(75)
                                
                                # Store results and update state
                                st.session_state.search_results = results
                                st.session_state.show_preview = False
                                st.session_state.show_results = True
                                
                                status_text.text("✅ Search complete!")
                                progress_bar.progress(100)
                                st.rerun()
                            else:
                                st.error("Search failed. Please try again.")
                                progress_bar.empty()
                                status_text.empty()
                        else:
                            # Fallback to mock data
                            import time
                            for i in range(4):
                                progress_bar.progress((i + 1) * 25)
                                if i == 0:
                                    status_text.text("🔍 Parsing search intent...")
                                elif i == 1:
                                    status_text.text("📊 Extracting parameters...")
                                elif i == 2:
                                    status_text.text("✅ Preview ready!")
                                elif i == 3:
                                    status_text.text("✅ Preview ready!")
                                time.sleep(0.5)
                            
                            # Load demo data and store in session state
                            demo_data = load_demo_data()
                            st.session_state.search_results = demo_data
                            st.session_state.show_preview = False
                            st.session_state.show_results = True
                            status_text.text("✅ Search complete!")
                            progress_bar.progress(100)
                            time.sleep(0.5)
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error during search: {e}")
                        progress_bar.empty()
                        status_text.empty()

    with col2:
        # Results Section - Right side for search results
        st.markdown("### 📊 Search Results")
        
        # Check if we should show results
        if st.session_state.get("show_results", False) and st.session_state.get("search_results"):
            results = st.session_state.search_results
            
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
                
                # Analytics section
                st.markdown("---")
                st.markdown("### 📈 Search Analytics")
                
                col3_1, col3_2, col3_3, col3_4 = st.columns(4)
                
                with col3_1:
                    st.metric("Total Candidates", len(results))
                
                with col3_2:
                    # Count PhD candidates
                    phd_count = sum(1 for r in results if 'ph' in r.get('Current Role & Affiliation').lower())
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
        
        else:
            # Empty state - show when no results yet
            st.info("🔍 Click 'Run Search Preview' to analyze your query and configure search parameters")
            st.markdown("""
            <div style="text-align: center; padding: 2rem;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🎯</div>
                <p style="color: #6c757d;">This demo will show example results from our MSRA talent database</p>
            </div>
            """, unsafe_allow_html=True)

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
    
    /* Multiselect styling */
    .stMultiSelect > div > div > div {
        border-radius: 10px !important;
        border: 2px solid #e1e5e9 !important;
    }
    
    /* Slider styling */
    .stSlider > div > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    }
    
    /* Slider track styling */
    .stSlider > div > div > div {
        background: #e1e5e9 !important;
        border-radius: 10px !important;
    }
    
    /* Slider thumb styling */
    .stSlider > div > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: 2px solid white !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }
    
    /* Slider tick bar min/max labels styling for both themes */
    [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
        background: rgba(255, 255, 255, 0.9) !important;
        color: #1e293b !important;
        padding: 4px 8px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        backdrop-filter: blur(10px) !important;
    }
    
    /* Dark theme specific styling for slider labels */
    [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
        background: rgba(255, 255, 255, 0.95) !important;
        color: #0f172a !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* Light theme specific styling for slider labels */
    [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
        background: rgba(255, 255, 255, 0.95) !important;
        color: #1e293b !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        text-shadow: 0 1px 2px rgba(255, 255, 255, 0.8) !important;
    }
    </style>
    """, unsafe_allow_html=True)