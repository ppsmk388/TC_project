import streamlit as st
import json
import pandas as pd
from pathlib import Path
import sys
import time
import os
import textwrap

# Import the backend module
try:
    from backend.reports import build_achievement_report
    backend_available = True
except ImportError as e:
    backend_available = False

# Default groups data
DEFAULT_GROUPS = {
    "xingqiao_plan": {
        "name": "星桥计划",
        "members": [
            {
            "name": "Jinsook Lee",
            "homepage": "https://jinsook-jennie-lee.github.io/",
            "affiliation": "Ph.D. candidate, Information Science, Cornell University"
            },
            {
            "name": "Zengqing Wu",
            "homepage": "https://wuzengqing001225.github.io/",
            "affiliation": "Master's student, Graduate School of Informatics, Kyoto University; Research Associate, Osaka University"
            },
            {
            "name": "Xinyi Mou",
            "homepage": "https://xymou.github.io/",
            "affiliation": "Ph.D. student, Fudan University (Data Intelligence and Social Computing Lab)"
            },
            {
            "name": "Jiarui Ji",
            "homepage": "https://ji-cather.github.io/homepage/",
            "affiliation": "M.E. student, Gaoling School of Artificial Intelligence, Renmin University of China"
            }
        ],
        "description": "4 active researchers in computational social science, NLP, and AI agent simulation",
        "color": "#4facfe"
    },
    "interns": {
        "name": "Intern",
        "members": [
            {"name": "Sun Xiaoming", "homepage": "https://scholar.google.com/citations?user=intern1", "affiliation": "University of Science and Technology of China"},
            {"name": "Zhao Lei", "homepage": "https://scholar.google.com/citations?user=intern2", "affiliation": "Nanjing University"},
            {"name": "Wu Fang", "homepage": "https://scholar.google.com/citations?user=intern3", "affiliation": "Wuhan University"},
            {"name": "Yang Lin", "homepage": "https://scholar.google.com/citations?user=intern4", "affiliation": "Sun Yat-sen University"},
            {"name": "Guo Rui", "homepage": "https://scholar.google.com/citations?user=intern5", "affiliation": "Harbin Institute of Technology"}
        ],
        "description": "5 current interns",
        "color": "#00f2fe"
    },
    "hku_nlp": {
        "name": "HKU-NLP",
        "members": [
            {"name": "Dr. Alan Chan", "homepage": "https://nlp.hku.hk/alan-chan", "affiliation": "HKU"},
            {"name": "Dr. Betty Wong", "homepage": "https://nlp.hku.hk/betty-wong", "affiliation": "HKU"},
            {"name": "Dr. Charles Lee", "homepage": "https://nlp.hku.hk/charles-lee", "affiliation": "HKU"},
            {"name": "Dr. Diana Chen", "homepage": "https://nlp.hku.hk/diana-chen", "affiliation": "HKU"},
            {"name": "Dr. Edward Liu", "homepage": "https://nlp.hku.hk/edward-liu", "affiliation": "HKU"}
        ],
        "description": "5 HKU NLP researchers",
        "color": "#f093fb"
    }
}

def load_groups():
    """Load groups from session state or use defaults"""
    if "achievement_groups" not in st.session_state:
        st.session_state.achievement_groups = DEFAULT_GROUPS.copy()
    return st.session_state.achievement_groups

def save_groups(groups):
    """Save groups to session state"""
    st.session_state.achievement_groups = groups

def render_research_groups_page():
    """Render the main research groups page"""

    # Check backend module status (silent)
    if not backend_available:
        st.warning("⚠️ Backend module not available. Using mock data mode.")

    # Page header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">📊 Researcher Achievement Report</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Manage research groups and generate comprehensive reports
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons row
    col_actions1, col_actions2 = st.columns(2)

    with col_actions1:
        if st.button("➕ Create New Group", key="create_new_group_unique_test", type="primary", use_container_width=True):
            st.session_state.current_page = "edit_group"
            st.session_state.editing_group = None
            # Force clear any cached state and rerun
            st.session_state.page_changed = True
            st.rerun()

    with col_actions2:
        if st.button("📋 View Existing Reports", key="view_existing_reports_unique_test", type="primary", use_container_width=True):
            st.session_state.current_page = "view_reports"
            # Force clear any cached state and rerun
            st.session_state.page_changed = True
            st.rerun()

    st.markdown("---")

    # Load and display groups
    groups = load_groups()
    
    # Groups grid layout
    st.markdown("### 🎯 Research Groups")
    
    # Create a responsive grid layout
    group_ids = list(groups.keys())
    num_groups = len(group_ids)
    
    # Calculate optimal grid layout
    if num_groups <= 3:
        cols = st.columns(num_groups)
    elif num_groups <= 6:
        cols = st.columns(3)
    else:
        cols = st.columns(4)
    
    for i, group_id in enumerate(group_ids):
        group_data = groups[group_id]
        col_idx = i % len(cols)
        
        with cols[col_idx]:
            # Group card
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {group_data['color']}15 0%, {group_data['color']}05 100%);
                border: 2px solid {group_data['color']};
                border-radius: 15px;
                padding: 1.5rem;
                margin: 1rem 0;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin: 0; color: {group_data['color']}; font-size: 1.3rem;">{group_data['name']}</h3>
                    <div style="
                        background: {group_data['color']};
                        color: white;
                        padding: 0.3rem 0.8rem;
                        border-radius: 20px;
                        font-size: 0.8rem;
                        font-weight: bold;
                    ">
                        {len(group_data['members'])} members
                    </div>
                </div>
                <p style="margin: 0 0 1rem 0; color: #666; font-size: 0.9rem;">{group_data['description']}</p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem;">
            """, unsafe_allow_html=True)
            
            # Show first 3 members as preview
            for member in group_data['members'][:3]:
                st.markdown(f"""
                <div style="
                    background: {group_data['color']}20;
                    border: 1px solid {group_data['color']}40;
                    padding: 0.3rem 0.6rem;
                    border-radius: 12px;
                    font-size: 0.8rem;
                    color: {group_data['color']};
                ">
                    {member['name']}
                </div>
                """, unsafe_allow_html=True)
            
            if len(group_data['members']) > 3:
                st.markdown(f"""
                <div style="
                    background: {group_data['color']}20;
                    border: 1px solid {group_data['color']}40;
                    padding: 0.3rem 0.6rem;
                    border-radius: 12px;
                    font-size: 0.8rem;
                    color: {group_data['color']};
                ">
                    +{len(group_data['members']) - 3} more
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div></div>", unsafe_allow_html=True)
            
            # Action buttons for each group
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✏️ Edit", key=f"edit_{group_id}", use_container_width=True):
                    st.session_state.current_page = "edit_group"
                    st.session_state.editing_group = group_id
                    st.rerun()

            with col_btn2:
                if st.button("📊 Generate Report", key=f"report_{group_id}", use_container_width=True):
                    st.session_state.current_page = "generate_report"
                    st.session_state.selected_group = group_id
                    # Force clear any cached state and rerun
                    st.session_state.page_changed = True
                    st.rerun()

def render_edit_group_page():
    """Render the edit group page"""

    # Back button
    if st.button("← Back to Groups", key="back_to_groups_edit", type="secondary"):
        st.session_state.current_page = "research_groups"
        st.session_state.page_changed = True
        st.rerun()

    # Page header
    is_edit = st.session_state.get('editing_group') is not None
    if is_edit:
        st.markdown("### ✏️ Edit Research Group")
    else:
        st.markdown("### ➕ Create New Research Group")
    
    # Load groups
    groups = load_groups()
    editing_group_id = st.session_state.get('editing_group')
    
    if editing_group_id and editing_group_id in groups:
        group_data = groups[editing_group_id]
    else:
        group_data = {
            'name': '',
            'description': '',
            'color': '#667eea',
            'members': []
        }
    
    # Group basic info
    st.markdown("#### 📝 Group Information")
    
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        group_name = st.text_input("Group Name", value=group_data.get('name', ''), key="edit_group_name")
    with col_info2:
        available_colors = ["#667eea", "#764ba2", "#4facfe", "#00f2fe", "#f093fb", "#f5576c"]
        selected_color = st.selectbox("Group Color", available_colors, 
                                    index=available_colors.index(group_data.get('color', '#667eea')) if group_data.get('color') in available_colors else 0, 
                                    key="edit_group_color")
    
    group_description = st.text_area("Description", value=group_data.get('description', ''), 
                                    height=100, key="edit_group_description")
    
    # Members management
    st.markdown("#### 👥 Group Members")
    
    if "temp_members" not in st.session_state:
        st.session_state.temp_members = group_data.get('members', []).copy()
    
    # Display existing members
    if st.session_state.temp_members:
        # Add headers for member input fields
        col_header1, col_header2, col_header3, col_header4 = st.columns([2, 3, 2, 1])
        with col_header1:
            st.markdown("**👤 Name**")
        with col_header2:
            st.markdown("**🔗 Homepage** *(optional)*")
        with col_header3:
            st.markdown("**🏛️ Affiliation** *(optional)*")
        with col_header4:
            st.markdown("**Action**")

        st.markdown("---")

    for i, member in enumerate(st.session_state.temp_members):
        st.markdown(f"**Member {i+1}:**")
        col_member1, col_member2, col_member3, col_member4 = st.columns([2, 3, 2, 1])

        with col_member1:
            member_name = st.text_input("Name", value=member.get('name', ''),
                                      key=f"member_name_{i}", label_visibility="collapsed",
                                      placeholder="e.g., John Smith")
        with col_member2:
            member_homepage = st.text_input("Homepage", value=member.get('homepage', ''),
                                          key=f"member_homepage_{i}", label_visibility="collapsed",
                                          placeholder="https://example.com/~john")
        with col_member3:
            member_affiliation = st.text_input("Affiliation", value=member.get('affiliation', ''),
                                             key=f"member_affiliation_{i}", label_visibility="collapsed",
                                             placeholder="University/Institution")
        with col_member4:
            if st.button("🗑️", key=f"remove_member_{i}", help="Remove member"):
                st.session_state.temp_members.pop(i)
                st.rerun()

        # Update member data
        st.session_state.temp_members[i] = {
            'name': member_name,
            'homepage': member_homepage,
            'affiliation': member_affiliation
        }
    
    # Add new member
    if st.button("➕ Add Member", key="add_member"):
        st.session_state.temp_members.append({
            'name': '',
            'homepage': '',
            'affiliation': ''
        })
        st.rerun()
    
    st.markdown("---")
    
    # Action buttons
    col_actions1, col_actions2, col_actions3 = st.columns([1, 1, 1])
    
    with col_actions1:
        if st.button("💾 Save", key="save_group", type="primary", use_container_width=True):
            # Validate input
            if not group_name.strip():
                st.error("Group name is required!")
                return

            if not st.session_state.temp_members:
                st.error("Group must have at least one member!")
                return

            # Create/update group
            groups = load_groups()
            if editing_group_id:
                groups[editing_group_id] = {
                    'name': group_name.strip(),
                    'description': group_description.strip(),
                    'color': selected_color,
                    'members': [m for m in st.session_state.temp_members if m['name'].strip()]
                }
            else:
                # Generate new ID
                new_id = f"group_{len(groups) + 1}"
                groups[new_id] = {
                    'name': group_name.strip(),
                    'description': group_description.strip(),
                    'color': selected_color,
                    'members': [m for m in st.session_state.temp_members if m['name'].strip()]
                }

            save_groups(groups)
            st.session_state.temp_members = []
            st.session_state.current_page = "research_groups"
            st.session_state.page_changed = True
            st.rerun()

    with col_actions2:
        if st.button("❌ Cancel", key="cancel_edit", type="secondary", use_container_width=True):
            st.session_state.temp_members = []
            st.session_state.current_page = "research_groups"
            st.session_state.page_changed = True
            st.rerun()
    
    with col_actions3:
        if editing_group_id:
            # Delete group functionality with proper state management
            delete_confirm_key = f"delete_confirm_{editing_group_id}"

            # Initialize delete confirmation state if not exists
            if delete_confirm_key not in st.session_state:
                st.session_state[delete_confirm_key] = False

            # Show delete button first
            if st.button("🗑️ Delete Group", key=f"delete_group_{editing_group_id}", type="secondary", use_container_width=True):
                # Toggle the confirmation state
                st.session_state[delete_confirm_key] = True
                st.rerun()

            # Show confirmation checkbox and final delete button only after initial click
            if st.session_state[delete_confirm_key]:
                st.markdown("---")
                st.markdown("⚠️ **Confirm Group Deletion**")
                st.markdown("*This action cannot be undone.*")

                confirm_delete = st.checkbox("I confirm I want to delete this group", key=f"confirm_checkbox_{editing_group_id}")

                col_confirm1, col_confirm2 = st.columns(2)
                with col_confirm1:
                    if st.button("✅ Yes, Delete Group", type="primary", use_container_width=True):
                        if confirm_delete:
                            try:
                                groups = load_groups()
                                group_name = groups[editing_group_id].get('name', 'Unknown')

                                # Delete the group
                                del groups[editing_group_id]
                                save_groups(groups)

                                # Clear all related state
                                st.session_state.temp_members = []
                                if "editing_group" in st.session_state:
                                    del st.session_state.editing_group
                                st.session_state.current_page = "research_groups"
                                st.session_state.page_changed = True

                                # Clear delete confirmation states
                                st.session_state[delete_confirm_key] = False
                                confirm_checkbox_key = f"confirm_checkbox_{editing_group_id}"
                                if confirm_checkbox_key in st.session_state:
                                    del st.session_state[confirm_checkbox_key]

                                st.success(f"Group '{group_name}' deleted successfully!")
                                st.rerun()
                            except KeyError:
                                st.error("Group not found. It may have already been deleted.")
                                st.session_state[delete_confirm_key] = False
                            except Exception as e:
                                st.error(f"Error deleting group: {str(e)}")
                                st.session_state[delete_confirm_key] = False
                        else:
                            st.warning("Please check the confirmation box to proceed with deletion.")

                with col_confirm2:
                    if st.button("❌ Cancel", key="cancel_delete", type="secondary", use_container_width=True):
                        # Reset confirmation state
                        st.session_state[delete_confirm_key] = False
                        st.rerun()

def render_generate_report_page():
    """Render the generate report page"""

    # Back button
    if st.button("← Back to Groups", key="back_to_groups_generate", type="secondary"):
        st.session_state.current_page = "research_groups"
        st.session_state.page_changed = True
        st.rerun()

    # Page header with enhanced styling
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">📊 Generate Achievement Report</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Create comprehensive reports for your research groups
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Load groups
    groups = load_groups()

    if not groups:
        st.warning("No research groups available. Please create a group first.")
        if st.button("Create Group", key="create_group_fallback"):
            st.session_state.current_page = "edit_group"
            st.session_state.page_changed = True
            st.rerun()
        return

    # Check if we have a pre-selected group from the group card
    selected_group = st.session_state.get("selected_group")

    # If no pre-selected group, show selection dropdown with enhanced styling
    if not selected_group or selected_group not in groups:
        st.markdown("#### 🎯 Select Research Group")
        selected_group = st.selectbox(
            "Choose a group to generate report for:",
            options=list(groups.keys()),
            format_func=lambda x: f"{groups[x]['name']} ({len(groups[x]['members'])} members)",
            key="report_group_select",
            help="Select the research group you want to generate an achievement report for"
        )

        # Show preview of selected group if available
        if selected_group and selected_group in groups:
            preview_group = groups[selected_group]
            st.info(f"📊 **{preview_group['name']}** - {len(preview_group['members'])} members\n\n{preview_group['description']}")
    else:
        st.markdown("#### 🎯 Selected Group")
        st.info(f"📊 **{groups[selected_group]['name']}** - {len(groups[selected_group]['members'])} members")
    
    if selected_group:
        selected_group_data = groups[selected_group]
        
        # Display selected group info
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {selected_group_data['color']}15 0%, {selected_group_data['color']}05 100%);
            border: 2px solid {selected_group_data['color']};
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1rem 0;
        ">
            <h4 style="margin: 0 0 1rem 0; color: {selected_group_data['color']};">{selected_group_data['name']}</h4>
            <p style="margin: 0 0 1rem 0;">{selected_group_data['description']}</p>
            <p style="margin: 0;"><strong>Members:</strong> {len(selected_group_data['members'])}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Report configuration with enhanced styling
        st.markdown("#### ⚙️ Report Configuration")

        # Configuration cards
        config_col1, config_col2 = st.columns(2)

        with config_col1:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
                border: 2px solid #4facfe;
                border-radius: 12px;
                padding: 1.5rem;
                margin: 0.5rem 0;
            ">
                <h4 style="color: #1976d2; margin-top: 0;">📋 Report Type</h4>
            """, unsafe_allow_html=True)

            report_type = st.selectbox(
                "Choose report focus:",
                ["Full report", "Recent achievements", "Publication stats", "Collaboration network"],
                key="report_type_select",
                help="Select the type of analysis you want in the report"
            )

            st.markdown("</div>", unsafe_allow_html=True)

        with config_col2:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #fff0f6 0%, #fce7f3 100%);
                border: 2px solid #f5576c;
                border-radius: 12px;
                padding: 1.5rem;
                margin: 0.5rem 0;
            ">
                <h4 style="color: #d32f2f; margin-top: 0;">⏰ Time Range</h4>
            """, unsafe_allow_html=True)

            time_range = st.selectbox(
                "Select time period:",
                ["Last 6 months", "Last year", "Last 2 years", "All time"],
                key="time_range_select",
                help="Choose the time period for the analysis"
            )

            st.markdown("</div>", unsafe_allow_html=True)

        # Optional query input
        st.markdown("---")
        st.markdown("#### 🔍 Optional Query (Advanced)")
        
        custom_query = st.text_area(
            "Custom analysis query (optional):",
            placeholder="e.g., Focus on recent publications and collaborations, exclude older achievements",
            height=100,
            help="Provide specific instructions for achievement analysis (optional)"
        )

        # Configuration summary
        st.markdown("---")
        st.markdown("### 📋 Configuration Summary")
        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:
            st.info(f"**Report Type:** {report_type}")
            st.info(f"**Custom Query:** {'Yes' if custom_query.strip() else 'No'}")
        with summary_col2:
            st.info(f"**Time Range:** {time_range}")
            st.info(f"**Members:** {len(selected_group_data['members'])}")
        
        # Additional options
        st.markdown("---")
        st.markdown("### 🚀 Generation Options")

        options_col1, options_col2 = st.columns(2)

        with options_col1:
            include_detailed_analysis = st.checkbox(
                "Include detailed member analysis",
                value=True,
                help="Generate individual analysis for each group member"
            )

        with options_col2:
            save_to_history = st.checkbox(
                "Save to report history",
                value=True,
                help="Store this report for future reference"
            )

        # Preview section
        with st.expander("👀 Preview Configuration", expanded=False):
            st.markdown("**Report Summary:**")
            st.info(f"""
            **Group:** {selected_group_data['name']}
            **Members:** {len(selected_group_data['members'])}
            **Type:** {report_type}
            **Time Range:** {time_range}
            **Custom Query:** {'Yes' if custom_query.strip() else 'No'}
            **Detailed Analysis:** {'Yes' if include_detailed_analysis else 'No'}
            **Save to History:** {'Yes' if save_to_history else 'No'}
            """)


        if st.button("🚀 Generate Group Report", key="generate_group_report", type="primary", use_container_width=True):
            # Check if OpenAI API key is set
            if not st.session_state.get("openai_api_key"):
                st.error("⚠️ **OpenAI API Key Required**")
                st.info("Please enter your OpenAI API key in the sidebar settings (🛠️ Settings → API Configuration) to use the AI-powered report generation features.")
                st.stop()
            
            with st.spinner("🔄 Generating achievement report..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # NOTE this is temp for
                    if backend_available == 0:
                        # Generate reports for each member
                        all_reports = []
                        for i, member in enumerate(selected_group_data['members']):
                            status_text.text(f"📊 Generating report for {member['name']}... ({i+1}/{len(selected_group_data['members'])})")
                            progress_bar.progress((i + 1) / len(selected_group_data['members']))
                            
                            # Call backend function
                            member_report = build_achievement_report(member['name'])
                            all_reports.append({
                                'name': member['name'],
                                'homepage': member['homepage'],
                                'affiliation': member['affiliation'],
                                'report': member_report
                            })
                        
                        # Store results
                        report_id = f"{selected_group}_{int(time.time())}"
                        new_report = {
                            'id': report_id,
                            'group_id': selected_group,
                            'group_name': selected_group_data['name'],
                            'members': all_reports,
                            'report_type': report_type,
                            'time_range': time_range,
                            'custom_query': custom_query,
                            'created_at': time.time()
                        }

                        # Initialize reports storage if not exists
                        if "stored_reports" not in st.session_state:
                            st.session_state.stored_reports = {}

                        # Store the report
                        st.session_state.stored_reports[report_id] = new_report

                        # Set current report for viewing and jump to view page
                        st.session_state.current_view_report = new_report
                        st.session_state.current_page = "view_single_report"
                        st.session_state.page_changed = True
                        
                        status_text.text("✅ Report generation complete!")
                        progress_bar.progress(100)
                        st.rerun()
                    else:
                        # Demo mode - use demo data from JSON file
                        try:
                            import json
                            import os
                            
                            # Try to load demo data
                            demo_file_path = os.path.join(os.path.dirname(__file__), "..", "backend", "demo_achievement_report_brief.json")
                            if os.path.exists(demo_file_path):
                                with open(demo_file_path, 'r', encoding='utf-8') as f:
                                    demo_data = json.load(f)
                            else:
                                # Fallback demo data if file not found
                                demo_data = [
                                    {
                                        "name": "Jiarui Ji",
                                        "homepage": "https://ji-cather.github.io/homepage/",
                                        "affiliation": "Gaoling School of AI, Renmin University of China (M.E.); Incoming Ph.D. (Sep 2025)",
                                        "focus": ["LLM-based Agents", "Social Simulation", "Graph Generation"],
                                        "summary": "Works on LLM multi-agent systems and dynamic/text-attributed graph generation, aiming to bridge agent interaction dynamics with scalable graph generative modeling. Early publications at ACL Findings 2025 and EMNLP Findings 2024 demonstrate a strong trajectory, with ongoing work extending to dynamic TAG prediction and benchmarking.",
                                        "highlights": [
                                            "ACL-Findings 2025: LLM multi-agent systems as scalable graph generative models",
                                            "EMNLP-Findings 2024: Scarce resource allocation via LLM-based agents"
                                        ]
                                    },
                                    {
                                        "name": "Xinyi Mou",
                                        "homepage": "https://xymou.github.io/",
                                        "affiliation": "Fudan University (DISC Lab), Ph.D. student",
                                        "focus": ["LLM-driven Social Simulation", "Computational Social Science", "Key Figure Modeling"],
                                        "summary": "Researches LLM agents for social simulation and socio-political analysis, emphasizing communication protocols, benchmarking, and large-scale societal modeling. Outputs span EMNLP/NAACL/ACL-Findings and TIST, reflecting both methodological contributions (e.g., EcoLANG, AgentSense) and applied studies in media and political domains.",
                                        "highlights": [
                                            "EMNLP-Findings 2025: EcoLANG for agent communication",
                                            "NAACL 2025: AgentSense benchmarking social intelligence"
                                        ]
                                    },
                                    {
                                        "name": "Zengqing Wu",
                                        "homepage": "https://wuzengqing001225.github.io/",
                                        "affiliation": "Kyoto University (M.Eng.); Research Associate, Osaka University",
                                        "focus": ["Agent-Based Modeling with LLMs", "Computational Social Science"],
                                        "summary": "Studies emergent behaviors in LLM-agent systems and develops simulations for complex social phenomena, including urban mobility generation. Publications at EMNLP 2024 and NeurIPS 2024, plus service at major venues, underscore a growing profile in agent-based modeling and empirical LLM evaluation.",
                                        "highlights": [
                                            "EMNLP 2024 Findings: Spontaneous cooperation of competing LLM agents",
                                            "NeurIPS 2024: LLM agents for personal mobility generation"
                                        ]
                                    },
                                    {
                                        "name": "Jinsook Lee",
                                        "homepage": "https://jinsook-jennie-lee.github.io/",
                                        "affiliation": "Cornell University, Ph.D. candidate (Information Science)",
                                        "focus": ["AI in Education", "Evaluation & Fairness", "Computational Social Science"],
                                        "summary": "Focuses on evaluating AI in high-stakes educational contexts, analyzing policy impacts and bias while comparing human and LLM-generated texts. Work at EAAMO and BJET highlights evidence-driven insights for admissions and learning analytics, complemented by cross-disciplinary collaborations.",
                                        "highlights": [
                                            "EAAMO 2024: Impact of ending affirmative action on diversity/merit",
                                            "BJET 2024: Life cycle of LLMs in education and bias"
                                        ]
                                    }
                                ]
                            
                            # Convert demo data to report format
                            demo_reports = []
                            for member in demo_data:
                                # Create formatted report with highlights and summary (without duplicate name/affiliation)
                                formatted_report = f"""### 🎯 Research Focus
{chr(10).join([f"- {focus}" for focus in member['focus']])}

### 🏆 Key Highlights
{chr(10).join([f"- {highlight}" for highlight in member['highlights']])}

### 📝 Summary
{member['summary']}

### 🔗 Profile
- **Homepage:** [{member['name']}'s Homepage]({member['homepage']})
- **Research Areas:** {', '.join(member['focus'])}
- **Notable Publications:** {len(member['highlights'])} recent papers"""
                                
                                demo_reports.append({
                                    'name': member['name'],
                                    'homepage': member['homepage'],
                                    'affiliation': member['affiliation'],
                                    'report': formatted_report
                                })
                            
                            # Store demo report
                            report_id = f"demo_星桥计划_{int(time.time())}"
                            demo_report = {
                                'id': report_id,
                                'group_id': 'demo_group',
                                'group_name': '星桥计划 (Demo)',
                                'members': demo_reports,
                                'report_type': 'Demo Report',
                                'time_range': 'Demo Data',
                                'custom_query': 'Demo achievement report using pre-loaded researcher data',
                                'created_at': time.time()
                            }

                            # Initialize reports storage if not exists
                            if "stored_reports" not in st.session_state:
                                st.session_state.stored_reports = {}

                            # Store the demo report
                            st.session_state.stored_reports[report_id] = demo_report

                            # Set current report for viewing and jump to view page
                            st.session_state.current_view_report = demo_report
                            st.session_state.current_page = "view_single_report"
                            st.session_state.page_changed = True
                            
                            status_text.text("✅ Demo report generation complete!")
                            progress_bar.progress(100)
                            st.success("🎉 Demo report generated successfully!")
                            st.info("Redirecting to report view...")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as demo_e:
                            st.error(f"Error generating demo report: {demo_e}")
                            st.info("Falling back to mock data...")
                            
                            # Fallback to mock data
                            for i in range(len(selected_group_data['members'])):
                                progress_bar.progress((i + 1) / len(selected_group_data['members']))
                                status_text.text(f"📊 Generating report for {selected_group_data['members'][i]['name']}... ({i+1}/{len(selected_group_data['members'])})")
                                time.sleep(0.5)
                            
                            # Create mock reports
                            mock_reports = []
                            for member in selected_group_data['members']:
                                mock_reports.append({
                                    'name': member['name'],
                                    'homepage': member['homepage'],
                                    'affiliation': member['affiliation'],
                                    'report': f"**Mock Report for {member['name']}**\n\nThis is a sample achievement report showing publications, research focus, and notable contributions in the field of AI and machine learning.\n\n### Recent Publications\n- Paper 1: Title of the paper (2024)\n- Paper 2: Another important paper (2023)\n\n### Research Focus\n- Machine Learning\n- Natural Language Processing\n- Computer Vision\n\n### Notable Achievements\n- Best Paper Award at Conference X\n- Outstanding Student Award\n- Multiple top-tier publications"
                                })

                            # Store results
                            report_id = f"{selected_group}_{int(time.time())}"
                            new_report = {
                                'id': report_id,
                                'group_id': selected_group,
                                'group_name': selected_group_data['name'],
                                'members': mock_reports,
                                'report_type': report_type,
                                'time_range': time_range,
                                'custom_query': custom_query,
                                'created_at': time.time()
                            }

                            # Initialize reports storage if not exists
                            if "stored_reports" not in st.session_state:
                                st.session_state.stored_reports = {}

                            # Store the report
                            st.session_state.stored_reports[report_id] = new_report

                            # Set current report for viewing and jump to view page
                            st.session_state.current_view_report = new_report
                            st.session_state.current_page = "view_single_report"
                            st.session_state.page_changed = True
                            
                            status_text.text("✅ Report generation complete!")
                            progress_bar.progress(100)
                            time.sleep(0.5)
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"Error during report generation: {e}")
                    progress_bar.empty()
                    status_text.empty()

def render_view_reports_page():
    """Render the view reports page"""

        # Back button
    if st.button("← Back to Groups", key="back_to_groups_view", type="secondary"):
        st.session_state.current_page = "research_groups"
        st.session_state.page_changed = True
        st.rerun()

    # Page header with enhanced styling
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">📋 Existing Reports</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Browse and manage all your generated achievement reports
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Get stored reports
    stored_reports = st.session_state.get("stored_reports", {})

    if not stored_reports:
        st.info("🔍 No reports available. Generate some reports first using the 'Generate Report' button on group cards.")
        if st.button("Go to Groups", key="goto_groups_view_reports"):
            st.session_state.current_page = "research_groups"
            st.session_state.page_changed = True
            st.rerun()
        return

    # Statistics and filters
    st.markdown("### 📈 Report Statistics")

    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)

    with stats_col1:
        st.metric("Total Reports", len(stored_reports))

    with stats_col2:
        unique_groups = len(set(report['group_id'] for report in stored_reports.values()))
        st.metric("Unique Groups", unique_groups)

    with stats_col3:
        total_members = sum(len(report['members']) for report in stored_reports.values())
        st.metric("Total Members", total_members)

    with stats_col4:
        if stored_reports:
            latest_report = max(stored_reports.values(), key=lambda x: x.get('created_at', 0))
            latest_time = time.strftime('%m/%d', time.localtime(latest_report.get('created_at', time.time())))
            st.metric("Latest Report", latest_time)
        else:
            st.metric("Latest Report", "N/A")

    # Search and filter options
    st.markdown("---")
    st.markdown("### 🔍 Search & Filter")

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        search_term = st.text_input(
            "Search reports:",
            placeholder="Enter group name...",
            key="report_search",
            help="Search for reports by group name"
        )

    with filter_col2:
        sort_options = ["Newest first", "Oldest first", "Group name A-Z", "Group name Z-A"]
        sort_by = st.selectbox("Sort by:", sort_options, key="report_sort")

    # Apply search and sorting
    filtered_reports = stored_reports.values()

    if search_term:
        filtered_reports = [
            report for report in filtered_reports
            if search_term.lower() in report['group_name'].lower()
        ]

    # Apply sorting
    if sort_by == "Newest first":
        sorted_reports = sorted(filtered_reports, key=lambda x: x.get('created_at', 0), reverse=True)
    elif sort_by == "Oldest first":
        sorted_reports = sorted(filtered_reports, key=lambda x: x.get('created_at', 0))
    elif sort_by == "Group name A-Z":
        sorted_reports = sorted(filtered_reports, key=lambda x: x['group_name'].lower())
    elif sort_by == "Group name Z-A":
        sorted_reports = sorted(filtered_reports, key=lambda x: x['group_name'].lower(), reverse=True)

    # Display results
    st.markdown("---")
    if search_term or sort_by != "Newest first":
        st.markdown(f"#### 📊 Available Reports ({len(sorted_reports)} found)")
    else:
        st.markdown("#### 📊 Available Reports")

    if not sorted_reports:
        st.info("🔍 No reports match your search criteria. Try adjusting your filters.")

    for report in sorted_reports:
        # Enhanced report card with more information
        created_time = time.localtime(report.get('created_at', time.time()))
        time_ago = time.time() - report.get('created_at', time.time())

        # Calculate time ago
        if time_ago < 3600:  # Less than 1 hour
            time_ago_text = f"{int(time_ago // 60)} minutes ago"
        elif time_ago < 86400:  # Less than 1 day
            time_ago_text = f"{int(time_ago // 3600)} hours ago"
        elif time_ago < 604800:  # Less than 1 week
            time_ago_text = f"{int(time_ago // 86400)} days ago"
        else:
            time_ago_text = time.strftime('%Y-%m-%d', created_time)

        # Get report type icon
        report_type_icons = {
            "Full report": "📊",
            "Recent achievements": "🏆",
            "Publication stats": "📚",
            "Collaboration network": "🤝",
            "Demo Report": "🎯"
        }
        type_icon = report_type_icons.get(report['report_type'], "📋")

        card_html = textwrap.dedent(f"""
<div style="
    background: linear-gradient(135deg, #667eea15 0%, #764ba205 100%);
    border: 2px solid #667eea;
    border-radius: 15px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
        <div style="flex: 1;">
            <h4 style="margin: 0 0 0.5rem 0; color: #667eea; font-size: 1.4rem; font-weight: 600;">
                {report['group_name']}
            </h4>
            <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                <span style="
                    background: #667eea;
                    color: white;
                    padding: 0.3rem 0.8rem;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: bold;
                ">
                    👥 {len(report['members'])} members
                </span>
                <span style="
                    background: #4facfe;
                    color: white;
                    padding: 0.3rem 0.8rem;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 500;
                ">
                    {type_icon} {report['report_type']}
                </span>
                <span style="
                    background: #00f2fe;
                    color: white;
                    padding: 0.3rem 0.8rem;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 500;
                ">
                    ⏰ {report['time_range']}
                </span>
            </div>
        </div>
    </div>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e1e5e9;">
        <div style="color: #666; font-size: 0.85rem;">
            <strong>Created:</strong> {time.strftime('%Y-%m-%d %H:%M', created_time)} ({time_ago_text})
        </div>
        <div style="color: #888; font-size: 0.8rem;">
            Report ID: {report['id'][:8]}...
        </div>
    </div>
</div>
        """)
        st.markdown(card_html, unsafe_allow_html=True)

        # Action buttons for each report
        col_view, col_delete = st.columns(2)

        with col_view:
            if st.button("👁️ View Report", key=f"view_{report['id']}", use_container_width=True):
                # Set current report for viewing
                st.session_state.current_view_report = report
                st.session_state.current_page = "view_single_report"
                st.session_state.page_changed = True
                st.rerun()

        with col_delete:
            if st.button("🗑️ Delete", key=f"delete_{report['id']}", use_container_width=True):
                # Confirm deletion
                if st.checkbox(f"Confirm delete '{report['group_name']}' report?", key=f"confirm_{report['id']}"):
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{report['id']}", type="secondary"):
                        # Delete the report
                        del st.session_state.stored_reports[report['id']]
                        st.success(f"Report '{report['group_name']}' deleted successfully!")
                        # Stay on the same page but refresh the list
                        st.rerun()

def render_view_single_report_page():
    """Render the single report view page"""

    # Back button
    if st.button("← Back to Reports", key="back_to_reports_single", type="secondary"):
        st.session_state.current_page = "view_reports"
        st.session_state.page_changed = True
        st.rerun()

    # Get the current report to view
    report_data = st.session_state.get("current_view_report")

    if not report_data:
        st.error("No report selected.")
        if st.button("Go to Reports", key="goto_reports_single"):
            st.session_state.current_page = "view_reports"
            st.session_state.page_changed = True
            st.rerun()
        return

    # Enhanced report header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">📊 {report_data['group_name']}</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">
            Achievement Report • {len(report_data['members'])} Members
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Report metadata with enhanced styling
    st.markdown("### 📋 Report Overview")

    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)

    with meta_col1:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">👥</div>
            <div style="font-size: 1.5rem; font-weight: bold;">{}</div>
            <div style="font-size: 0.9rem; opacity: 0.9;">Members</div>
        </div>
        """.format(len(report_data['members'])), unsafe_allow_html=True)

    with meta_col2:
        report_type_icons = {
            "Full report": "📊",
            "Recent achievements": "🏆",
            "Publication stats": "📚",
            "Collaboration network": "🤝",
            "Demo Report": "🎯"
        }
        type_icon = report_type_icons.get(report_data['report_type'], "📋")
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">{}</div>
            <div style="font-size: 0.9rem; font-weight: bold;">{}</div>
            <div style="font-size: 0.8rem; opacity: 0.9;">Report Type</div>
        </div>
        """.format(type_icon, report_data['report_type']), unsafe_allow_html=True)

    with meta_col3:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏰</div>
            <div style="font-size: 0.9rem; font-weight: bold;">{}</div>
            <div style="font-size: 0.8rem; opacity: 0.9;">Time Range</div>
        </div>
        """.format(report_data['time_range']), unsafe_allow_html=True)

    with meta_col4:
        created_time = time.localtime(report_data.get('created_at', time.time()))
        formatted_time = time.strftime('%m/%d %H:%M', created_time)
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(78, 205, 196, 0.3);
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">📅</div>
            <div style="font-size: 0.9rem; font-weight: bold;">{}</div>
            <div style="font-size: 0.8rem; opacity: 0.9;">Created</div>
        </div>
        """.format(formatted_time), unsafe_allow_html=True)

    # Member navigation and summary
    st.markdown("---")
    st.markdown("### 👥 Member Reports")

    # Quick navigation
    member_names = [f"#{i+1} {member['name']}" for i, member in enumerate(report_data['members'])]
    selected_member = st.selectbox(
        "Quick jump to member:",
        ["Select a member..."] + member_names,
        key="member_navigator",
        help="Quickly navigate to a specific member's report"
    )

    # Display individual reports
    for i, member_report in enumerate(report_data['members'], 1):
        with st.expander(f"#{i} {member_report['name']}", expanded=True):
            # Member header
            col_name, col_links = st.columns([2, 1])
            with col_name:
                st.markdown(f"### {member_report['name']}")
                if member_report['affiliation']:
                    st.markdown(f"**Affiliation:** {member_report['affiliation']}")

            with col_links:
                if member_report['homepage']:
                    st.markdown(f"[🔗 Homepage]({member_report['homepage']})")

            # Report content
            st.markdown(member_report['report'])

    # Export options
    st.markdown("---")
    st.markdown("### 📤 Export Options")

    col_export1, col_export2 = st.columns(2)

    with col_export1:
        if st.button("📊 Export as CSV", key="export_csv_single", type="secondary", use_container_width=True):
            # Convert to DataFrame for CSV export
            df_data = []
            for member_report in report_data['members']:
                df_data.append({
                    'Name': member_report['name'],
                    'Affiliation': member_report['affiliation'],
                    'Homepage': member_report['homepage'],
                    'Report Type': report_data['report_type'],
                    'Time Range': report_data['time_range']
                })

            df = pd.DataFrame(df_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name=f"{report_data['group_name']}_achievement_report.csv",
                mime="text/csv",
                use_container_width=True
            )

    with col_export2:
        if st.button("📋 Export as JSON", key="export_json_single", type="secondary", use_container_width=True):
            json_data = json.dumps(report_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Download JSON",
                data=json_data,
                file_name=f"{report_data['group_name']}_achievement_report.json",
                mime="application/json",
                use_container_width=True
            )

def render_achievement_report_page():
    """Main function to render the achievement report page with navigation"""

    # Initialize current page if not set
    if "current_page" not in st.session_state:
        st.session_state.current_page = "research_groups"



    # Clear any stale state when entering the page
    if "temp_members" in st.session_state and st.session_state.current_page != "edit_group":
        del st.session_state.temp_members

    # Check if page was changed and clear any cached state
    if st.session_state.get('page_changed', False):
        st.session_state.page_changed = False
        # Force a clean state for the new page
        if "temp_members" in st.session_state and st.session_state.current_page != "edit_group":
            del st.session_state.temp_members

    # Get current page and use exact matching
    current_page = st.session_state.get('current_page', '')
    
    # Use exact string matching for pages
    if current_page == "research_groups":
        target_page = "research_groups"
    elif current_page == "edit_group":
        target_page = "edit_group"
    elif current_page == "generate_report":
        target_page = "generate_report"
    elif current_page == "view_reports":
        target_page = "view_reports"
    elif current_page == "view_single_report":
        target_page = "view_single_report"
    else:
        # For main navigation pages, map them to sub-pages
        if current_page == "📊 Achievement Report":
            target_page = "research_groups"
            st.session_state.current_page = "research_groups"
        else:
            # Fallback: reset to research groups page
            st.session_state.current_page = "research_groups"
            target_page = "research_groups"

    # Navigation logic with proper state management
    if target_page == "research_groups":
        render_research_groups_page()
    elif target_page == "edit_group":
        render_edit_group_page()
    elif target_page == "generate_report":
        render_generate_report_page()
    elif target_page == "view_reports":
        render_view_reports_page()
    elif target_page == "view_single_report":
        render_view_single_report_page()
    else:
        # Fallback: reset to research groups page
        st.session_state.current_page = "research_groups"
        render_research_groups_page()

def apply_achievement_report_styles():
    """Apply custom CSS for achievement report page"""
    # Temporarily disabled all custom styles to test button visibility
    pass
