# 🎯 MSRA Resume Evaluation Feature

## Overview
The Resume Evaluation feature has been enhanced to support Microsoft Research Asia (MSRA) Research Internship evaluation criteria. This feature allows HR professionals and hiring managers to evaluate candidates using a structured, comprehensive rubric.

## Features

### 📄 Input Methods
1. **PDF Upload**: Traditional resume PDF upload and text extraction
2. **Homepage URL**: Direct input of candidate's personal or lab homepage URL for evaluation

### 🎯 MSRA Evaluation Criteria
The system evaluates candidates across four key dimensions:

#### 1. Academic Background
- University/research lab reputation
- Advisor's recognition in the field
- Degree stage (MS/PhD preferred)

#### 2. Research Output
- Publications at top-tier venues (NeurIPS, ICML, ICLR, ACL, CVPR, etc.)
- Oral/Spotlight/Best Paper awards
- First-author or equal contribution papers
- Preprints showing an active pipeline

#### 3. Research Alignment
- Topics closely match MSRA directions
- Evidence of originality and problem definition ability

#### 4. Recognition & Impact
- Fellowships, rising star awards, scholarships
- Reviewer/PC/organizer roles in major conferences
- Visible leadership in research community

### 🚀 User Experience Features
- **Progress Tracking**: Visual progress bar showing evaluation steps
- **Demo Mode**: Built-in example evaluation (Linxin Song) for demonstration
- **Professional Styling**: MSRA-branded evaluation report with enhanced CSS
- **Export Options**: Download results as JSON or Markdown formats

## Usage

### For Demo/Testing
1. Navigate to "📄 Resume Evaluation" in the sidebar
2. Check "Show demo result (Linxin Song example)"
3. Click "🔍 Evaluate Candidate"
4. View the comprehensive MSRA evaluation report

### For Real Evaluations
1. Choose input method (PDF or Homepage URL)
2. Upload PDF or enter homepage URL
3. Configure evaluation parameters
4. Uncheck demo mode
5. Click "🔍 Evaluate Candidate"
6. Review results and export as needed

## Technical Implementation

### Backend Functions
- `evaluate_resume_msra()`: Main MSRA evaluation function
- `process_homepage_url()`: Placeholder for homepage processing
- `extract_pdf_text()`: PDF text extraction

### Frontend Components
- Enhanced UI with MSRA-specific styling
- Progress indicators and status updates
- Professional evaluation report layout
- Export functionality for results

## Future Enhancements
- Real homepage URL processing and web scraping
- Integration with academic databases (Google Scholar, Semantic Scholar)
- Automated scoring and ranking algorithms
- Comparison tools for multiple candidates
- Custom evaluation criteria configuration

## Dependencies
- Streamlit for web interface
- PyPDF2 for PDF processing
- Custom CSS styling for professional appearance
- LLM integration for intelligent evaluation (when available)

## Notes
- Currently uses a demo evaluation result for demonstration purposes
- Real evaluation requires resume text input and LLM backend
- Export functionality supports both JSON and Markdown formats
- Styling follows MSRA brand guidelines and professional standards
