import streamlit as st
import json
import pandas as pd
import time

# Default groups data
DEFAULT_GROUPS = {
    "ai_news": {
        "name": "AI 新闻媒体",
        "sources": [
            {"name": "量子位", "url": "https://www.qbitai.com/", "type": "news", "description": "AI科技媒体"},
            {"name": "新智源", "url": "https://link.baai.ac.cn/@AI_era", "type": "news", "description": "AI时代资讯"}
        ],
        "description": "主流AI新闻媒体和资讯平台",
        "color": "#667eea"
    },
    "tech_platforms": {
        "name": "科技平台",
        "sources": [
            {"name": "36氪", "url": "https://36kr.com/", "type": "platform", "description": "科技创投媒体"},
            {"name": "虎嗅", "url": "https://www.huxiu.com/", "type": "platform", "description": "商业科技媒体"},
            {"name": "钛媒体", "url": "https://www.tmtpost.com/", "type": "platform", "description": "TMT科技媒体"}
        ],
        "description": "主流科技创投和商业媒体平台",
        "color": "#764ba2"
    },
    "research_institutes": {
        "name": "研究机构",
        "sources": [
            {"name": "MSRA", "url": "https://www.microsoft.com/en-us/research/lab/microsoft-research-asia/", "type": "institute", "description": "微软亚洲研究院"},
            {"name": "OpenAI", "url": "https://openai.com/", "type": "institute", "description": "OpenAI研究机构"},
            {"name": "DeepMind", "url": "https://deepmind.com/", "type": "institute", "description": "DeepMind AI研究"}
        ],
        "description": "AI领域重要研究机构",
        "color": "#4facfe"
    },
    "social_media": {
        "name": "社交媒体",
        "sources": [
            {"name": "Twitter AI", "url": "https://twitter.com/search?q=AI&src=typed_query", "type": "social", "description": "Twitter AI话题"},
            {"name": "LinkedIn AI", "url": "https://www.linkedin.com/search/results/content/?keywords=AI", "type": "social", "description": "LinkedIn AI内容"},
            {"name": "知乎AI", "url": "https://www.zhihu.com/topic/19552832", "type": "social", "description": "知乎AI话题讨论"}
        ],
        "description": "社交媒体AI话题和讨论",
        "color": "#00f2fe"
    }
}

def load_groups():
    if "trend_groups" not in st.session_state:
        st.session_state.trend_groups = DEFAULT_GROUPS.copy()
    return st.session_state.trend_groups

def save_groups(groups):
    st.session_state.trend_groups = groups

def render_trend_groups_page():
    """Render the main trend groups page"""
    
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
        <h1 style="margin: 0; font-size: 2.5rem;">📈 Trend Radar</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Monitor AI trends across multiple sources and platforms
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons row
    col_actions1, col_actions2 = st.columns(2)

    with col_actions1:
        if st.button("➕ Create New Group", key="create_new_trend_group", type="primary", use_container_width=True):
            st.session_state.current_page = "edit_trend_group"
            st.session_state.editing_group = None
            # Force clear any cached state and rerun
            st.session_state.page_changed = True
            st.rerun()

    with col_actions2:
        if st.button("📋 View Existing Reports", key="view_trend_reports", type="primary", use_container_width=True):
            st.session_state.current_page = "view_trend_reports"
            # Force clear any cached state and rerun
            st.session_state.page_changed = True
            st.rerun()

    st.markdown("---")

    # Load and display groups
    groups = load_groups()
    
    # Groups grid layout
    st.markdown("### 🎯 Trend Groups")
    
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
                        {len(group_data['sources'])} sources
                    </div>
                </div>
                <p style="margin: 0 0 1rem 0; color: #666; font-size: 0.9rem;">{group_data['description']}</p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem;">
            """, unsafe_allow_html=True)
            
            # Show first 3 sources as preview
            for source in group_data['sources'][:3]:
                st.markdown(f"""
                <div style="
                    background: {group_data['color']}20;
                    border: 1px solid {group_data['color']}40;
                    padding: 0.3rem 0.6rem;
                    border-radius: 12px;
                    font-size: 0.8rem;
                    color: {group_data['color']};
                ">
                    {source['name']}
                </div>
                """, unsafe_allow_html=True)
            
            if len(group_data['sources']) > 3:
                st.markdown(f"""
                <div style="
                    background: {group_data['color']}20;
                    border: 1px solid {group_data['color']}40;
                    padding: 0.3rem 0.6rem;
                    border-radius: 12px;
                    font-size: 0.8rem;
                    color: {group_data['color']};
                ">
                    +{len(group_data['sources']) - 3} more
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div></div>", unsafe_allow_html=True)
            
            # Action buttons for each group
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✏️ Edit", key=f"edit_{group_id}", use_container_width=True):
                    st.session_state.current_page = "edit_trend_group"
                    st.session_state.editing_group = group_id
                    st.rerun()

            with col_btn2:
                if st.button("📊 Generate Report", key=f"report_{group_id}", use_container_width=True):
                    st.session_state.current_page = "generate_trend_report"
                    st.session_state.selected_group = group_id
                    # Force clear any cached state and rerun
                    st.session_state.page_changed = True
                    st.rerun()

def render_edit_trend_group_page():
    """Render the edit trend group page"""

    # Back button
    if st.button("← Back to Groups", key="back_to_groups_edit", type="secondary"):
        st.session_state.current_page = "trend_groups"
        st.session_state.page_changed = True
        st.rerun()

    # Page header
    is_edit = st.session_state.get('editing_group') is not None
    if is_edit:
        st.markdown("### ✏️ Edit Trend Group")
    else:
        st.markdown("### ➕ Create New Trend Group")
    
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
            'sources': []
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
    
    # Sources management
    st.markdown("#### 🔗 Group Sources")
    
    if "temp_sources" not in st.session_state:
        st.session_state.temp_sources = group_data.get('sources', []).copy()
    
    # Display existing sources
    if st.session_state.temp_sources:
        # Add headers for source input fields
        col_header1, col_header2, col_header3, col_header4, col_header5 = st.columns([2, 3, 2, 2, 1])
        with col_header1:
            st.markdown("**🔗 Name**")
        with col_header2:
            st.markdown("**🌐 URL**")
        with col_header3:
            st.markdown("**📊 Type**")
        with col_header4:
            st.markdown("**📝 Description**")
        with col_header5:
            st.markdown("**Action**")

        st.markdown("---")

    for i, source in enumerate(st.session_state.temp_sources):
        st.markdown(f"**Source {i+1}:**")
        col_source1, col_source2, col_source3, col_source4, col_source5 = st.columns([2, 3, 2, 2, 1])

        with col_source1:
            source_name = st.text_input("Name", value=source.get('name', ''),
                                      key=f"source_name_{i}", label_visibility="collapsed",
                                      placeholder="e.g., 量子位")
        with col_source2:
            source_url = st.text_input("URL", value=source.get('url', ''),
                                     key=f"source_url_{i}", label_visibility="collapsed",
                                     placeholder="https://example.com")
        with col_source3:
            source_type = st.selectbox("Type", ["news", "platform", "institute", "social", "other"], 
                                     index=["news", "platform", "institute", "social", "other"].index(source.get('type', 'news')) if source.get('type') in ["news", "platform", "institute", "social", "other"] else 0,
                                     key=f"source_type_{i}", label_visibility="collapsed")
        with col_source4:
            source_description = st.text_input("Description", value=source.get('description', ''),
                                            key=f"source_description_{i}", label_visibility="collapsed",
                                            placeholder="Brief description")
        with col_source5:
            if st.button("🗑️", key=f"remove_source_{i}", help="Remove source"):
                st.session_state.temp_sources.pop(i)
                st.rerun()

        # Update source data
        st.session_state.temp_sources[i] = {
            'name': source_name,
            'url': source_url,
            'type': source_type,
            'description': source_description
        }
    
    # Add new source
    if st.button("➕ Add Source", key="add_source"):
        st.session_state.temp_sources.append({
            'name': '',
            'url': '',
            'type': 'news',
            'description': ''
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

            if not st.session_state.temp_sources:
                st.error("Group must have at least one source!")
                return

            # Create/update group
            groups = load_groups()
            if editing_group_id:
                groups[editing_group_id] = {
                    'name': group_name.strip(),
                    'description': group_description.strip(),
                    'color': selected_color,
                    'sources': [s for s in st.session_state.temp_sources if s['name'].strip() and s['url'].strip()]
                }
            else:
                # Generate new ID
                new_id = f"trend_group_{len(groups) + 1}"
                groups[new_id] = {
                    'name': group_name.strip(),
                    'description': group_description.strip(),
                    'color': selected_color,
                    'sources': [s for s in st.session_state.temp_sources if s['name'].strip() and s['url'].strip()]
                }

            save_groups(groups)
            st.session_state.temp_sources = []
            st.session_state.current_page = "trend_groups"
            st.session_state.page_changed = True
            st.rerun()

    with col_actions2:
        if st.button("❌ Cancel", key="cancel_edit", type="secondary", use_container_width=True):
            st.session_state.temp_sources = []
            st.session_state.current_page = "trend_groups"
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
                                st.session_state.temp_sources = []
                                if "editing_group" in st.session_state:
                                    del st.session_state.editing_group
                                st.session_state.current_page = "trend_groups"
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

def render_generate_trend_report_page():
    """Render the generate trend report page"""

    # Back button
    if st.button("← Back to Groups", key="back_to_groups_generate", type="secondary"):
        st.session_state.current_page = "trend_groups"
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
        <h1 style="margin: 0; font-size: 2.5rem;">📊 Generate Trend Report</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Monitor trends across multiple sources and generate comprehensive reports
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Demo notice
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
    ">
        <strong>🎯 Demo Mode:</strong> This is a demonstration with pre-loaded AI industry trend analysis content. 
        The reports will show real industry insights from 量子位 and 新智元 sources.
    </div>
    """, unsafe_allow_html=True)

    # Load groups
    groups = load_groups()

    if not groups:
        st.warning("No trend groups available. Please create a group first.")
        if st.button("Create Group", key="create_group_fallback"):
            st.session_state.current_page = "edit_trend_group"
            st.session_state.page_changed = True
            st.rerun()
        return

    # Check if we have a pre-selected group from the group card
    selected_group = st.session_state.get("selected_group")

    # If no pre-selected group, show selection dropdown with enhanced styling
    if not selected_group or selected_group not in groups:
        st.markdown("#### 🎯 Select Trend Group")
        selected_group = st.selectbox(
            "Choose a group to generate report for:",
            options=list(groups.keys()),
            format_func=lambda x: f"{groups[x]['name']} ({len(groups[x]['sources'])} sources)",
            key="report_group_select",
            help="Select the trend group you want to monitor and generate a report for"
        )

        # Show preview of selected group if available
        if selected_group and selected_group in groups:
            preview_group = groups[selected_group]
            st.info(f"📊 **{preview_group['name']}** - {len(preview_group['sources'])} sources\n\n{preview_group['description']}")
    else:
        st.markdown("#### 🎯 Selected Group")
        st.info(f"📊 **{groups[selected_group]['name']}** - {len(groups[selected_group]['sources'])} sources")
    
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
            <p style="margin: 0;"><strong>Sources:</strong> {len(selected_group_data['sources'])}</p>
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
                <h4 style="color: #1976d2; margin-top: 0;">⏰ Time Range</h4>
            """, unsafe_allow_html=True)

            time_range = st.selectbox(
                "Select time period:",
                ["Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Last year"],
                key="time_range_select",
                help="Choose the time period for trend monitoring"
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
                <h4 style="color: #d32f2f; margin-top: 0;">📊 Report Type</h4>
            """, unsafe_allow_html=True)

            report_type = st.selectbox(
                "Choose report focus:",
                ["Full trend analysis", "Hot topics only", "Source comparison", "Trend timeline"],
                key="report_type_select",
                help="Select the type of trend analysis you want in the report"
            )

            st.markdown("</div>", unsafe_allow_html=True)

        # Optional query input
        st.markdown("---")
        st.markdown("#### 🔍 Optional Query (Advanced)")
        
        custom_query = st.text_area(
            "Custom analysis query (optional):",
            placeholder="e.g., Focus on AI safety topics, exclude marketing content, prioritize technical discussions",
            height=100,
            help="Provide specific instructions for trend analysis (optional)"
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
            st.info(f"**Sources:** {len(selected_group_data['sources'])}")
        
        # Additional options
        st.markdown("---")
        st.markdown("### 🚀 Generation Options")

        options_col1, options_col2 = st.columns(2)

        with options_col1:
            include_source_analysis = st.checkbox(
                "Include source-by-source analysis",
                value=True,
                help="Generate individual analysis for each source in the group"
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
            **Sources:** {len(selected_group_data['sources'])}
            **Type:** {report_type}
            **Time Range:** {time_range}
            **Custom Query:** {'Yes' if custom_query.strip() else 'No'}
            **Source Analysis:** {'Yes' if include_source_analysis else 'No'}
            **Save to History:** {'Yes' if save_to_history else 'No'}
            """)

        # Generate report button with enhanced styling
        st.markdown("---")
        if st.button("🚀 Generate Trend Report", key="generate_trend_report", type="primary", use_container_width=True):
            # Check if OpenAI API key is set
            if not st.session_state.get("openai_api_key"):
                st.error("⚠️ **OpenAI API Key Required**")
                st.info("Please enter your OpenAI API key in the sidebar settings (🛠️ Settings → API Configuration) to use the AI-powered trend analysis features.")
                st.stop()
            
            with st.spinner("🔄 Generating trend report..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # Simulate trend analysis for each source
                    all_reports = []
                    for i, source in enumerate(selected_group_data['sources']):
                        status_text.text(f"📊 Analyzing trends from {source['name']}... ({i+1}/{len(selected_group_data['sources'])})")
                        progress_bar.progress((i + 1) / len(selected_group_data['sources']))
                        
                        # Simulate API call delay
                        time.sleep(0.5)
                        
                        # Create demo trend report for each source
                        if source['name'] == "量子位":
                            demo_trend_report = """## 量子位 | AI Coding & Parallel Agents

**Source Type:** News Media
**URL:** https://www.qbitai.com/

### 🚀 赛道概况
从硅谷到欧洲，AI Coding 融资与产品密度显著上升。形态从"补全"迁移到"从需求到 PR"的端到端交付；优秀的助手类产品开始内置/试水 Agent；低/零代码平台借助自然语言与场景驱动扩张创作者群体。基础大模型（Claude/Gemini/GPT 等）在 HumanEval/MBPP/SWE-Bench 持续刷榜，模型每次迭代都会"免费抬升"工具生态上限。

### 🏗️ 产品分层

#### **助手 → 代理化**
- 强调"自主拆解需求、多轮自动编码"
- 从被动辅助转为主动执行

#### **低代码**
- 关注"把更多人拉入开发"
- 而非替代专业开发者

#### **全生命周期**
- 要从一次性生成转向"规划—实现—测试—运维—留存"
- 依赖长期记忆与上下文复用

### 🤖 并行智能体（Andrew Ng）
多 Agent 并行是下一步性能与体验杠杆。典型路径包括：
- **测试时并行轨迹**（如 Code Monkeys）
- **Mixture-of-Agents**（Together MoA）

token 成本下降使并行更可行，难点在任务分解、编排与结果汇合。

### 🎯 落地要点（对开发/产品）

1. **以仓库/项目为边界的 Agent 编排**
   - 任务切分、并行执行、冲突/合并策略

2. **评测从"单次准确率"转向"质量 × 吞吐 × 预算"**

3. **将记忆、历史对话、Issue/PR 关联进入"可持续上下文"**

4. **低/零代码场景中优先做"场景模板 + 可视化管线"**
   - 让非专业者可复用

### 📊 关键指标
- **融资密度**: 显著上升
- **产品形态**: 端到端交付
- **模型性能**: 持续刷榜
- **生态上限**: 免费抬升"""
                        
                        elif source['name'] == "新智源":
                            demo_trend_report = """## 新智源 | 一周快讯脉络

**Source Type:** News Media
**URL:** https://link.baai.ac.cn/@AI_era

### 🔒 安全与治理
未成年人心理健康诉讼将加剧对对话式 AI 的年龄分级、风险提示与转介机制的监管要求。

### 🧪 Agent 进入科研流程
- **Agents4Science** 拟让 AI 以作者/评审/报告者身份参与
- "虚拟实验室"式协作提示可重复、可追溯的科研工作流将成新基建

### 💻 代码大模型竞逐
**xAI 推出 Grok Code Fast 1**（SWE-Bench 排名靠前），预示：
- IDE 集成
- 仓库级推理
- Agent API 将成入场门槛

### 🌐 平台多栈策略
**微软同日发布 MAI-Voice-1 / MAI-1-preview**：
- 语音与通用模型并进
- 指向"听—想—做"端到端链路的生态绑定

### 🎨 生成视觉前沿
**谷歌 nano banana** 聚焦：
- 多图融合
- 地理/建筑理解
- 2D→3D 与多轮"有记忆"创作
- 利好地图、设计、游戏资产到世界的自动生成

### 😊 情绪与舆情
Ilya 头像引发 AGI 情绪波动，更像市场情绪指标而非硬证据。

### 🧪 环境与评测
**Karpathy 强调 Environment Hub 的重要性**：
- 企业级 Agent 需要标准化任务 API
- 安全沙箱来做上岗前评测

### 📈 三条主线

1. **Agent 化纵深**
   - 科研/编码/企业流程全面渗透

2. **多模态与多栈平台合流**
   - 语音 + 通用
   - 视觉走向 3D 与长记忆

3. **安全与合规加压**
   - 青少年安全
   - 可追溯科研
   - 评测基准重塑

### 🎯 关键洞察
- **监管趋势**: 未成年人保护加强
- **技术融合**: 多模态平台整合
- **应用场景**: 科研流程AI化
- **安全要求**: 评测基准重塑"""
                        
                        else:
                            # For other sources, create a generic report
                            demo_trend_report = f"""## {source['name']} - Trend Analysis

**Source Type:** {source['type'].title()}
**URL:** {source['url']}

### 🔥 Hot Topics (Last {time_range.lower()})
- **AI Safety & Alignment**: 23% increase in mentions
- **Large Language Models**: 18% increase in discussions
- **Multimodal AI**: 15% increase in coverage
- **AI Regulation**: 12% increase in attention

### 📈 Trend Analysis
- **Positive Sentiment**: 67% of content
- **Neutral Sentiment**: 28% of content
- **Negative Sentiment**: 5% of content

### 🎯 Key Insights
- Growing focus on AI safety and responsible development
- Increased coverage of practical AI applications
- Rising interest in AI governance and policy discussions

### 📊 Engagement Metrics
- **Average Engagement**: 2.3K interactions per post
- **Peak Activity**: Tuesday-Thursday 10AM-2PM
- **Top Performing Content**: Technical tutorials and research updates"""
                        
                        all_reports.append({
                            'name': source['name'],
                            'url': source['url'],
                            'type': source['type'],
                            'description': source['description'],
                            'report': demo_trend_report
                        })
                    
                    # Store results
                    report_id = f"{selected_group}_{int(time.time())}"
                    new_report = {
                        'id': report_id,
                        'group_id': selected_group,
                        'group_name': selected_group_data['name'],
                        'sources': all_reports,
                        'report_type': report_type,
                        'time_range': time_range,
                        'custom_query': custom_query,
                        'created_at': time.time()
                    }

                    # Initialize reports storage if not exists
                    if "stored_trend_reports" not in st.session_state:
                        st.session_state.stored_trend_reports = {}

                    # Store the report
                    st.session_state.stored_trend_reports[report_id] = new_report

                    # Set current report for viewing and jump to view page
                    st.session_state.current_view_trend_report = new_report
                    st.session_state.current_page = "view_single_trend_report"
                    st.session_state.page_changed = True
                    
                    status_text.text("✅ Trend report generation complete!")
                    progress_bar.progress(100)
                    
                    # Show success message and redirect
                    st.success(f"🎉 Trend report generated successfully for {selected_group_data['name']}!")
                    st.info("Redirecting to report view...")
                
                    
                    # Force rerun to show the new page
                    time.sleep(1)  # Give user time to see the success message
                    st.rerun()
                        
                except Exception as e:
                    st.error(f"Error during trend report generation: {e}")
                    progress_bar.empty()
                    status_text.empty()

def render_view_trend_reports_page():
    """Render the view trend reports page"""

    # Back button
    if st.button("← Back to Groups", key="back_to_groups_view", type="secondary"):
        st.session_state.current_page = "trend_groups"
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
        <h1 style="margin: 0; font-size: 2.5rem;">📋 Existing Trend Reports</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Browse and manage all your generated trend reports
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Get stored reports
    stored_reports = st.session_state.get("stored_trend_reports", {})

    if not stored_reports:
        st.info("🔍 No trend reports available. Generate some reports first using the 'Generate Report' button on group cards.")
        if st.button("Go to Groups", key="goto_groups_view_reports"):
            st.session_state.current_page = "trend_groups"
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
        total_sources = sum(len(report['sources']) for report in stored_reports.values())
        st.metric("Total Sources", total_sources)

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
            key="trend_report_search",
            help="Search for reports by group name"
        )

    with filter_col2:
        sort_options = ["Newest first", "Oldest first", "Group name A-Z", "Group name Z-A"]
        sort_by = st.selectbox("Sort by:", sort_options, key="trend_report_sort")

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
            "Full trend analysis": "📊",
            "Hot topics only": "🔥",
            "Source comparison": "📈",
            "Trend timeline": "⏰"
        }
        type_icon = report_type_icons.get(report['report_type'], "📋")

        # # Create a native Streamlit version instead of HTML
        # st.markdown("### 📊 Report Card")
        
        # Use Streamlit containers and columns for layout
        with st.container():
            # Header section
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.markdown(f"#### {report['group_name']}")
            with col_header2:
                st.markdown(f"**{len(report['sources'])} sources**")
            
            # Tags section
            col_tags1, col_tags2, col_tags3 = st.columns(3)
            with col_tags1:
                st.markdown(f"""
                <div class="tag-purple">
                    🔗 {len(report['sources'])} sources
                </div>
                """, unsafe_allow_html=True)
            
            with col_tags2:
                st.markdown(f"""
                <div class="tag-blue">
                    {type_icon} {report['report_type']}
                </div>
                """, unsafe_allow_html=True)
            
            with col_tags3:
                st.markdown(f"""
                <div class="tag-cyan">
                    ⏰ {report['time_range']}
                </div>
                """, unsafe_allow_html=True)
            
            # Divider
            st.markdown("---")
            
            # Footer section
            col_footer1, col_footer2 = st.columns(2)
            with col_footer1:
                st.caption(f"**Created:** {time.strftime('%Y-%m-%d %H:%M', created_time)} ({time_ago_text})")
            with col_footer2:
                st.caption(f"**Report ID:** {report['id'][:8]}...")

        # Action buttons for each report
        col_view, col_delete = st.columns(2)

        with col_view:
            if st.button("👁️ View Report", key=f"view_trend_{report['id']}", use_container_width=True):
                # Set current report for viewing
                st.session_state.current_view_trend_report = report
                st.session_state.current_page = "view_single_trend_report"
                st.session_state.page_changed = True
                st.rerun()

        with col_delete:
            if st.button("🗑️ Delete", key=f"delete_trend_{report['id']}", use_container_width=True):
                # Confirm deletion
                if st.checkbox(f"Confirm delete '{report['group_name']}' report?", key=f"confirm_trend_{report['id']}"):
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_trend_{report['id']}", type="secondary"):
                        # Delete the report
                        del st.session_state.stored_trend_reports[report['id']]
                        st.success(f"Report '{report['group_name']}' deleted successfully!")
                        # Stay on the same page but refresh the list
                        st.rerun()

def render_view_single_trend_report_page():
    """Render the single trend report view page"""

    # Back button
    if st.button("← Back to Reports", key="back_to_reports_single", type="secondary"):
        st.session_state.current_page = "view_trend_reports"
        st.session_state.page_changed = True
        st.rerun()

    # Get the current report to view
    report_data = st.session_state.get("current_view_trend_report")

    if not report_data:
        st.error("No trend report selected.")
        if st.button("Go to Reports", key="goto_reports_single"):
            st.session_state.current_page = "view_trend_reports"
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
            Trend Report • {len(report_data['sources'])} Sources
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
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔗</div>
            <div style="font-size: 1.5rem; font-weight: bold;">{}</div>
            <div style="font-size: 0.9rem; opacity: 0.9;">Sources</div>
        </div>
        """.format(len(report_data['sources'])), unsafe_allow_html=True)

    with meta_col2:
        report_type_icons = {
            "Full trend analysis": "📊",
            "Hot topics only": "🔥",
            "Source comparison": "📈",
            "Trend timeline": "⏰"
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

    # Source navigation and summary
    st.markdown("---")
    st.markdown("### 🔗 Source Reports")

    # Quick navigation
    source_names = [f"#{i+1} {source['name']}" for i, source in enumerate(report_data['sources'])]
    selected_source = st.selectbox(
        "Quick jump to source:",
        ["Select a source..."] + source_names,
        key="source_navigator",
        help="Quickly navigate to a specific source's trend report"
    )

    # Display individual reports
    for i, source_report in enumerate(report_data['sources'], 1):
        with st.expander(f"#{i} {source_report['name']}", expanded=True):
            # Source header
            col_name, col_links = st.columns([2, 1])
            with col_name:
                st.markdown(f"### {source_report['name']}")
                if source_report['description']:
                    st.markdown(f"**Description:** {source_report['description']}")

            with col_links:
                if source_report['url']:
                    st.markdown(f"[🔗 Visit Source]({source_report['url']})")

            # Report content
            st.markdown(source_report['report'])

    # Export options
    st.markdown("---")
    st.markdown("### 📤 Export Options")

    col_export1, col_export2 = st.columns(2)

    with col_export1:
        if st.button("📊 Export as CSV", key="export_csv_trend", type="secondary", use_container_width=True):
            # Convert to DataFrame for CSV export
            df_data = []
            for source_report in report_data['sources']:
                df_data.append({
                    'Source Name': source_report['name'],
                    'Source Type': source_report['type'],
                    'Description': source_report['description'],
                    'URL': source_report['url'],
                    'Report Type': report_data['report_type'],
                    'Time Range': report_data['time_range']
                })

            df = pd.DataFrame(df_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name=f"{report_data['group_name']}_trend_report.csv",
                mime="text/csv",
                use_container_width=True
            )

    with col_export2:
        if st.button("📋 Export as JSON", key="export_json_trend", type="secondary", use_container_width=True):
            json_data = json.dumps(report_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Download JSON",
                data=json_data,
                file_name=f"{report_data['group_name']}_trend_report.json",
                mime="application/json",
                use_container_width=True
            )

def render_trend_radar_page():
    """Main function to render the trend radar page with navigation"""

    # Apply custom styles first
    apply_trend_radar_styles()

    # Initialize current page if not set
    if "current_page" not in st.session_state:
        st.session_state.current_page = "trend_groups"

    # Clear any stale state when entering the page
    if "temp_sources" in st.session_state and st.session_state.current_page != "edit_trend_group":
        del st.session_state.temp_sources

    # Check if page was changed and clear any cached state
    if st.session_state.get('page_changed', False):
        st.session_state.page_changed = False
        # Force a clean state for the new page
        if "temp_sources" in st.session_state and st.session_state.current_page != "edit_trend_group":
            del st.session_state.temp_sources

    # Get current page and use exact matching
    current_page = st.session_state.get('current_page', '')
    
    # Use exact string matching for pages
    if current_page == "trend_groups":
        target_page = "trend_groups"
    elif current_page == "edit_trend_group":
        target_page = "edit_trend_group"
    elif current_page == "generate_trend_report":
        target_page = "generate_trend_report"
    elif current_page == "view_trend_reports":
        target_page = "view_trend_reports"
    elif current_page == "view_single_trend_report":
        target_page = "view_single_trend_report"
    else:
        # For main navigation pages, map them to sub-pages
        if current_page == "📈 Trend Radar":
            target_page = "trend_groups"
            st.session_state.current_page = "trend_groups"
        else:
            # Fallback: reset to trend groups page
            st.session_state.current_page = "trend_groups"
            target_page = "trend_groups"
    
    if target_page == "trend_groups":
        render_trend_groups_page()
    elif target_page == "edit_trend_group":
        render_edit_trend_group_page()
    elif target_page == "generate_trend_report":
        render_generate_trend_report_page()
    elif target_page == "view_trend_reports":
        render_view_trend_reports_page()
    elif target_page == "view_single_trend_report":
        render_view_single_trend_report_page()
    else:
        # Fallback: reset to trend groups page
        st.session_state.current_page = "trend_groups"
        render_trend_groups_page()

def apply_trend_radar_styles():
    """Apply custom CSS for trend radar page"""
    st.markdown("""
    <style>
    /* Enhanced button styling for trend radar */
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
    
    /* Selectbox styling */
    .stSelectbox > div > div > div {
        border-radius: 10px !important;
        border: 2px solid #e1e5e9 !important;
    }
    
    /* Metric styling */
    .metric-container {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 12px;
        text-align: center;
        margin: 0.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.2);
    }
    
    /* Ensure HTML content renders properly */
    .stMarkdown {
        overflow: visible !important;
    }
    
    /* Custom report card styling */
    .trend-report-card {
        background: linear-gradient(135deg, #667eea15 0%, #764ba205 100%);
        border: 2px solid #667eea;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .trend-report-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.2);
    }
    
    /* Tag styling for report cards */
    .tag-purple {
        background: #667eea !important;
        color: white !important;
        padding: 0.3rem 0.8rem !important;
        border-radius: 20px !important;
        font-size: 0.8rem !important;
        font-weight: bold !important;
        text-align: center !important;
        display: inline-block !important;
        margin: 0.2rem !important;
    }
    
    .tag-blue {
        background: #4facfe !important;
        color: white !important;
        padding: 0.3rem 0.8rem !important;
        border-radius: 20px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        text-align: center !important;
        display: inline-block !important;
        margin: 0.2rem !important;
    }
    
    .tag-cyan {
        background: #00f2fe !important;
        color: white !important;
        padding: 0.3rem 0.8rem !important;
        border-radius: 20px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        text-align: center !important;
        display: inline-block !important;
        margin: 0.2rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
