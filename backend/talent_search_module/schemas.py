"""
Pydantic schemas for Talent Search System
Defines all data models used in the system
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
import config
import utils
from utils import normalize_whitespace, normalize_url

# ============================ QUERY AND PLANNING SCHEMAS ============================

class QuerySpec(BaseModel):
    """Structured intent parsed from user query"""
    top_n: int = config.DEFAULT_TOP_N
    years: List[int] = Field(default_factory=lambda: config.DEFAULT_YEARS)
    venues: List[str] = Field(default_factory=lambda: ["ICLR","ICML","NeurIPS"])     # e.g., ["ICLR","ICML","NeurIPS",...]
    keywords: List[str] = Field(default_factory=lambda: ["social simulation","multi-agent"])   # e.g., ["social simulation","multi-agent",...]
    must_be_current_student: bool = True
    degree_levels: List[str] = Field(default_factory=lambda: ["PhD","MSc","Master","Graduate"])
    author_priority: List[str] = Field(default_factory=lambda: ["first","last"])
    extra_constraints: List[str] = Field(default_factory=list)  # Other constraints (region/domain etc.)

    @field_validator("years")
    @classmethod
    def keep_ints(cls, v):
        out = []
        for x in v:
            try:
                out.append(int(x))
            except:
                pass
        return out[:5]

    @field_validator("keywords", "venues", "degree_levels", "author_priority", "extra_constraints")
    @classmethod
    def trim_list(cls, v):
        # Deduplicate while preserving order + limit length
        seen = set()
        out = []
        for s in v:
            s = utils.normalize_whitespace(s)
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out[:32]

class PlanSpec(BaseModel):
    """Search plan specification"""
    search_terms: List[str] = Field(..., description="Initial search queries.")
    selection_hint: str = Field(..., description="Preferred sources to select.")

    @field_validator("search_terms")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("search_terms cannot be empty")
        return v[:config.MAX_SEARCH_TERMS]

# ============================ SEARCH AND SELECTION SCHEMAS ============================

class LLMSelectSpec(BaseModel):
    """LLM decision for single URL selection"""
    should_fetch: bool = Field(..., description="Whether this URL should be fetched")

class LLMSelectSpecWithValue(BaseModel):
    """LLM decision for single URL selection with value score"""
    should_fetch: bool = Field(..., description="Whether this URL should be fetched")
    value_score: float = Field(..., description="Value score for this URL")
    reason: str = Field(..., description="Reason for the value score")

class LLMSelectSpecHasAuthorInfo(BaseModel):
    """LLM decision for single URL selection with author info"""
    has_author_info: bool = Field(..., description="Whether this URL contains author info")
    confidence: float = Field(..., description="Confidence score for the author info")
    reason: str = Field(..., description="Reason for the author info")

class LLMSelectSpecVerifyIdentity(BaseModel):
    """LLM decision for profile identity verification"""
    is_target_author: bool = Field(..., description="Whether this profile belongs to the target author")
    confidence: float = Field(..., description="Confidence score for identity verification")
    reason: str = Field(..., description="Specific reason for the decision")

class LLMHomepageIdentitySpec(BaseModel):
    """LLM decision for homepage identity verification before content extraction"""
    is_target_author_homepage: bool = Field(..., description="Whether this homepage belongs to the target author")
    confidence: float = Field(..., description="Confidence score for homepage identity verification")
    author_name_found: str = Field(default="", description="Author name found on the homepage")
    research_area_match: bool = Field(default=False, description="Whether research areas match expectations")
    reason: str = Field(..., description="Detailed reason for the verification decision")

class SelectSpec(BaseModel):
    """URL selection specification - keeping existing structure"""
    urls: List[str] = Field(..., description="Up to N URLs worth fetching (http/https).")

    @field_validator("urls")
    @classmethod
    def limit_len(cls, v):
        seen = set()
        out = []
        for u in v:
            nu = utils.normalize_whitespace(u)
            if nu.startswith("http") and nu not in seen:
                seen.add(nu)
                out.append(nu)
        return out[:config.MAX_URLS]
    
class LLMPaperNameSpec(BaseModel):
    """Specification for paper name extraction"""
    have_paper_name: bool = Field(..., description="Whether the paper name is extracted")
    paper_name: str = Field(..., description="The name of the paper")
    
    
# ============================ CONTENT ANALYSIS SCHEMAS ============================

# Removed complex content analysis - keeping it simple for now

# ============================ AUTHOR AND CANDIDATE SCHEMAS ============================

class CandidateCard(BaseModel):
    """Individual candidate information card"""
    name: str = Field(..., alias="Name")
    current_role_affiliation: str = Field(..., alias="Current Role & Affiliation")
    research_focus: List[str] = Field(default_factory=list, alias="Research Focus")
    profiles: Dict[str, str] = Field(default_factory=dict, alias="Profiles")
    notable: Optional[str] = Field(default=None, alias="Notable")
    evidence_notes: Optional[str] = Field(default=None, alias="Evidence Notes")
    model_config = ConfigDict(populate_by_name=True)

class CandidatesSpec(BaseModel):
    """Specification for candidate extraction results"""
    candidates: List[CandidateCard] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    need_more: bool = False
    followups: List[str] = Field(default_factory=list)

class AuthorListSpec(BaseModel):
    """Specification for author list extraction"""
    authors: List[str] = Field(default_factory=list)

    @field_validator("authors")
    @classmethod
    def limit_authors(cls, v):
        seen = set()
        out = []
        for name in v:
            name = normalize_whitespace(name)
            if config.MIN_AUTHOR_NAME_LENGTH <= len(name) <= config.MAX_AUTHOR_NAME_LENGTH and name not in seen:
                seen.add(name)
                out.append(name)
        return out[:config.MAX_AUTHORS]

# ============================ PAPER AND AUTHOR SCHEMAS ============================

class PaperInfo(BaseModel):
    """Information about a paper with deduplication support"""
    paper_name: str = Field(..., description="The extracted paper name")
    urls: List[str] = Field(default_factory=list, description="List of URLs where this paper was found")
    primary_url: Optional[str] = Field(default=None, description="The primary/best URL for this paper")

    @field_validator("paper_name")
    @classmethod
    def normalize_paper_name(cls, v):
        return normalize_whitespace(v)

    @field_validator("urls")
    @classmethod
    def deduplicate_urls(cls, v):
        seen = set()
        out = []
        for url in v:
            if url and url not in seen:
                seen.add(url)
                out.append(url)
        return out

class AuthorWithId(BaseModel):
    """Author information with Semantic Scholar ID"""
    name: str = Field(..., description="Author name")
    author_id: Optional[str] = Field(default=None, description="Semantic Scholar author ID")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v):
        return normalize_whitespace(v)

class PaperAuthorsResult(BaseModel):
    """Result from Semantic Scholar paper search with authors"""
    url: str = Field(..., description="Original URL where paper was found")
    paper_name: str = Field(..., description="Paper title used for search")
    paper_id: Optional[str] = Field(default=None, description="Semantic Scholar paper ID")
    match_score: Optional[float] = Field(default=None, description="Semantic Scholar match score")
    year: Optional[int] = Field(default=None, description="Publication year")
    venue: Optional[str] = Field(default=None, description="Publication venue")
    paper_url: Optional[str] = Field(default=None, description="Semantic Scholar paper URL")
    authors: List[AuthorWithId] = Field(default_factory=list, description="List of authors with IDs")
    found: bool = Field(default=False, description="Whether the paper was found in Semantic Scholar")

class PaperCollection(BaseModel):
    """Collection of unique papers with deduplication"""
    papers: Dict[str, PaperInfo] = Field(default_factory=dict, description="Paper name -> PaperInfo mapping")

    def add_paper(self, paper_name: str, url: str) -> bool:
        """
        Add a paper URL. Returns True if added, False if paper already exists.
        If paper exists, adds URL to existing list if not already present.
        """
        paper_name = normalize_whitespace(paper_name)

        if not paper_name or not url:
            return False

        if paper_name in self.papers:
            # Paper already exists, add URL if not present
            if url not in self.papers[paper_name].urls:
                self.papers[paper_name].urls.append(url)
            return False  # Not newly added

        # New paper
        self.papers[paper_name] = PaperInfo(
            paper_name=paper_name,
            urls=[url],
            primary_url=url
        )
        return True

    def get_all_papers(self) -> List[PaperInfo]:
        """Get all papers as a list"""
        return list(self.papers.values())

    def get_paper_names(self) -> List[str]:
        """Get all paper names"""
        return list(self.papers.keys())

    def get_urls_for_paper(self, paper_name: str) -> List[str]:
        """Get all URLs for a specific paper"""
        paper_name = normalize_whitespace(paper_name)
        if paper_name in self.papers:
            return self.papers[paper_name].urls
        return []

# ============================ AUTHOR PROFILE SCHEMAS ============================

class LLMAuthorProfileSpec(BaseModel):
    """LLM specification for author profile extraction"""
    name: str = Field(default="", description="Author name as written")
    aliases: List[str] = Field(default_factory=list, description="Name variants/aliases of THIS AUTHOR ONLY")
    affiliation_current: str = Field(default="", description="Current affiliation")
    emails: List[str] = Field(default_factory=list, description="Professional emails")
    personal_homepage: str = Field(default="", description="Personal website URL (not current page)")
    homepage_url: str = Field(default="", description="Personal or lab/university page (legacy field)")
    interests: List[str] = Field(default_factory=list, description="Research interests")
    selected_publications: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Selected publications with title/year/venue/url"
    )
    notable_achievements: List[str] = Field(
        default_factory=list,
        description="Awards, honors, fellowships, recognitions"
    )
    social_impact: str = Field(default="", description="H-index, citations, influence metrics")
    career_stage: str = Field(default="", description="Career stage: student/postdoc/assistant_prof/etc")
    social_links: Dict[str, str] = Field(
        default_factory=dict,
        description="Social media and platform links extracted from page"
    )

# ============================ STATE AND RESEARCH SCHEMAS ============================

class ResearchState(BaseModel):
    """Main state object for the research process"""
    query: str
    round: int = 0
    query_spec: QuerySpec = Field(default_factory=QuerySpec)
    plan: Dict[str, Any] = Field(default_factory=dict)
    serp: List[Dict[str, str]] = Field(default_factory=list)
    selected_urls: List[str] = Field(default_factory=list)
    selected_serp: List[Dict[str, str]] = Field(default_factory=list)
    sources: Dict[str, str] = Field(default_factory=dict)   # url -> text
    report: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    need_more: bool = False
    followups: List[str] = Field(default_factory=list)
    expanded_authors: bool = False

# ============================ UTILITY FUNCTIONS ============================

# Removed create_selection_prompt - now handled directly in graph.py
