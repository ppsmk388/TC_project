#!/usr/bin/env python3
"""
Demo script for the enhanced Targeted Search functionality
Run this to test the new UI and demo data integration
"""

import streamlit as st
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from frontend.targeted_search import render_targeted_search_page, apply_targeted_search_styles
from frontend.theme import inject_global_css

def main():
    st.set_page_config(
        page_title="Targeted Search Demo", 
        page_icon="🔍", 
        layout="wide", 
        initial_sidebar_state="collapsed"
    )
    
    # Apply styling
    inject_global_css()
    apply_targeted_search_styles()
    
    # Render the page
    render_targeted_search_page()

if __name__ == "__main__":
    main()
