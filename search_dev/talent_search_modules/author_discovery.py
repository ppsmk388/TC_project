"""
Author Discovery Module for Talent Search System
Implements comprehensive author profile discovery and integration
"""

from typing import List, Dict, Any, Tuple, Optional
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
import json
import requests
from bs4 import BeautifulSoup

import config
import utils
import search
import llm
import schemas
from utils import normalize_url, domain_of, clean_text, safe_sleep
from search import searxng_search, fetch_text, extract_title_unified, extract_main_text

# ============================ DATA CLASSES ============================

@dataclass
class AuthorProfile:
    """Complete author profile with all discovered information"""
    name: str
    aliases: List[str]
    platforms: Dict[str, str]        # {'openreview': url, 'semanticscholar': url, ...}
    ids: Dict[str, str]              # {'orcid': '0000-0000-0000-0000', 'semanticscholar': '2316...', ...}
    homepage_url: Optional[str]
    affiliation_current: Optional[str]
    emails: List[str]
    interests: List[str]
    selected_publications: List[Dict[str, Any]]  # [{'title':..., 'year':..., 'venue':..., 'url':...}]
    confidence: float                 # 0~1
    
    # 新增字段
    notable_achievements: List[str] = field(default_factory=list)  # Awards, honors, recognitions
    social_impact: Optional[str] = None      # H-index, citations, influence metrics
    career_stage: Optional[str] = None       # student/postdoc/assistant_prof/etc
    overall_score: float = 0.0               # 综合评分 0~100

@dataclass
class ProfileCandidate:
    """Candidate profile URL with scoring and LLM decision"""
    url: str
    title: str
    snippet: str
    score: float
    should_fetch: Optional[bool] = None
    reason: Optional[str] = None

# ============================ PLATFORM CONFIGURATION ============================

# Platform priority (high → low)
TRUST_RANK = ['orcid', 'openreview', 'scholar', 'semanticscholar', 'dblp', 'university', 'homepage', 'github', 'huggingface', 'researchgate', 'twitter', 'linkedin']

# Whitelist domains with high trust scores
WHITELIST_HOSTS = {
    'orcid.org': 0.9,
    'openreview.net': 0.9,
    'scholar.google.com': 0.9,
    'semanticscholar.org': 0.9,
    'dblp.org': 0.9,
}

# Secondary domains with medium trust
SECONDARY_HOSTS = {
    'github.io': 1, 'github.com': 0.8, 'huggingface.co': 0.8,
}

# Domains to block/avoid
PERSONAL_DOMAINS = {
    'linkedin.com', 'x.com', 'twitter.com', 'facebook.com', 'medium.com', 'reddit.com', 'youtube.com'
}

# ============================ SEARCH QUERY TEMPLATES ============================

# 优化的平台特定查询模板 - 专注高质量结果
PLATFORM_QUERIES = [
    # 个人主页 - 最高优先级
    '{q} site:github.io',
    '{q} "personal website" OR "homepage"',
    '{q} site:x.com',
    '{q} site:linkedin.com/in',
    '{q} site:researchgate.net/profile',
    '{q} site:github.com',
    '{q} site:huggingface.co',
    
    # 学术平台 - 高优先级，精确匹配
    '{q} site:openreview.net/profile',
    '{q} site:scholar.google.com/citations',
    '{q} site:orcid.org',
    '{q} site:semanticscholar.org/author',
    '{q} site:dblp.org/pid',
    '{q} site:dblp.org/pers',
    

]

# 优化的Notable查询 - 只保留高价值的成就查询
NOTABLE_QUERIES = [
    '{q} "best paper" OR "outstanding paper" OR "paper award"',
    '{q} "fellow" OR "IEEE fellow" OR "ACM fellow"',
    '{q} "rising star" OR "young researcher award"',
    '{q} "keynote" OR "invited speaker"',
    '{q} "distinguished" OR "excellence award"'
]

# ============================ REGEX PATTERNS FOR ID EXTRACTION ============================

ID_PATTERNS = {
    'orcid': re.compile(r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})'),
    'openreview': re.compile(r'openreview\.net/profile\?id=([A-Za-z0-9_\-\.%]+)'),
    'scholar': re.compile(r'scholar\.google\.com/citations\?user=([A-Za-z0-9_\-]+)'),
    'semanticscholar': re.compile(r'semanticscholar\.org/author/([^/\s]+)'),
    'dblp1': re.compile(r'dblp\.org/pid/([0-9a-z/]+)'),
    'dblp2': re.compile(r'dblp\.org/pers/([0-9a-z/]+)'),
    'twitter': re.compile(r'(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})(?:/|$)'),
    'github': re.compile(r'github\.com/([A-Za-z0-9\-]+)(?:/|$)'),
}

# ============================ LLM PROMPTS ============================

# 第一阶段：判断是否包含作者信息
PROMPT_HAS_AUTHOR_INFO = lambda author_name, title, url, snippet: f"""
Determine if this page contains information ABOUT the specific researcher (not just mentions).

TARGET AUTHOR: {author_name}

CANDIDATE PAGE:
Title: {title[:180]}
URL: {url}
Snippet: {snippet[:400]}

Does this page contain biographical/professional information ABOUT this specific researcher?

Look for:
✓ Author profile/bio pages
✓ Faculty/staff pages  
✓ Personal homepages
✓ Research group pages featuring the author
✓ Academic platform profiles (ORCID, Google Scholar, etc.)

Avoid:
✗ Just paper listings without author info
✗ Generic conference/journal pages
✗ News articles just mentioning the name
✗ Social media posts without substantial bio info
✗ Company/organization pages without individual profiles

Return JSON: {{"has_author_info": true/false, "confidence": 0.0-1.0, "reason": "<brief explanation>"}}
"""

# 新增：Profile身份验证prompt
PROMPT_VERIFY_PROFILE_IDENTITY = lambda author_name, platform, url, content_preview: f"""
Verify if this {platform} profile belongs to the target researcher.

TARGET AUTHOR: {author_name}

PROFILE TO VERIFY:
Platform: {platform}
URL: {url}
Content Preview: {content_preview[:800]}

Is this profile definitely for the target author {author_name}?

VERIFICATION CRITERIA:
✓ Name match (exact or reasonable variations)
✓ Research area consistency 
✓ Institution/affiliation match
✓ Publication overlap
✓ Profile completeness and authenticity

REJECT IF:
✗ Different person with similar name
✗ Generic/incomplete profile
✗ Conflicting information (different field, institution)
✗ Suspicious/fake profile indicators

Return JSON: {{"is_target_author": true/false, "confidence": 0.0-1.0, "reason": "<specific reason>"}}
"""

# Homepage身份预验证prompt
PROMPT_HOMEPAGE_IDENTITY_CHECK = lambda author_name, paper_title, url, preview_content: f"""
CRITICAL IDENTITY VERIFICATION: Verify if this homepage belongs to the target author BEFORE extracting detailed information.

TARGET AUTHOR: {author_name}
KNOWN PAPER: {paper_title}

HOMEPAGE TO VERIFY:
URL: {url}
Preview Content: {preview_content[:1200]}

VERIFICATION TASK:
Is this homepage definitely for the target author {author_name}?

STRICT VERIFICATION CRITERIA:
✓ EXACT name match (not just similar names)
✓ Research area alignment with expected field
✓ Institution/affiliation consistency
✓ Publication overlap or research focus match
✓ No conflicting biographical information

REJECT IF:
✗ Different person with similar/same name
✗ Wrong research field entirely
✗ Conflicting affiliations or timeline
✗ Generic template or incomplete site
✗ Any doubt about identity

EXAMPLES OF REJECTION:
- "John Smith" at MIT vs "John Smith" at Stanford (different people)
- Computer Science researcher vs Biology researcher with same name
- Graduate student vs Senior Professor with same name but different backgrounds

Return JSON: {{
  "is_target_author_homepage": true/false,
  "confidence": 0.0-1.0,
  "author_name_found": "<exact name found on homepage>",
  "research_area_match": true/false,
  "reason": "<detailed explanation with specific evidence>"
}}

BE EXTREMELY CONSERVATIVE - when in doubt, return false.
"""

# 第二阶段：判断是否值得抓取
PROMPT_PROFILE_RELEVANCE = lambda author_name, paper_title, title, url, snippet: f"""
This page contains author information. Decide if it's worth fetching for profile building.

AUTHOR: {author_name}
PAPER: {paper_title}

CANDIDATE:
Title: {title[:180]}
URL: {url}
SNIPPET: {snippet[:400]}

Rate the VALUE for building author profile (0.0-1.0):

HIGH VALUE (0.8-1.0):
- Official academic profiles (ORCID, OpenReview, Semantic Scholar)
- University faculty pages
- Personal research websites
- Detailed CV/bio pages

MEDIUM VALUE (0.5-0.7):
- GitHub profiles with research projects
- Conference speaker bios
- Research group member pages
- Professional platform profiles

LOW VALUE (0.1-0.4):
- Brief mentions in news
- Social media profiles
- Generic directory listings

Return JSON: {{"should_fetch": true/false, "value_score": 0.0-1.0, "reason": "<short>"}}
"""

# 个人网站专用的“零幻觉”提取 prompt（严格版）
HOMEPAGE_EXTRACT_PROMPT = lambda author_name, dump: f"""
You are in ZERO-HALLUCINATION mode. Extract ONLY information that appears **verbatim in TEXT CONTENT**. 
If something is not explicitly present, return an empty string "" or empty list [].

TARGET AUTHOR: {author_name}
CONTENT TYPE: Personal Website / Homepage

TEXT CONTENT (source of truth — do not infer beyond this):
{dump}
==== END ====

OUTPUT REQUIREMENTS
- Return **valid JSON only** (no prose, no comments).
- Use exactly these keys (and no extras):
{{
  "name": "<full name as written or ''>",
  "aliases": ["..."],                      // author’s own variants only; else []
  "affiliation_current": "<... or ''>",
  "emails": ["..."],                       // professional emails only; else []
  "interests": ["..."],                    // concrete research areas; else []
  "selected_publications": [               // up to 3; else []
    {{"title":"...", "year":2024, "venue":"...", "url":"..."}}
  ],
  "notable_achievements": ["..."],         // awards/fellowships/best papers; else []
  "social_impact": "<e.g., 'h-index: 18, citations: 1350' or ''>",
  "career_stage": "<student/postdoc/assistant_prof/associate_prof/full_prof/industry or ''>",
  "social_links": {{
    "scholar": "",                         // MUST be a URL string present verbatim in TEXT CONTENT, else ""
    "github": "",
    "linkedin": "",
    "twitter": "",
    "orcid": ""
  }}
}}

CRITICAL NON-NEGOTIABLE RULES
1) **VERBATIM-URL RULE for social_links**: A field may be non-empty **only if the exact URL substring exists in TEXT CONTENT**.
   - Acceptable patterns (must appear literally in TEXT CONTENT):
     - scholar: "scholar.google.com/citations?user="…
     - github:  "github.com/<username>"…
     - linkedin:"linkedin.com/in/<handle>"…
     - twitter: "twitter.com/<handle>" or "x.com/<handle>"
     - orcid:   "orcid.org/0000-0000-0000-0000" (4-4-4-4 digits)
   - **Do NOT** construct URLs from names, emails, or guesses. **If absent, return ""**.

2) **DO NOT NORMALIZE OR REWRITE URLs**. Copy the substring exactly as it appears in TEXT CONTENT (including http/https if shown). If a platform is mentioned without a visible URL, leave the field as "".

3) **Emails**: copy only emails that appear verbatim in TEXT CONTENT. Exclude generic addresses (info@, admin@, support@, etc.). If none, return [].

4) **Aliases**: include only alternative names that refer to THIS author and are shown in TEXT CONTENT. Otherwise [].

5) **Publications/achievements/metrics**: include only if explicitly present. **No inferences.**

6) If any field is missing or unclear, return "" or [] for that field.

Return JSON only.
"""

# 通用字段抽取prompt
PROFILE_EXTRACT_PROMPT = lambda author_name, dump, platform_type="generic": f"""
Extract author profile fields from {platform_type} page content.

TARGET AUTHOR: {author_name}
PLATFORM TYPE: {platform_type}

TEXT CONTENT:
{dump}
==== END ====

Return STRICT JSON with these keys:
{{
  "name": "<full name as written>",
  "aliases": ["ONLY alternative names/nicknames of THIS AUTHOR"],
  "affiliation_current": "<current institution/company>",
  "emails": ["professional emails only"],
  "personal_homepage": "<personal website URL if different from current page>",
  "interests": ["research areas/topics"],
  "selected_publications": [{{"title":"...", "year":2024, "venue":"...", "url":"..."}}],
  "notable_achievements": ["awards/honors/recognitions"],
  "social_impact": "<h-index, citations, influence metrics>",
  "career_stage": "<student/postdoc/assistant_prof/associate_prof/full_prof/industry>",
  "social_links": {{"platform": "url"}}
}}

CRITICAL EXTRACTION RULES:
1. **Name**: Use the most complete/formal version found for THIS AUTHOR ONLY
2. **Aliases**: ONLY include alternative names/nicknames of THE TARGET AUTHOR
3. **Affiliation**: Current primary affiliation only
4. **Emails**: Only work/institutional emails visible on page
5. **Homepage**: Personal website URL (NOT the current page URL)
6. **Interests**: Specific research areas, not generic terms
7. **Publications**: Max 3 most recent/important papers by THIS AUTHOR
8. **Notable**: Awards, fellowships, best papers of THIS AUTHOR only
9. **Social Impact**: Citation counts, h-index of THIS AUTHOR
10. **Career Stage**: Current career stage of THIS AUTHOR
11. **Social Links**: Extract social media/platform links from the page

PLATFORM-SPECIFIC HINTS:
- OpenReview: Focus on reviews, paper submissions, expertise areas  
- Google Scholar: Emphasize citation metrics, publication trends
- ORCID: Look for comprehensive work history, affiliations
- University pages: Focus on teaching, research groups, lab info
- GitHub: Technical projects, code contributions, collaboration

If any field is unclear/absent, return empty string "" or empty list [].
DO NOT invent information not present in the text.
NEVER include names of other people in aliases field.
"""

# ============================ QUERY BUILDING FUNCTIONS ============================

def build_author_queries(first_author: str, paper_title: str, aliases: List[str] = None, 
                        include_notable: bool = True) -> List[str]:
    """Build comprehensive and precise search queries for author discovery"""
    aliases = aliases or []
    name_variants = [first_author] + aliases
    base = []

    for nm in name_variants:
        # 核心查询：作者名 + 论文名
        name_paper_q = f'"{nm}" "{paper_title}"'
        # 作者名查询
        name_q = f'"{nm}"'
        
        # 平台特定查询
        for tpl in PLATFORM_QUERIES:
            # 优先使用名字+论文的查询
            if "x.com" in tpl or "twitter.com" in tpl or "linkedin.com" in tpl or "researchgate.net" in tpl or "huggingface.co" in tpl:
                # 然后使用只有名字的查询（更广泛）
                base.append(tpl.format(q=name_q))
            else:
                base.append(tpl.format(q=name_paper_q))

        
        # 添加Notable信息查询
        if include_notable:
            for notable_tpl in NOTABLE_QUERIES:
                base.append(notable_tpl.format(q=name_q))

    # 去重并排序（优先级排序）
    seen, out = set(), []
    
    # 第一优先级：个人主页
    priority_0 = [q for q in base if any(site in q for site in ['github.io', 'github.com', 'personal', 'homepage', 'x.com', 'twitter.com', 'linkedin.com', 'researchgate.net', 'huggingface.co']) 
                  and paper_title in q]
    
    # 第一优先级：学术平台 + 名字+论文
    priority_1 = [q for q in base if any(site in q for site in 
                  ['openreview.net', 'semanticscholar.org', 'scholar.google.com', 'orcid.org']) 
                  and paper_title in q]
    
    # 第二优先级：机构页面 + 名字+论文  
    priority_2 = [q for q in base if any(site in q for site in 
                  ['site:edu', 'site:ac.']) 
                  and paper_title in q]
    
    # 第三优先级：学术平台 + 只有名字
    priority_3 = [q for q in base if any(site in q for site in 
                  ['openreview.net', 'semanticscholar.org', 'scholar.google.com', 'orcid.org']) 
                  and paper_title not in q and not any(notable in q for notable in 
                  ['award', 'fellow', 'best paper'])]
    
    # 第四优先级：Notable查询
    priority_4 = [q for q in base if any(notable in q for notable in 
                  ['award', 'fellow', 'best paper', 'rising star', 'keynote'])]
    
    # 第五优先级：其他查询
    priority_5 = [q for q in base if q not in priority_0 + priority_1 + priority_2 + priority_3 + priority_4]
    
    # 按优先级合并
    for priority_list in [priority_0, priority_1, priority_2, priority_3, priority_4, priority_5]:
        for q in priority_list:
            if q not in seen and len(out) < 150:  # 增加查询数量限制
                seen.add(q)
                out.append(q)
    
    return out

# ============================ SCORING AND EVALUATION FUNCTIONS ============================

def score_candidate(item: Dict[str, Any], author_name: str, paper_title: str) -> float:
    """Score a search result candidate based on relevance and trust"""
    url = (item.get('url') or '').lower()
    title = (item.get('title') or '')
    snippet = (item.get('snippet') or '')

    dom = domain_of(url)
    score = 0.0

    # Domain trust scoring
    if dom in WHITELIST_HOSTS:
        score += 0.8 * WHITELIST_HOSTS[dom]
    elif any(dom.endswith(k) for k in SECONDARY_HOSTS):
        score += 0.5
    elif dom in PERSONAL_DOMAINS:
        score += 0.9

    # Name and paper matching signals
    if author_name.lower() in (title + " " + snippet).lower():
        score += 0.25

    # Paper title presence
    if len(paper_title) > 0 and paper_title[:20].lower() in (title + " " + snippet).lower():
        score += 0.25

    # Platform-specific patterns
    if any(k in url for k in ['orcid.org/', 'openreview.net/profile', '/citations?user=', '/author/']):
        score += 0.25

    # Avoid generic content
    if any(k in url for k in ['news', 'blog', 'forum', 'comment', 'review']):
        score -= 0.2

    return max(0.0, score)

def extract_ids_from_url(url: str) -> Dict[str, str]:
    """Extract platform IDs from URL using regex patterns"""
    out = {}
    for key, pat in ID_PATTERNS.items():
        m = pat.search(url)
        if m:
            val = m.group(1)
            if key.startswith('dblp'):
                out['dblp'] = val
            else:
                out[key] = val
    return out

def check_url_redirect(url: str, max_redirects: int = 5) -> Tuple[str, bool]:
    """
    检查URL是否有重定向，返回最终URL和是否发生了重定向
    
    Args:
        url: 原始URL
        max_redirects: 最大重定向次数
        
    Returns:
        (final_url, redirected)
    """
    try:
        # 使用HEAD请求检查重定向，避免下载完整内容
        response = requests.head(url, allow_redirects=True, timeout=10, headers=config.UA)
        final_url = response.url
        
        # 规范化URL比较
        original_normalized = normalize_url(url)
        final_normalized = normalize_url(final_url)
        
        redirected = original_normalized != final_normalized
        
        if redirected:
            print(f"[URL Redirect] {url} → {final_url}")
        
        return final_url, redirected
        
    except Exception as e:
        print(f"[URL Redirect] Failed to check redirect for {url}: {e}")
        return url, False

def verify_homepage_identity_before_fetch(author_name: str, paper_title: str, url: str, 
                                       snippet: str, llm_client) -> Tuple[bool, float, str]:
    """
    在抓取homepage完整内容之前验证身份
    
    Args:
        author_name: 目标作者姓名
        paper_title: 已知论文标题
        url: homepage URL
        snippet: 搜索结果snippet
        llm_client: LLM客户端
        
    Returns:
        (is_target_author, confidence, reason)
    """
    try:
        # 获取少量预览内容进行身份验证
        preview_content = fetch_text(url, max_chars=2000, snippet=snippet)
        if not preview_content or len(preview_content) < 100:
            return False, 0.1, "Insufficient content for verification"
        
        prompt = PROMPT_HOMEPAGE_IDENTITY_CHECK(author_name, paper_title, url, preview_content)
        result = llm.safe_structured(llm_client, prompt, schemas.LLMHomepageIdentitySpec)
        
        if result:
            is_target = bool(getattr(result, 'is_target_author_homepage', False))
            confidence = float(getattr(result, 'confidence', 0.0))
            reason = str(getattr(result, 'reason', 'LLM verification'))
            author_found = str(getattr(result, 'author_name_found', ''))
            research_match = bool(getattr(result, 'research_area_match', False))
            
            # 增加额外的验证逻辑
            if is_target and confidence >= 0.7:
                # 检查找到的作者名是否与目标匹配
                if author_found and author_name.lower() in author_found.lower():
                    return True, confidence, f"Identity verified: {reason}"
                elif research_match:
                    return True, max(0.6, confidence - 0.1), f"Research area match: {reason}"
                else:
                    return False, 0.3, f"Name mismatch despite LLM approval: {reason}"
            
            return is_target, confidence, reason
        
    except Exception as e:
        print(f"[Homepage Identity Check] LLM failed for {url}: {e}")
        
    # 回退到简单的文本匹配
    if snippet:
        author_words = set(author_name.lower().split())
        snippet_lower = snippet.lower()
        name_matches = sum(1 for word in author_words if len(word) > 2 and word in snippet_lower)
        
        if name_matches >= len(author_words) * 0.7:
            return True, 0.6, "Fallback name matching in snippet"
    
    return False, 0.2, "Failed identity verification"

def verify_profile_identity(author_name: str, platform: str, url: str, content: str, 
                          llm_client) -> Tuple[bool, float, str]:
    """
    使用LLM验证profile是否属于目标作者
    
    Args:
        author_name: 目标作者姓名
        platform: 平台类型 (linkedin, twitter, scholar, etc.)
        url: profile URL
        content: 页面内容预览
        llm_client: LLM客户端
        
    Returns:
        (is_target_author, confidence, reason)
    """
    # 对于权威学术平台，降低验证要求
    if platform in ['orcid', 'openreview', 'scholar', 'semanticscholar']:
        # 简单的名字匹配检查
        author_words = set(author_name.lower().split())
        content_lower = content.lower()
        
        # 检查是否有足够的名字匹配
        name_matches = sum(1 for word in author_words if len(word) > 2 and word in content_lower)
        if name_matches >= len(author_words) * 0.6:  # 60%的名字词汇匹配
            return True, 0.8, f"Academic platform with name match"
    
    # 对于社交平台，使用LLM严格验证
    if platform in ['linkedin', 'twitter', 'researchgate']:
        try:
            prompt = PROMPT_VERIFY_PROFILE_IDENTITY(author_name, platform, url, content)
            result = llm.safe_structured(llm_client, prompt, schemas.LLMSelectSpecVerifyIdentity)
            
            if result:
                is_target = bool(getattr(result, 'is_target_author', False))
                confidence = float(getattr(result, 'confidence', 0.0))
                reason = str(getattr(result, 'reason', 'LLM verification'))
                return is_target, confidence, reason
        except Exception as e:
            print(f"[Profile Verification] LLM failed for {platform}: {e}")
    
    # 默认：基于内容的简单验证
    author_words = set(author_name.lower().split())
    content_lower = content.lower()
    name_matches = sum(1 for word in author_words if len(word) > 2 and word in content_lower)
    
    if name_matches >= len(author_words) * 0.7:
        return True, 0.6, "Basic name matching"
    
    return False, 0.2, "Insufficient name match"

# ============================ SMART PLATFORM URL MANAGEMENT ============================

def should_update_platform_url(profile: AuthorProfile, platform_type: str, new_url: str, author_name: str) -> bool:
    """判断是否应该更新平台URL - 使用LLM验证关键更新"""
    current_url = profile.platforms.get(platform_type)
    if not current_url:
        return True  # 没有现有URL，直接添加
    
    # 对于LinkedIn和Twitter，如果现有URL质量很低，需要LLM验证
    if platform_type in ['linkedin', 'twitter']:
        current_quality = assess_url_quality(current_url, platform_type, author_name)
        new_quality = assess_url_quality(new_url, platform_type, author_name)
        
        # 如果新URL质量显著更高，且现有URL质量很低，直接更新
        if current_quality < 0.3 and new_quality > 0.6:
            return True
        
        # 如果质量相近，保持现有URL
        if abs(new_quality - current_quality) < 0.2:
            return False
    
    return assess_url_quality(new_url, platform_type, author_name) > assess_url_quality(current_url, platform_type, author_name)

def update_platform_url(profile: AuthorProfile, platform_type: str, new_url: str, author_name: str):
    """智能更新平台URL，优先保留更准确的链接"""
    
    if should_update_platform_url(profile, platform_type, new_url, author_name):
        profile.platforms[platform_type] = new_url

def assess_url_quality(url: str, platform: str, author: str) -> float:
    """评估URL质量"""
    score = 0.0
    author_lower = author.lower().replace(' ', '')
    author_parts = [part.lower() for part in author.split()]
    
    # 包含作者名字的URL质量更高
    if any(part in url.lower() for part in author_parts if len(part) > 2):
        score += 0.5
    
    # 特定平台的质量指标
    if platform == 'scholar' and 'citations?user=' in url:
        score += 0.4
    elif platform == 'github' and not any(bad in url for bad in ['/orgs/', '/topics/', '/search']):
        score += 0.4
    elif platform == 'linkedin':
        if '/in/' in url and not '/directory/' in url:
            score += 0.6  # LinkedIn个人档案
            # 检查用户名是否与作者相关
            linkedin_username = url.split('/in/')[-1].split('/')[0].split('?')[0]
            if any(part.lower() in linkedin_username.lower() for part in author_parts if len(part) > 2):
                score += 0.4
        elif '/directory/' in url:
            score -= 0.5  # 目录页面质量很低
    elif platform == 'twitter':
        if not any(bad in url for bad in ['/status/', '/search', '?lang=', '/hashtag/']):
            # 检查用户名是否与作者相关
            twitter_username = url.split('/')[-1].split('?')[0]
            name_match = any(part.lower() in twitter_username.lower() for part in author_parts if len(part) > 2)
            if name_match:
                score += 0.7  # 用户名匹配的Twitter账号
            else:
                score += 0.2  # 用户名不匹配的Twitter账号质量低
    elif platform == 'orcid' and re.search(r'\d{4}-\d{4}-\d{4}-\d{4}', url):
        score += 0.5
    elif platform == 'openreview' and 'profile?id=' in url:
        score += 0.4
    elif platform == 'homepage':
        # 个人域名优于托管服务
        if any(domain in url for domain in ['.com/', '.org/', '.net/', '.edu/']):
            score += 0.5
        if 'github.io' in url:
            score += 0.3
    
    # 惩罚明显错误的URL
    if any(bad in url.lower() for bad in ['directory', 'search', 'random', 'example']):
        score -= 0.3
        
    return max(0.0, score)

def validate_social_link_for_author(platform: str, url: str, author_name: str) -> bool:
    """
    验证社交媒体链接是否真的属于目标作者
    
    Args:
        platform: 平台类型
        url: 链接URL
        author_name: 目标作者姓名
        
    Returns:
        是否有效
    """
    if not url or not url.startswith('http'):
        return False
    
    author_words = [word.lower() for word in author_name.split() if len(word) > 2]
    url_lower = url.lower()
    
    # Twitter/X 特殊验证
    if platform == 'twitter':
        # 提取用户名
        if 'x.com/' in url_lower or 'twitter.com/' in url_lower:
            # 排除明显错误的URL
            if any(bad in url_lower for bad in ['/status/', '/search', '/hashtag/', '?lang=', '/i/']):
                return False
            
            # 提取用户名部分
            username_part = url_lower.split('/')[-1].split('?')[0]
            
            # 检查用户名是否与作者相关
            if len(username_part) < 3 or len(username_part) > 20:
                return False
            
            # 检查是否包含作者名字的部分
            name_match = any(word in username_part for word in author_words)
            return name_match
    
    # LinkedIn验证
    elif platform == 'linkedin':
        if 'linkedin.com/in/' in url_lower:
            # 排除目录页面
            if '/directory/' in url_lower:
                return False
            
            username_part = url_lower.split('/in/')[-1].split('/')[0].split('?')[0]
            
            # 检查用户名长度
            if len(username_part) < 3:
                return False
            
            # 检查是否包含作者名字的部分
            name_match = any(word in username_part for word in author_words)
            return name_match
    
    # GitHub验证
    elif platform == 'github':
        if 'github.com/' in url_lower:
            # 排除组织和搜索页面
            if any(bad in url_lower for bad in ['/orgs/', '/search', '/topics/', '/trending']):
                return False
            
            username_part = url_lower.split('github.com/')[-1].split('/')[0].split('?')[0]
            
            if len(username_part) < 2:
                return False
            
            # GitHub用户名通常与作者名相关
            name_match = any(word in username_part for word in author_words)
            return name_match
    
    # Scholar验证
    elif platform == 'scholar':
        return 'citations?user=' in url_lower
    
    # 其他平台的基本验证
    return True

def extract_social_links_from_content(content: str, base_url: str = "") -> Dict[str, str]:
    """从页面内容中提取社交媒体链接 - 增强版"""
    social_links = {}
    
    # 更全面的社交媒体链接模式，包括更多变体
    patterns = {
        'scholar': [
            r'https?://scholar\.google\.com/citations\?user=([A-Za-z0-9_\-]+)',
            r'https?://scholar\.google\.com/citations\?hl=[^&]*&user=([A-Za-z0-9_\-]+)',
            r'scholar\.google\.com/citations\?user=([A-Za-z0-9_\-]+)',  # 无协议版本
        ],
        'github': [
            r'https?://github\.com/([A-Za-z0-9_\-]+)(?:/[^"\s]*)?',
            r'github\.com/([A-Za-z0-9_\-]+)',  # 无协议版本
        ],
        'linkedin': [
            r'https?://(?:www\.)?linkedin\.com/in/([A-Za-z0-9_\-]+)',
            r'linkedin\.com/in/([A-Za-z0-9_\-]+)',  # 无协议版本
        ],
        'twitter': [
            r'https?://(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)',
            r'(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)',  # 无协议版本
            r'@([A-Za-z0-9_]+)',  # @username 格式
        ],
        'orcid': [
            r'https?://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})',
            r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})',
        ],
        'openreview': [
            r'https?://openreview\.net/profile\?id=([A-Za-z0-9_\-\.%~]+)',
            r'openreview\.net/profile\?id=([A-Za-z0-9_\-\.%~]+)',
        ],
        'huggingface': [
            r'https?://huggingface\.co/([A-Za-z0-9_\-]+)',
            r'huggingface\.co/([A-Za-z0-9_\-]+)',
        ],
    }
    
    print(f"[Regex Debug] Content length: {len(content)} characters")
    
    for platform, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f"[Regex Match] {platform}: {pattern} found {len(matches)} matches: {matches[:3]}")  # 显示前3个匹配
                
                # 取第一个匹配的链接，但排除明显错误的
                valid_match = None
                for match in matches:
                    # 对Twitter特殊处理@username格式
                    if platform == 'twitter' and pattern.startswith(r'@'):
                        # 排除过短或明显不是用户名的匹配
                        if len(match) >= 3 and not any(bad in match.lower() for bad in ['http', 'www', 'com']):
                            valid_match = match
                            break
                    else:
                        # 其他平台的常规处理
                        if match and len(match) > 2:
                            valid_match = match
                            break
                
                if valid_match:
                    # 构建完整URL
                    if platform == 'scholar':
                        social_links[platform] = f"https://scholar.google.com/citations?user={valid_match}"
                    elif platform == 'github':
                        social_links[platform] = f"https://github.com/{valid_match}"
                    elif platform == 'linkedin':
                        social_links[platform] = f"https://www.linkedin.com/in/{valid_match}"
                    elif platform == 'twitter':
                        social_links[platform] = f"https://x.com/{valid_match}"
                    elif platform == 'orcid':
                        social_links[platform] = f"https://orcid.org/{valid_match}"
                    elif platform == 'openreview':
                        social_links[platform] = f"https://openreview.net/profile?id={valid_match}"
                    elif platform == 'huggingface':
                        social_links[platform] = f"https://huggingface.co/{valid_match}"
                    
                    print(f"[Regex Success] {platform}: {social_links[platform]}")
                    break  # 找到有效匹配后跳出内层循环
    
    print(f"[Regex Summary] Extracted {len(social_links)} social links: {list(social_links.keys())}")
    return social_links

# ============================ PROFILE MERGING FUNCTIONS ============================

def process_homepage_candidate(candidate: ProfileCandidate, author_name: str, paper_title: str, 
                             profile: AuthorProfile, protected_platforms: set, llm_ext) -> bool:
    """
    处理homepage类型的候选者
    
    Args:
        candidate: 候选者信息
        author_name: 目标作者姓名
        paper_title: 论文标题
        profile: 当前作者档案
        protected_platforms: 受保护的平台集合
        llm_ext: LLM客户端
        
    Returns:
        是否成功处理
    """
    print(f"[Homepage Candidate] Processing: {candidate.url}")
    
    # 1. 检查URL重定向
    final_url, redirected = check_url_redirect(candidate.url)
    working_url = final_url if redirected else candidate.url
    
    if redirected:
        print(f"[Homepage Redirect] Using final URL: {working_url}")
    
    # 2. 预验证身份（使用最终URL）
    is_target, confidence, reason = verify_homepage_identity_before_fetch(
        author_name, paper_title, working_url, candidate.snippet, llm_ext
    )
    
    print(f"[Homepage Identity] {is_target} (conf: {confidence:.2f}, reason: {reason})")
    
    if not is_target or confidence < 0.6:
        print(f"[Homepage Rejected] Identity verification failed")
        return False
    
    # 3. 身份验证通过，进行全面抓取（使用最终URL）
    print(f"[Homepage] Identity verified, starting comprehensive fetch")
    homepage_result = fetch_homepage_comprehensive(working_url, author_name, max_chars=50000)
    
    if not homepage_result['success']:
        print(f"[Homepage] Comprehensive fetch failed, using fallback")
        txt = fetch_text(working_url, max_chars=30000, snippet=candidate.snippet)
        if not txt or len(txt) < config.MIN_TEXT_LENGTH:
            return False
    else:
        txt = homepage_result['text_content']
        
        # 3. 直接从HTML提取的高质量链接
        html_social_links = homepage_result['social_platforms']
        html_emails = homepage_result['emails']
        
        print(f"[Homepage Integration] Adding {len(html_social_links)} social links and {len(html_emails)} emails")
        
        # 添加社交平台链接（最高优先级，但需要验证）
        for platform, url in html_social_links.items():
            if platform not in profile.platforms and validate_social_link_for_author(platform, url, author_name):
                profile.platforms[platform] = url
                protected_platforms.add(platform)
                print(f"[Homepage Direct] Added {platform}: {url}")
            elif not validate_social_link_for_author(platform, url, author_name):
                print(f"[Homepage Rejected] Invalid {platform} link: {url}")
        
        # 添加邮箱（经过过滤）
        for email in html_emails:
            if email not in profile.emails and is_email_relevant_to_author(email, author_name):
                profile.emails.append(email)
                print(f"[Homepage Direct] Added email: {email}")
    
    # 4. LLM内容提取
    if len(txt) >= config.MIN_TEXT_LENGTH:
        dump = txt[:25000] if homepage_result['success'] else txt[:15000]
        prompt = HOMEPAGE_EXTRACT_PROMPT(author_name, dump)
        
        try:
            ext = llm.safe_structured(llm_ext, prompt, schemas.LLMAuthorProfileSpec)
            if ext:
                # 处理提取的信息
                process_extracted_profile_info(ext, candidate.url, author_name, profile, protected_platforms, is_homepage=True)
                return True
        except Exception as e:
            print(f"[Homepage LLM] Extraction failed: {e}")
    
    return False

def process_regular_candidate(candidate: ProfileCandidate, author_name: str, 
                            profile: AuthorProfile, protected_platforms: set, llm_ext) -> bool:
    """
    处理非homepage类型的候选者
    
    Args:
        candidate: 候选者信息
        author_name: 目标作者姓名
        profile: 当前作者档案
        protected_platforms: 受保护的平台集合
        llm_ext: LLM客户端
        
    Returns:
        是否成功处理
    """
    # 1. 确定平台类型
    host = domain_of(candidate.url)
    platform_type = determine_platform_type(candidate.url, host)
    
    if not platform_type:
        return False
    
    # 2. 抓取内容
    max_chars = config.FETCH_MAX_CHARS
    txt = fetch_text(candidate.url, max_chars=max_chars, snippet=candidate.snippet)
    
    if not txt or len(txt) < config.MIN_TEXT_LENGTH:
        print(f"[Regular Candidate] Failed to fetch sufficient content from {candidate.url}")
        return False
    
    print(f"[Regular Candidate] Fetched {len(txt)} characters from {candidate.url}")
    
    # 3. 对社交平台进行身份验证
    if platform_type in ['linkedin', 'twitter', 'researchgate']:
        is_target, confidence, reason = verify_profile_identity(
            author_name, platform_type, candidate.url, txt[:1000], llm_ext
        )
        print(f"[Profile Verification] {platform_type}: {is_target} (conf: {confidence:.2f})")
        
        if not is_target or confidence < 0.6:
            print(f"[Profile Rejected] {platform_type} profile rejected")
            return False
    
    # 4. 更新平台URL
    if platform_type not in protected_platforms:
        update_platform_url(profile, platform_type, candidate.url, author_name)
    else:
        print(f"[Skipped Platform] {platform_type} already protected by homepage")
    
    # 5. LLM内容提取
    dump = txt[:8000]
    platform_hint = get_platform_hint(host)
    prompt = PROFILE_EXTRACT_PROMPT(author_name, dump, platform_hint)
    
    try:
        ext = llm.safe_structured(llm_ext, prompt, schemas.LLMAuthorProfileSpec)
        if ext:
            process_extracted_profile_info(ext, candidate.url, author_name, profile, protected_platforms, is_homepage=False)
            return True
    except Exception as e:
        print(f"[Regular LLM] Extraction failed for {candidate.url}: {e}")
    
    return False

def determine_platform_type(url: str, host: str) -> str:
    """确定平台类型 - 增强homepage检测"""
    url_lower = url.lower()
    
    # 权威学术平台
    if 'orcid.org' in host:
        return 'orcid'
    elif 'openreview.net' in host:
        return 'openreview'
    elif 'scholar.google.' in host:
        return 'scholar'
    elif 'semanticscholar.org' in host:
        return 'semanticscholar'
    elif 'dblp.org' in host:
        return 'dblp'
    
    # 机构网站
    elif host.endswith('.edu') or host.endswith('.ac.nz') or host.endswith('.ac.uk'):
        return 'university'
    
    # 个人网站检测 - 增强版
    elif 'github.io' in host:
        return 'homepage'
    elif any(personal_indicator in host for personal_indicator in [
        'personal', 'homepage', 'home', 'about', 'profile'
    ]):
        return 'homepage'
    elif any(domain_pattern in host for domain_pattern in [
        '.com', '.org', '.net', '.me', '.io'
    ]) and not any(platform in host for platform in [
        'github.com', 'linkedin.com', 'twitter.com', 'x.com', 'facebook.com',
        'instagram.com', 'youtube.com', 'medium.com', 'reddit.com'
    ]):
        # 可能是个人域名，进一步检查URL路径
        if any(indicator in url_lower for indicator in [
            'personal', 'homepage', 'home', 'about', 'profile', 'cv', 'resume'
        ]) or len(host.split('.')) <= 2:  # 简单域名如 yuzheyang.com
            return 'homepage'
    
    # 代码和专业平台
    elif 'github.com' in host:
        return 'github'
    elif 'huggingface.co' in host:
        return 'huggingface'
    elif 'researchgate.net' in host:
        return 'researchgate'
    
    # 社交媒体
    elif 'x.com' in host or 'twitter.com' in host:
        return 'twitter'
    elif 'linkedin.com' in host:
        return 'linkedin'
    
    # 排除明显不相关的网站
    elif any(blocked in host for blocked in [
        'wikipedia', 'news', 'blog', 'forum', 'reddit', 'youtube', 'facebook'
    ]):
        return None
    
    return None

def get_platform_hint(host: str) -> str:
    """获取平台提示"""
    if 'openreview.net' in host:
        return "openreview"
    elif 'scholar.google.' in host:
        return "google_scholar"
    elif 'orcid.org' in host:
        return "orcid"
    elif 'semanticscholar.org' in host:
        return "semantic_scholar"
    elif host.endswith('.edu') or host.endswith('.ac.uk') or host.endswith('.ac.nz'):
        return "university"
    elif 'github.com' in host:
        return "github"
    return "generic"

def process_extracted_profile_info(ext, url: str, author_name: str, profile: AuthorProfile, 
                                 protected_platforms: set, is_homepage: bool = False):
    """处理LLM提取的profile信息"""
    # 处理个人主页URL
    personal_homepage = getattr(ext, 'personal_homepage', '') or getattr(ext, 'homepage_url', '')
    if personal_homepage == url:
        personal_homepage = None  # 当前页面不是个人主页
    
    if is_homepage and not personal_homepage:
        personal_homepage = url
    
    if 'github.io' in url and not profile.homepage_url:
        profile.homepage_url = url
    
    # 处理社交链接
    social_links = getattr(ext, 'social_links', {}) or {}
    
    if is_homepage:
        # 个人网站：强制更新所有社交链接（但需要验证）
        for social_platform, social_url in social_links.items():
            if social_url and social_url != url and validate_social_link_for_author(social_platform, social_url, author_name):
                profile.platforms[social_platform] = social_url
                protected_platforms.add(social_platform)
                print(f"[Protected LLM] {social_platform}: {social_url}")
            elif social_url and not validate_social_link_for_author(social_platform, social_url, author_name):
                print(f"[LLM Rejected] Invalid {social_platform} link: {social_url}")
        
        # 从内容提取额外链接（如果还没有足够的链接）
        if len(social_links) < 3:  # 如果LLM提取的链接不够
            extracted_links = extract_social_links_from_content(fetch_text(url, max_chars=10000))
            for social_platform, social_url in extracted_links.items():
                if social_platform not in profile.platforms:
                    profile.platforms[social_platform] = social_url
                    protected_platforms.add(social_platform)
                    print(f"[Protected HTML] {social_platform}: {social_url}")
    else:
        # 非个人网站：只有在平台未被保护时才更新
        for social_platform, social_url in social_links.items():
            if social_url and social_url != url and social_platform not in protected_platforms:
                update_platform_url(profile, social_platform, social_url, author_name)
    
    # 创建incoming profile并合并
    cleaned_aliases = clean_aliases(getattr(ext, 'aliases', []) or [], author_name)
    
    incoming = AuthorProfile(
        name=getattr(ext, 'name', '') or author_name,
        aliases=cleaned_aliases,
        platforms={}, ids={}, 
        homepage_url=personal_homepage,
        affiliation_current=getattr(ext, 'affiliation_current','') or None,
        emails=list(getattr(ext, 'emails', []) or []),
        interests=list(getattr(ext, 'interests', []) or []),
        selected_publications=list(getattr(ext, 'selected_publications', []) or []),
        confidence=0.4,
        notable_achievements=list(getattr(ext, 'notable_achievements', []) or []),
        social_impact=getattr(ext, 'social_impact', '') or None,
        career_stage=getattr(ext, 'career_stage', '') or None,
        overall_score=0.0
    )
    
    # 合并profiles，但不返回值因为profile是引用传递
    merged = merge_profiles(profile, incoming)
    # 更新profile的属性
    for attr in ['name', 'aliases', 'platforms', 'ids', 'homepage_url', 'affiliation_current', 
                 'emails', 'interests', 'selected_publications', 'notable_achievements', 
                 'social_impact', 'career_stage', 'confidence']:
        setattr(profile, attr, getattr(merged, attr))

def clean_aliases(raw_aliases: List[str], author_name: str) -> List[str]:
    """清理aliases，只保留真正的作者别名"""
    cleaned_aliases = []
    author_words = set(author_name.lower().split())
    
    for alias in raw_aliases:
        if alias and alias != author_name:
            alias_words = set(alias.lower().split())
            # 如果别名与作者名有重叠词汇，可能是真正的别名
            if len(alias_words & author_words) > 0 or len(alias.split()) <= 3:
                cleaned_aliases.append(alias)
    
    return cleaned_aliases[:5]  # 限制别名数量

def merge_profiles(base: AuthorProfile, incoming: AuthorProfile) -> AuthorProfile:
    """Merge two author profiles with trust ranking"""
    # Merge platforms and IDs
    for k, v in incoming.platforms.items():
        base.platforms.setdefault(k, v)
    for k, v in incoming.ids.items():
        base.ids.setdefault(k, v)
    
    # 合并homepage_url - 优先保留非平台URL的个人网站
    if incoming.homepage_url:
        if not base.homepage_url:
            base.homepage_url = incoming.homepage_url
        elif 'github.io' in incoming.homepage_url and 'github.io' not in base.homepage_url:
            # 个人域名优于github.io
            pass
        elif 'github.io' in base.homepage_url and 'github.io' not in incoming.homepage_url:
            # 个人域名优于github.io
            base.homepage_url = incoming.homepage_url
    
    # Merge names and aliases
    if not base.name and incoming.name:
        base.name = incoming.name
    for a in incoming.aliases:
        if a and a not in base.aliases:
            base.aliases.append(a)

    # Merge basic fields (prefer non-empty)
    if not base.affiliation_current and incoming.affiliation_current:
        base.affiliation_current = incoming.affiliation_current
    if not base.social_impact and incoming.social_impact:
        base.social_impact = incoming.social_impact
    if not base.career_stage and incoming.career_stage:
        base.career_stage = incoming.career_stage
        
    # Merge list fields with deduplication
    for e in incoming.emails:
        if e and e not in base.emails:
            base.emails.append(e)
    for i in incoming.interests:
        if i and i not in base.interests:
            base.interests.append(i)
    
    # Merge notable achievements
    if hasattr(incoming, 'notable_achievements') and incoming.notable_achievements:
        for achievement in incoming.notable_achievements:
            if achievement and achievement not in base.notable_achievements:
                base.notable_achievements.append(achievement)

    # Merge publications with deduplication
    def key(pub):
        return re.sub(r'\s+', ' ', (pub.get('title','') or '').strip().lower())

    seen = {key(p) for p in base.selected_publications}
    for p in incoming.selected_publications:
        if key(p) not in seen:
            base.selected_publications.append(p)
            seen.add(key(p))

    # Update confidence
    base.confidence = min(1.0, base.confidence + 0.1)
    return base

# ============================ MAIN DISCOVERY FUNCTIONS ============================

def discover_author_profile(first_author: str, paper_title: str, aliases: List[str] = None,
                          k_queries: int = 40, author_id: str = None) -> AuthorProfile:
    """Main function to discover comprehensive author profile"""
    aliases = aliases or []
    queries = build_author_queries(first_author, paper_title, aliases)
    queries = queries[:k_queries]

    # Phase 1: Search and aggregate results
    serp = []
    for q in queries:
        res = searxng_search(q, engines=['google'], pages=1, k_per_query=6)
        serp.extend(res)
        safe_sleep(0.05)

    # Deduplicate URLs
    seen, items = set(), []
    for r in serp:
        u = r.get('url') or ''
        if u and u not in seen:
            seen.add(u)
            items.append(r)

    # Phase 2: Score and filter candidates
    cand: List[ProfileCandidate] = []
    for it in items:
        sc = score_candidate(it, first_author, paper_title)
        cand.append(ProfileCandidate(
            url=it.get('url',''), title=it.get('title',''),
            snippet=it.get('snippet',''), score=sc
        ))

    # Phase 3: 两阶段LLM评估
    llm_sel = llm.get_llm("select", temperature=0.2)
    picked: List[ProfileCandidate] = []

    for c in cand:
        # 高分直接通过
        if c.score >= 2:
            c.should_fetch = True
            c.reason = "High rule-based score"
        # 极低分直接丢弃
        elif c.score <= 0.25:
            c.should_fetch = False
            c.reason = "Low rule-based score"
        else:
            # 第一阶段：判断是否包含作者信息
            prompt_has_info = PROMPT_HAS_AUTHOR_INFO(first_author, c.title, c.url, c.snippet)
            try:
                r1 = llm.safe_structured(llm_sel, prompt_has_info, schemas.LLMSelectSpecHasAuthorInfo)
                has_author_info = bool(r1 and getattr(r1, 'has_author_info', False))
                
                if not has_author_info:
                    c.should_fetch = False
                    c.reason = "No author info detected"
                else:
                    # 第二阶段：判断抓取价值
                    prompt_relevance = PROMPT_PROFILE_RELEVANCE(first_author, paper_title, c.title, c.url, c.snippet)
                    r2 = llm.safe_structured(llm_sel, prompt_relevance, schemas.LLMSelectSpecWithValue)
                    c.should_fetch = bool(r2 and getattr(r2, 'should_fetch', False))
                    c.reason = getattr(r2, 'reason', 'LLM evaluation')
            except Exception as e:
                # LLM失败时使用规则兜底
                c.should_fetch = c.score >= 0.5
                c.reason = f"LLM failed, rule fallback: {e}"

        if c.should_fetch:
            picked.append(c)

    # Phase 4: Initialize base profile and fetch papers from Semantic Scholar
    profile = AuthorProfile(
        name=first_author, aliases=aliases[:], platforms={}, ids={},
        homepage_url=None, affiliation_current=None, emails=[],
        interests=[], selected_publications=[], confidence=0.3,
        notable_achievements=[], social_impact=None, career_stage=None, overall_score=0.0
    )
    
    # 如果提供了author_id，直接从Semantic Scholar获取论文和profile信息
    if author_id:
        try:
            from semantic_paper_search import SemanticScholarClient
            s2_client = SemanticScholarClient()
            
            # 获取作者的详细信息
            s2_profile = s2_client.get_author_profile_info(author_id)
            if s2_profile:
            #     if s2_profile.get('homepage'):
            #         profile.homepage_url = s2_profile['homepage']
                if s2_profile.get('affiliations'):
                    profile.affiliation_current = s2_profile['affiliations'][0].get('name', '') if s2_profile['affiliations'] else None
                if s2_profile.get('aliases'):
                    profile.aliases.extend([alias for alias in s2_profile['aliases'] if alias not in profile.aliases])
                
                # 设置社交影响力信息
                h_index = s2_profile.get('hIndex', 0)
                citation_count = s2_profile.get('citationCount', 0)
                paper_count = s2_profile.get('paperCount', 0)
                
                if h_index > 0 or citation_count > 0:
                    profile.social_impact = f"h-index: {h_index}, citations: {citation_count}, papers: {paper_count}"
            
            # 获取作者的论文
            papers = s2_client.get_author_papers(author_id, limit=50, sort="citationCount")
            if papers:
                profile.selected_publications = [
                    {
                        'title': paper['title'],
                        'year': paper.get('year'),
                        'venue': paper.get('venue', ''),
                        'url': paper.get('url', ''),
                        'citations': paper.get('citationCount', 0)
                    }
                    for paper in papers[:20]  # 限制为前20篇
                ]
                
                print(f"[S2 Integration] Added {len(profile.selected_publications)} papers from Semantic Scholar")
            
        except Exception as e:
            print(f"[S2 Integration] Failed to fetch from Semantic Scholar: {e}")
    
    
    # 记录从个人网站提取的高质量平台链接，保护它们不被覆盖
    protected_platforms = set()

    # Phase 5: Process candidates using modular approach
    llm_ext = llm.get_llm("extract", temperature=0.1)
    
    # 按优先级排序候选者：个人网站优先
    def get_candidate_priority(candidate):
        url = candidate.url.lower()
        if 'github.io' in url or any(indicator in url for indicator in ['personal', 'homepage']):
            return 1  # 最高优先级：个人网站
        elif any(platform in url for platform in ['x.com', 'twitter.com', 'linkedin.com','orcid.org', 'openreview.net']):
            return 2  # 高优先级：权威学术平台
        elif any(platform in url for platform in ['researchgate.net', 'github.com', 'huggingface.co','scholar.google.', 'semanticscholar.org']):
            return 3  # 中高优先级：学术搜索平台
        else:
            return 4  # 低优先级：其他平台
    
    picked_sorted = sorted(picked[:20], key=get_candidate_priority)
    
    # 统计处理结果
    processed_count = 0
    homepage_processed = False

    for c in picked_sorted:
        # 5.1: Extract IDs from URL (fast path)
        ids = extract_ids_from_url(c.url)
        for k, v in ids.items():
            profile.ids.setdefault(k, v)

        # 5.2: 确定是否为个人网站
        host = domain_of(c.url)
        platform_type = determine_platform_type(c.url, host)
        is_homepage = platform_type == 'homepage' or 'github.io' in c.url
        
        # 5.3: 模块化处理
        success = False
        
        if is_homepage and not homepage_processed:
            # 个人网站处理：包含身份预验证
            success = process_homepage_candidate(
                c, first_author, paper_title, profile, protected_platforms, llm_ext
            )
            if success:
                homepage_processed = True
                print(f"[Homepage Success] Successfully processed homepage: {c.url}")
        elif not is_homepage:
            # 非个人网站处理
            success = process_regular_candidate(
                c, first_author, profile, protected_platforms, llm_ext
            )
        else:
            print(f"[Homepage Skip] Already processed a homepage, skipping: {c.url}")
        
        if success:
            processed_count += 1
            print(f"[Candidate Success] Processed {processed_count} candidates so far")
        
        # 限制处理数量以提高效率
        if processed_count >= 100:  # 最多处理10个成功的候选者
            print(f"[Processing Limit] Reached maximum candidate limit")
            break

    # Phase 6: 最终档案精炼
    profile = refine_author_profile(profile, first_author)
    
    # Phase 7: 计算综合评分
    profile.overall_score = calculate_overall_score(profile)
    
    return profile

# ============================ PROFILE REFINEMENT ============================

def enhance_career_stage_detection(profile: AuthorProfile) -> str:
    """
    增强的career stage检测，从多个来源综合判断
    
    Args:
        profile: 作者档案
        
    Returns:
        推断的career stage
    """
    stage_indicators = []
    
    # 1. 从affiliation中提取线索
    if profile.affiliation_current:
        affiliation_lower = profile.affiliation_current.lower()
        
        if any(keyword in affiliation_lower for keyword in ['professor', 'prof']):
            if 'assistant' in affiliation_lower:
                stage_indicators.append(('assistant_prof', 0.8))
            elif 'associate' in affiliation_lower:
                stage_indicators.append(('associate_prof', 0.8))
            elif 'full' in affiliation_lower or 'chair' in affiliation_lower:
                stage_indicators.append(('full_prof', 0.8))
            else:
                stage_indicators.append(('professor', 0.6))
        elif any(keyword in affiliation_lower for keyword in ['postdoc', 'postdoctoral', 'research fellow']):
            stage_indicators.append(('postdoc', 0.8))
        elif any(keyword in affiliation_lower for keyword in ['phd student', 'doctoral student', 'graduate student']):
            stage_indicators.append(('phd_student', 0.8))
        elif any(keyword in affiliation_lower for keyword in ['researcher', 'scientist']):
            if any(company in affiliation_lower for company in ['google', 'microsoft', 'amazon', 'meta', 'openai', 'anthropic']):
                stage_indicators.append(('industry_researcher', 0.7))
            else:
                stage_indicators.append(('researcher', 0.6))
        elif any(keyword in affiliation_lower for keyword in ['engineer', 'developer', 'manager']):
            stage_indicators.append(('industry', 0.7))
    
    # 2. 从notable achievements中提取线索
    for achievement in profile.notable_achievements:
        achievement_lower = achievement.lower()
        
        if any(keyword in achievement_lower for keyword in ['dissertation award', 'phd thesis']):
            stage_indicators.append(('recent_phd', 0.6))
        elif any(keyword in achievement_lower for keyword in ['young researcher', 'rising star', 'early career']):
            stage_indicators.append(('early_career', 0.7))
        elif any(keyword in achievement_lower for keyword in ['fellow', 'distinguished']):
            stage_indicators.append(('senior_researcher', 0.8))
    
    # 3. 从social impact中提取线索
    if profile.social_impact:
        impact_lower = profile.social_impact.lower()
        
        # 解析h-index和citations来推断career stage
        import re
        h_index_match = re.search(r'h-?index[:\s]*(\d+)', impact_lower)
        citation_match = re.search(r'citation[s]?[:\s]*(\d+)', impact_lower)
        paper_match = re.search(r'paper[s]?[:\s]*(\d+)', impact_lower)
        
        h_index = int(h_index_match.group(1)) if h_index_match else 0
        citations = int(citation_match.group(1)) if citation_match else 0
        papers = int(paper_match.group(1)) if paper_match else 0
        
        # 根据学术指标推断career stage
        if h_index >= 30 or citations >= 5000:
            stage_indicators.append(('senior_researcher', 0.7))
        elif h_index >= 15 or citations >= 1000:
            stage_indicators.append(('mid_career', 0.6))
        elif h_index >= 5 or citations >= 200:
            stage_indicators.append(('early_career', 0.6))
        elif papers <= 5 and citations <= 100:
            stage_indicators.append(('student_or_early', 0.5))
    
    # 4. 综合判断
    if not stage_indicators:
        return "unknown"
    
    # 按置信度排序，选择最可能的stage
    stage_indicators.sort(key=lambda x: x[1], reverse=True)
    best_stage, best_confidence = stage_indicators[0]
    
    # 如果有多个高置信度的指标，进行进一步判断
    high_confidence_stages = [stage for stage, conf in stage_indicators if conf >= 0.7]
    
    if len(high_confidence_stages) > 1:
        # 优先级：教授 > 研究员 > 博士后 > 学生
        priority_order = ['full_prof', 'associate_prof', 'assistant_prof', 'professor', 
                         'senior_researcher', 'industry_researcher', 'researcher', 
                         'postdoc', 'phd_student', 'student_or_early']
        
        for priority_stage in priority_order:
            if priority_stage in high_confidence_stages:
                return priority_stage
    
    return best_stage

def refine_author_profile(profile: AuthorProfile, target_author: str) -> AuthorProfile:
    """最终精炼作者档案，确保数据质量"""
    
    # 1. 清理aliases - 移除明显不相关的名字
    target_words = set(target_author.lower().split())
    refined_aliases = []
    
    for alias in profile.aliases:
        if not alias or alias == profile.name:
            continue
            
        alias_words = set(alias.lower().split())
        
        # 更严格的别名检查
        is_valid_alias = False
        
        # 1. 检查是否有共同的实质性词汇（长度>2）
        common_words = [word for word in (alias_words & target_words) if len(word) > 2]
        if len(common_words) > 0:
            is_valid_alias = True
        
        # 2. 检查是否是名字的部分或变体
        target_first = target_author.split()[0].lower() if target_author.split() else ""
        target_last = target_author.split()[-1].lower() if len(target_author.split()) > 1 else ""
        
        if (target_first and target_first in alias.lower()) or (target_last and target_last in alias.lower()):
            is_valid_alias = True
        
        # 3. 排除明显不相关的名字
        if any(bad_indicator in alias.lower() for bad_indicator in ['rex', 'cook', 'evans', 'dante', 'ortega', 'camerino']):
            is_valid_alias = False
        
        # 4. 排除过长的名字（可能是其他人）
        if len(alias.split()) > 4:
            is_valid_alias = False
        
        if is_valid_alias:
            refined_aliases.append(alias)
    
    profile.aliases = refined_aliases[:3]  # 限制为最多3个别名
    
    # 2. 验证和清理平台链接
    verified_platforms = {}
    for platform, url in profile.platforms.items():
        if url and url.startswith('http') and len(url) > 10:
            # 基本URL验证
            verified_platforms[platform] = url
    
    profile.platforms = verified_platforms
    
    # 3. 清理兴趣领域 - 去重和规范化
    refined_interests = []
    seen_interests = set()
    
    for interest in profile.interests:
        if interest:
            # 规范化兴趣描述
            normalized = interest.strip().lower()
            if normalized not in seen_interests and len(normalized) > 2:
                seen_interests.add(normalized)
                refined_interests.append(interest.strip())
    
    profile.interests = refined_interests[:8]  # 限制兴趣数量
    
    # 4. 清理论文列表
    refined_publications = []
    seen_titles = set()
    
    for pub in profile.selected_publications:
        if isinstance(pub, dict) and pub.get('title'):
            title_normalized = pub['title'].lower().strip()
            if title_normalized not in seen_titles:
                seen_titles.add(title_normalized)
                refined_publications.append(pub)
    
    # 限制论文数量 to 10
    profile.selected_publications = refined_publications[:10]  
    
    # 5. 清理Notable成就
    refined_achievements = []
    for achievement in profile.notable_achievements:
        if achievement and len(achievement.strip()) > 5:
            refined_achievements.append(achievement.strip())
    
    # 限制成就数量 to 10
    profile.notable_achievements = refined_achievements[:10] 
    
    # 6. 增强career stage检测
    if not profile.career_stage or profile.career_stage == "assistant_prof":  # 如果没有或者是默认值
        enhanced_stage = enhance_career_stage_detection(profile)
        if enhanced_stage and enhanced_stage != "unknown":
            profile.career_stage = enhanced_stage
            print(f"[Enhanced Career Stage] Updated to: {enhanced_stage}")
    
    return profile

# ============================ SCORING SYSTEM ============================

def calculate_overall_score(profile: AuthorProfile) -> float:
    """计算作者的综合评分 (0-100)"""
    score = 0.0
    
    # 1. 平台权威性评分 (0-25分)
    platform_score = 0
    platform_weights = {
        'orcid': 8, 'openreview': 7, 'scholar': 6, 'semanticscholar': 5, 
        'dblp': 4, 'university': 6, 'github': 3, 'homepage': 4
    }
    for platform in profile.platforms:
        if platform in platform_weights:
            platform_score += platform_weights[platform]
    score += min(25, platform_score)
    
    # 2. 信息完整性评分 (0-20分)
    completeness = 0
    if profile.affiliation_current: completeness += 4
    if profile.emails: completeness += 3
    if profile.interests: completeness += 4
    if profile.homepage_url: completeness += 3
    if len(profile.aliases) > 0: completeness += 2
    if len(profile.selected_publications) > 0: completeness += 4
    score += completeness
    
    # 3. Notable成就评分 (0-25分)
    notable_score = 0
    if profile.notable_achievements:
        for achievement in profile.notable_achievements:
            achievement_lower = achievement.lower()
            if any(keyword in achievement_lower for keyword in 
                   ['best paper', 'outstanding paper', 'award']):
                notable_score += 8
            elif any(keyword in achievement_lower for keyword in 
                     ['fellow', 'ieee fellow', 'acm fellow']):
                notable_score += 10
            elif any(keyword in achievement_lower for keyword in 
                     ['rising star', 'young researcher']):
                notable_score += 6
            elif any(keyword in achievement_lower for keyword in 
                     ['keynote', 'invited speaker']):
                notable_score += 5
            elif any(keyword in achievement_lower for keyword in 
                     ['startup', 'founder', 'entrepreneur']):
                notable_score += 4
            else:
                notable_score += 2
    score += min(25, notable_score)
    
    # 4. 学术影响力评分 (0-20分)
    impact_score = 0
    if profile.social_impact:
        impact_text = profile.social_impact.lower()
        # 解析h-index
        import re
        h_index_match = re.search(r'h-?index[:\s]*(\d+)', impact_text)
        if h_index_match:
            h_index = int(h_index_match.group(1))
            if h_index >= 50: impact_score += 20
            elif h_index >= 30: impact_score += 15
            elif h_index >= 20: impact_score += 12
            elif h_index >= 10: impact_score += 8
            elif h_index >= 5: impact_score += 5
        
        # 解析引用数
        citation_match = re.search(r'citation[s]?[:\s]*(\d+)', impact_text)
        if citation_match:
            citations = int(citation_match.group(1))
            if citations >= 10000: impact_score += 10
            elif citations >= 5000: impact_score += 8
            elif citations >= 1000: impact_score += 6
            elif citations >= 500: impact_score += 4
            elif citations >= 100: impact_score += 2
    
    # 论文数量作为影响力指标
    pub_count = len(profile.selected_publications)
    if pub_count >= 20: impact_score += 8
    elif pub_count >= 10: impact_score += 6
    elif pub_count >= 5: impact_score += 4
    elif pub_count >= 3: impact_score += 2
    
    score += min(20, impact_score)
    
    # 5. 职业阶段调整 (0-10分)
    stage_score = 0
    if profile.career_stage:
        stage_lower = profile.career_stage.lower()
        if 'full_prof' in stage_lower or 'professor' in stage_lower:
            stage_score += 10
        elif 'associate_prof' in stage_lower or 'associate professor' in stage_lower:
            stage_score += 8
        elif 'assistant_prof' in stage_lower or 'assistant professor' in stage_lower:
            stage_score += 6
        elif 'postdoc' in stage_lower:
            stage_score += 4
        elif 'phd' in stage_lower or 'student' in stage_lower:
            stage_score += 2
        elif 'industry' in stage_lower:
            stage_score += 7
    score += stage_score
    
    return min(100.0, score)

# ============================ ADDITIONAL PUBLICATIONS FUNCTIONS ============================

def fetch_author_publications_via_s2(author_id: str, k: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch additional publications via Semantic Scholar API
    """
    publications = []

    try:
        from semantic_paper_search import SemanticScholarClient
        s2_client = SemanticScholarClient()
        
        papers = s2_client.get_author_papers(author_id, limit=k, sort="citationCount")
        
        for paper in papers:
            pub_info = {
                'title': paper.get('title', ''),
                'year': paper.get('year'),
                'venue': paper.get('venue', ''),
                'url': paper.get('url', ''),
                'citations': paper.get('citationCount', 0),
                'authors': paper.get('authors', [])
            }
            publications.append(pub_info)
            
        print(f"[S2 Publications] Fetched {len(publications)} papers for author {author_id}")
        
    except Exception as e:
        print(f"[S2 publications] Error: {e}")

    return publications

def fetch_author_pubs_fallback_arxiv(author_name: str, k: int = 10) -> List[Dict[str, Any]]:
    """Fallback publication discovery via arXiv"""
    publications = []

    try:
        # Search arXiv for author publications
        query = f'site:arxiv.org "{author_name}"'
        results = searxng_search(query, engines=config.SEARXNG_ENGINES, pages=2, k_per_query=10)

        for result in results[:k]:
            url = result.get('url', '')
            if 'arxiv.org' in url and ('abs' in url or 'pdf' in url):
                # Extract basic info from snippet
                title = result.get('title', '')
                snippet = result.get('snippet', '')

                pub_info = {
                    'title': title,
                    'url': url,
                    'venue': 'arXiv',
                    'year': None  # Would need more sophisticated extraction
                }
                publications.append(pub_info)

    except Exception as e:
        print(f"[arXiv publications] Error: {e}")

    return publications

# ============================ COMPREHENSIVE HOMEPAGE FETCHER ============================

def fetch_homepage_comprehensive(url: str, author_name: str = "", max_chars: int = 50000) -> Dict[str, Any]:
    """
    专门处理homepage链接的全面抓取函数
    从整个HTML内容中提取各种社交媒体链接和其他作者信息

    Args:
        url: homepage URL
        author_name: 作者姓名（用于验证和匹配）
        max_chars: 最大字符限制

    Returns:
        Dict containing:
        - 'full_html': 完整的HTML内容
        - 'extracted_links': 提取的各种链接
        - 'emails': 邮箱列表
        - 'social_platforms': 社交媒体平台链接
        - 'text_content': 文本内容
        - 'title': 页面标题
    """
    print(f"[Homepage Fetcher] Starting comprehensive fetch for: {url}")

    result = {
        'full_html': '',
        'extracted_links': {},
        'emails': [],
        'social_platforms': {},
        'text_content': '',
        'title': '',
        'success': False
    }

    try:
        # 使用requests获取完整HTML内容
        r = requests.get(url, timeout=15, headers=config.UA)

        if not r.ok:
            print(f"[Homepage Fetcher] HTTP error {r.status_code} for {url}")
            return result

        html_content = r.text
        result['full_html'] = html_content[:max_chars]  # 限制大小但保留完整性
        result['success'] = True

        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 提取页面标题
        title = extract_title_unified(html_content)
        result['title'] = title
        print(f"[Homepage Fetcher] Extracted title: {title}")

        # 2. 提取所有链接
        all_links = extract_all_links_from_html(html_content, url)
        result['extracted_links'] = all_links

        # 3. 专门提取社交媒体平台链接
        social_platforms = extract_social_platforms_from_html(html_content, url)
        result['social_platforms'] = social_platforms
        print(f"[Homepage Fetcher] Found {len(social_platforms)} social platforms")

        # 4. 提取邮箱地址（带作者名过滤）
        emails = extract_emails_from_html(html_content, author_name)
        result['emails'] = emails
        print(f"[Homepage Fetcher] Found {len(emails)} email addresses")

        # 5. 提取主要文本内容（用于LLM处理）
        text_content = extract_main_text(html_content, url)
        result['text_content'] = text_content[:30000]  # 限制文本内容大小

        # 6. 打印提取结果摘要
        print(f"[Homepage Fetcher] Summary:")
        print(f"  - Title: {title}")
        print(f"  - Social platforms: {list(social_platforms.keys())}")
        print(f"  - Emails: {emails}")
        print(f"  - Total links found: {len(all_links)}")

        return result

    except Exception as e:
        print(f"[Homepage Fetcher] Error fetching {url}: {e}")
        return result


def extract_all_links_from_html(html_content: str, base_url: str = "") -> Dict[str, List[str]]:
    """
    从HTML内容中提取所有类型的链接

    Args:
        html_content: HTML内容
        base_url: 基础URL（用于相对链接转换）

    Returns:
        分类后的链接字典
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links = {
        'all': [],
        'mailto': [],
        'http': [],
        'https': [],
        'relative': []
    }

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()

        # 跳过空链接和JavaScript
        if not href or href.startswith('javascript:') or href == '#':
            continue

        links['all'].append(href)

        if href.startswith('mailto:'):
            links['mailto'].append(href)
        elif href.startswith('http://'):
            links['http'].append(href)
        elif href.startswith('https://'):
            links['https'].append(href)
        elif not href.startswith(('http://', 'https://', 'mailto:')):
            # 相对链接
            links['relative'].append(href)

    return links


def extract_social_platforms_from_html(html_content: str, base_url: str = "") -> Dict[str, str]:
    """
    从HTML内容中专门提取社交媒体和学术平台链接

    Args:
        html_content: HTML内容
        base_url: 基础URL

    Returns:
        平台名称到URL的映射字典
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    platforms = {}

    # 定义平台识别规则
    platform_patterns = {
        'scholar': [
            r'scholar\.google\.com/citations\?user=',
            r'scholar\.google\.com/citations/',
        ],
        'github': [
            r'github\.com/[A-Za-z0-9\-_]+',
        ],
        'twitter': [
            r'(?:x\.com|twitter\.com)/[A-Za-z0-9_]+',
        ],
        'linkedin': [
            r'linkedin\.com/in/[A-Za-z0-9\-_]+',
        ],
        'orcid': [
            r'orcid\.org/\d{4}-\d{4}-\d{4}-\d{4}',
        ],
        'openreview': [
            r'openreview\.net/profile\?id=',
        ],
        'semanticscholar': [
            r'semanticscholar\.org/author/',
        ],
        'dblp': [
            r'dblp\.org/pid/',
            r'dblp\.org/pers/',
        ],
        'researchgate': [
            r'researchgate\.net/profile/',
        ],
        'huggingface': [
            r'huggingface\.co/[A-Za-z0-9\-_]+',
        ]
    }

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()

        for platform, patterns in platform_patterns.items():
            for pattern in patterns:
                if re.search(pattern, href, re.IGNORECASE):
                    if platform not in platforms:  # 保留第一个匹配的链接
                        # 确保URL是完整的
                        if not href.startswith(('http://', 'https://')):
                            if base_url:
                                if href.startswith('/'):
                                    from urllib.parse import urljoin
                                    href = urljoin(base_url, href)
                                else:
                                    href = f"{base_url.rstrip('/')}/{href}"
                        platforms[platform] = href
                        print(f"[Platform Found] {platform}: {href}")
                        break

    return platforms


def extract_emails_from_html(html_content: str, author_name: str = "") -> List[str]:
    """
    从HTML内容中提取邮箱地址，并过滤掉明显不属于目标作者的邮箱

    Args:
        html_content: HTML内容
        author_name: 目标作者姓名，用于过滤

    Returns:
        过滤后的邮箱地址列表
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    emails = set()  # 使用set去重

    # 1. 从mailto链接中提取
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        if href.startswith('mailto:'):
            email = href[7:].split('?')[0]  # 移除可能的查询参数
            if '@' in email and is_email_relevant_to_author(email, author_name):
                emails.add(email.lower())

    # 2. 从文本内容中提取（使用正则表达式）
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    text_content = soup.get_text()
    found_emails = re.findall(email_pattern, text_content, re.IGNORECASE)

    for email in found_emails:
        if is_email_relevant_to_author(email, author_name):
            emails.add(email.lower())

    # 3. 从特定属性中提取（有些网站把邮箱放在data属性中）
    for tag in soup.find_all(attrs={'data-email': True}):
        email = tag.get('data-email', '').strip()
        if '@' in email and is_email_relevant_to_author(email, author_name):
            emails.add(email.lower())

    return list(emails)

def is_email_relevant_to_author(email: str, author_name: str) -> bool:
    """
    判断邮箱是否可能属于目标作者 - 增强版
    
    Args:
        email: 邮箱地址
        author_name: 目标作者姓名
        
    Returns:
        是否相关
    """
    if not author_name or not email:
        return False
    
    email_lower = email.lower().strip()
    
    # 排除明显的系统/通用邮箱
    system_emails = [
        'info@', 'admin@', 'support@', 'contact@', 'webmaster@', 
        'noreply@', 'no-reply@', 'help@', 'service@', 'office@',
        'secretary@', 'dept@', 'department@', 'marketing@', 'sales@'
    ]
    
    if any(email_lower.startswith(prefix) for prefix in system_emails):
        return False
    
    # 排除明显的垃圾邮箱或占位符
    if any(spam in email_lower for spam in ['****', 'xxx@', 'example@', 'test@', 'dummy@', 'fake@']):
        return False
    
    # 排除明显不是个人邮箱的地址
    if any(company in email_lower for company in [
        '@google.com', '@microsoft.com', '@amazon.com', '@meta.com', 
        '@apple.com', '@nvidia.com', '@openai.com', '@anthropic.com'
    ]):
        # 这些大公司邮箱通常不是学者的主要联系邮箱
        return False
    
    # 提取邮箱用户名和域名
    if '@' not in email_lower:
        return False
    
    email_username, email_domain = email_lower.split('@', 1)
    author_words = [word.lower() for word in author_name.split() if len(word) > 2]
    
    # 强匹配：邮箱用户名包含作者姓名的关键词
    name_match_score = 0
    for word in author_words:
        if word in email_username:
            name_match_score += 1
    
    # 如果有强名字匹配，直接接受
    if name_match_score >= len(author_words) * 0.5:
        return True
    
    # 检查是否是学术机构邮箱
    academic_domains = ['.edu', '.ac.uk', '.ac.nz', '.ac.jp', '.edu.cn', '.ac.cn']
    is_academic = any(domain in email_domain for domain in academic_domains)
    
    # 学术邮箱 + 有一定名字匹配度
    if is_academic and name_match_score > 0:
        return True
    
    # 如果没有名字匹配且不是学术邮箱，拒绝
    if name_match_score == 0 and not is_academic:
        return False
    
    # 其他情况保守接受
    return True

def validate_url_quality(url: str, platform: str, author_name: str) -> Tuple[bool, float, str]:
    """
    验证URL的整体质量和相关性
    
    Args:
        url: 待验证的URL
        platform: 平台类型
        author_name: 目标作者姓名
        
    Returns:
        (is_valid, quality_score, reason)
    """
    if not url or not url.startswith('http'):
        return False, 0.0, "Invalid URL format"
    
    url_lower = url.lower()
    
    # 基础质量检查
    if len(url) > 500:
        return False, 0.0, "URL too long"
    
    if any(bad in url_lower for bad in ['spam', 'fake', 'test', 'example', 'dummy']):
        return False, 0.0, "Contains suspicious keywords"
    
    # 平台特定验证
    if platform == 'twitter':
        return validate_social_link_for_author(platform, url, author_name), 0.8, "Twitter validation"
    elif platform == 'linkedin':
        return validate_social_link_for_author(platform, url, author_name), 0.8, "LinkedIn validation"
    elif platform == 'github':
        return validate_social_link_for_author(platform, url, author_name), 0.7, "GitHub validation"
    elif platform == 'scholar':
        is_valid = 'citations?user=' in url_lower
        return is_valid, 0.9 if is_valid else 0.0, "Scholar validation"
    elif platform == 'homepage':
        # 个人网站质量评估
        quality_indicators = [
            len(url.split('.')) <= 3,  # 简单域名结构
            any(tld in url_lower for tld in ['.com', '.org', '.net', '.io', '.me']),  # 常见TLD
            not any(platform in url_lower for platform in ['blogspot', 'wordpress.com', 'wix.com'])  # 非博客平台
        ]
        quality_score = sum(quality_indicators) / len(quality_indicators)
        return quality_score >= 0.5, quality_score, f"Homepage quality: {quality_score:.2f}"
    
    # 默认验证
    return True, 0.6, "Basic validation passed"


# ============================ DEMO AND TESTING FUNCTIONS ============================
def demo_author_discovery():
    """Demo function for testing author discovery"""
    # Example usage
    first_author = "Yoshua Bengio"
    paper_title = "Deep Learning"
    aliases = ["Y. Bengio"]

    print(f"Discovering profile for: {first_author}")
    print(f"Paper: {paper_title}")

    profile = discover_author_profile(first_author, paper_title, aliases, k_queries=30)

    print("\n=== DISCOVERED PROFILE ===")
    print(f"Name: {profile.name}")
    print(f"Aliases: {profile.aliases}")
    print(f"Platforms: {profile.platforms}")
    print(f"IDs: {profile.ids}")
    print(f"Affiliation: {profile.affiliation_current}")
    print(f"Emails: {profile.emails}")
    print(f"Interests: {profile.interests}")
    print(f"Publications: {len(profile.selected_publications)}")
    print(f"Confidence: {profile.confidence}")

    return profile

if __name__ == "__main__":
    import sys

    # 可以选择运行不同的测试
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "discovery":
            print("Running author discovery demo...")
            demo_author_discovery()
        else:
            print("Usage: python author_discovery.py [discovery]")
            print("  discovery: Run full author discovery demo")
    else:
        print("Running default author discovery demo...")
        demo_author_discovery()
