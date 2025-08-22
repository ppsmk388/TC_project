import streamlit as st


def render_home_page():
    """Render the beautiful home page"""
    st.markdown("## 🚀 Core Features")
    
    # Stats section with clickable navigation buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 Smart Search\n\nAI-powered candidate discovery", key="nav_smart_search", use_container_width=True, help="Click to go to Targeted Search"):
            st.session_state.current_page = "🔍 Targeted Search"
            st.rerun()
    
    with col2:
        if st.button("📊 Analytics\n\nPerformance insights", key="nav_analytics", use_container_width=True, help="Click to go to Achievement Report"):
            st.session_state.current_page = "📊 Achievement Report"
            st.rerun()
    
    with col3:
        if st.button("📄 Evaluation\n\nResume analysis", key="nav_evaluation", use_container_width=True, help="Click to go to Resume Evaluation"):
            st.session_state.current_page = "📄 Resume Evaluation"
            st.rerun()
    
    with col4:
        if st.button("📈 Trends\n\nMarket intelligence", key="nav_trends", use_container_width=True, help="Click to go to Trend Radar"):
            st.session_state.current_page = "📈 Trend Radar"
            st.rerun()
    
    # Feature cards with better styling
    st.markdown("## 🚀 Detailed Features")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="home-feature-card">
            <div class="home-feature-icon">🔍</div>
            <h3 style="color: #2c3e50; margin-bottom: 1rem; font-size: 1.5rem;">Targeted Talent Search</h3>
            <p style="color: #34495e; line-height: 1.6; margin-bottom: 1rem;">Find the perfect candidates using AI-powered semantic search across research areas, locations, and roles.</p>
            <ul style="color: #34495e; line-height: 1.6;">
                <li>Semantic search across academic databases</li>
                <li>Location-based filtering</li>
                <li>Role-specific candidate matching</li>
                <li>Publication history analysis</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="home-feature-card">
            <div class="home-feature-icon">📊</div>
            <h3 style="color: #2c3e50; margin-bottom: 1rem; font-size: 1.5rem;">Achievement Reports</h3>
            <p style="color: #34495e; line-height: 1.6; margin-bottom: 1rem;">Generate comprehensive performance reports for researchers and academics.</p>
            <ul style="color: #34495e; line-height: 1.6;">
                <li>Publication metrics analysis</li>
                <li>Citation impact assessment</li>
                <li>Collaboration network mapping</li>
                <li>Career progression tracking</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="home-feature-card">
            <div class="home-feature-icon">📄</div>
            <h3 style="color: #2c3e50; margin-bottom: 1rem; font-size: 1.5rem;">Resume Evaluation</h3>
            <p style="color: #34495e; line-height: 1.6; margin-bottom: 1rem;">AI-powered resume analysis with detailed scoring and recommendations.</p>
            <ul style="color: #34495e; line-height: 1.6;">
                <li>PDF resume parsing</li>
                <li>Skills assessment</li>
                <li>Role fit analysis</li>
                <li>Improvement suggestions</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="home-feature-card">
            <div class="home-feature-icon">📈</div>
            <h3 style="color: #2c3e50; margin-bottom: 1rem; font-size: 1.5rem;">Trend Radar</h3>
            <p style="color: #34495e; line-height: 1.6; margin-bottom: 1rem;">Monitor industry trends and social media insights in real-time.</p>
            <ul style="color: #34495e; line-height: 1.6;">
                <li>Social media monitoring</li>
                <li>Trend analysis</li>
                <li>Competitive intelligence</li>
                <li>Market insights</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Quick start section with better styling
    st.markdown("## 🚀 Quick Start")
    st.info("💡 **Tip**: Use the sidebar navigation to explore different features. Each tool is designed to work independently, so you can start with any feature that interests you most!")
    
    # Footer with better styling
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem; background: rgba(255,255,255,0.1); border-radius: 10px;'>
        <p style='font-size: 1.1rem; color: #2c3e50; margin-bottom: 0.5rem;'>🎯 Talent Copilot HR - Transforming HR with AI</p>
        <p style='color: #7f8c8d; margin: 0;'>Built with Streamlit • Powered by AI</p>
    </div>
    """, unsafe_allow_html=True)
