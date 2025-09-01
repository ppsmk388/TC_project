"""
Agent functions for Talent Search System
Handles query parsing and search execution
"""

from typing import Dict, Any, List
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import schemas
from schemas import QuerySpec, ResearchState
import search
import utils
import config
import llm

def agent_parse_search_query(search_query: str) -> QuerySpec:
    """
    Parse a natural language search query into structured QuerySpec
    
    Args:
        search_query: Natural language query from user
        
    Returns:
        QuerySpec: Structured search parameters
    """
    # 使用LLM解析查询（如果LLM可用）
    try:
        llm_instance = llm.get_llm("parse", temperature=0.3)
        
        conf_list = ", ".join(config.DEFAULT_CONFERENCES.keys())
        prompt = (
            "You are a professional talent recruitment analysis assistant responsible for parsing recruitment queries and extracting structured information.\n\n"
            "=== PARSING TASK INSTRUCTIONS ===\n"
            "Please carefully analyze the user's recruitment query and extract the following key information:\n\n"
            "1. **top_n** (int): Number of candidates needed. Look for numbers in the query like '10 candidates', '20 people', etc.\n\n"
            "2. **years** (int[]): Years to focus on for papers. Prioritize recent years like [2024,2025]. Default to [2025,2024] if not specified.\n\n"
            "3. **venues** (string[]): Target conferences/journals. Users will explicitly mention venues like 'ACL', 'NeurIPS', etc.\n"
            f"   Known venues include (not exhaustive): {conf_list}\n"
            "   Recognition rules:\n"
            "   - Direct conference names: ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML\n"
            "   - Conference variants: NIPS→NeurIPS, The Web Conference→WWW\n"
            "   - Platforms: OpenReview (counts as a venue)\n\n"
            "4. **keywords** (string[]): Research areas and technical keywords. Focus on identifying:\n"
            "   Technical keywords: LLM, large language models, transformer, attention, multi-agent, multi-agent systems, reinforcement learning, RL, graph neural networks, GNN, foundation model, social simulation, computer vision, CV, natural language processing, NLP\n"
            "   Research areas: machine learning, deep learning, AI alignment, robotics, computer vision, NLP, speech recognition, recommendation systems\n"
            "   Application areas: autonomous driving, medical AI, finance, social simulation, game theory, human-AI interaction\n\n"
            "5. **must_be_current_student** (bool): Whether candidates must be current students. Look for:\n"
            "   - Explicit requirements: current student, currently enrolled, active student\n"
            "   - Degree phases: PhD student, Master's student, graduate student\n"
            "   - Default: true (unless explicitly stated otherwise)\n\n"
            "6. **degree_levels** (string[]): Acceptable degree levels.\n"
            "   Recognition: PhD, MSc, Master, Graduate, Undergraduate, Bachelor, Postdoc\n"
            "   Default: ['PhD', 'MSc', 'Master', 'Graduate']\n\n"
            "7. **author_priority** (string[]): Author position preferences.\n"
            "   Recognition: first author, last author, corresponding author\n"
            "   Default: ['first', 'last']\n\n"
            "8. **extra_constraints** (string[]): Other constraints.\n"
            "   Recognition: geographic requirements (e.g., 'Asia', 'North America')\n"
            "   institutional requirements (e.g., 'top universities', 'Ivy League')\n"
            "   language requirements, experience requirements, etc.\n\n"
            "=== PARSING STRATEGY TIPS ===\n"
            "• Prioritize explicitly mentioned information, then make reasonable inferences\n"
            "• For technical keywords, identify specific models, methods, and research areas\n"
            "• Distinguish between different recruitment goals: interns vs researchers vs postdocs\n"
            "• Pay attention to time-sensitive information: recent publications, accepted papers, upcoming deadlines\n\n"
            "Return STRICT JSON format only, no additional text.\n\n"
            "User Query:\n"
            f"{search_query}\n"
        )
        
        query_spec = llm.safe_structured(llm_instance, prompt, schemas.QuerySpec)
        
        # 如果venues为空，设置默认值
        if query_spec.venues == []:
            query_spec.venues = ["ICLR", "ICML", "NeurIPS", "ACL", "EMNLP", "NAACL", "KDD", "WWW", "AAAI", "IJCAI", "CVPR", "ECCV", "ICCV", "SIGIR"]
        
        return query_spec
        
    except Exception as e:
        print(f"LLM解析失败，使用模拟数据: {e}")
        
        # 回退到模拟数据
        return schemas.QuerySpec(
            top_n=10,
            years=[2025, 2024],
            venues=["ICLR", "ICML", "NeurIPS"],
            keywords=["social simulation", "multi-agent systems"],
            must_be_current_student=True,
            degree_levels=["PhD", "Master"],
            author_priority=["first"],
        )

def agent_execute_search(query_spec: QuerySpec) -> List[Dict[str, Any]]:
    """
    Execute the search based on QuerySpec and return results
    
    Args:
        query_spec: Structured search parameters
        
    Returns:
        List of candidate results
    """
    # 这里会调用实际的搜索模块
    # 暂时返回模拟数据，后续可以集成真实的搜索逻辑
    
    # 基于query_spec生成搜索结果
    mock_results = [
        {
            "Name": "Jiarui Ji",
            "Current Role & Affiliation": "M.E. Student, Gaoling School of Artificial Intelligence, Renmin University of China; Incoming Ph.D. (Sep 2025)",
            "Research Focus": [
                "LLM-based agents",
                "social simulation",
                "dynamic graph generation",
                "text-attributed graph generation"
            ],
            "Profiles": {
                "Homepage": "https://ji-cather.github.io/homepage/",
                "Google Scholar": "https://scholar.google.com/citations?user=zLUgeEMAAAAJ",
                "GitHub": "https://github.com/Ji-Cather"
            },
            "Notable": (
                "First-author ACL Findings 2025 on LLM-based multi-agent systems as scalable graph generative models; "
                "first-author EMNLP Findings 2024 (SRAP-Agent) on scarce resource allocation with LLM agents; "
                "2025 preprints on dynamic TAG prediction and the GDGB benchmark."
            )
        },
        {
            "Name": "Xinyi Mou",
            "Current Role & Affiliation": "Ph.D. Student, Fudan University (Data Intelligence & Social Computing Lab, DISC)",
            "Research Focus": [
                "LLM-driven social simulation",
                "computational social science",
                "key figure modeling",
                "discourse analysis"
            ],
            "Profiles": {
                "Homepage": "https://xymou.github.io/",
                "Google Scholar": "https://scholar.google.com/citations?user=nMkkDWYAAAAJ&hl=zh-CN",
                "GitHub": "https://github.com/xymou",
                "Dblp": "https://dblp.org/pid/297/8903.html"
            },
            "Notable": (
                "EMNLP Findings 2025 EcoLANG on agent communication for social simulation; "
                "NAACL 2025 AgentSense benchmarking social intelligence of language agents; "
                "ACL Findings 2024 on agent-based large-scale social movement simulation; "
                "broader work spanning ACM TIST 2025 (GPT-4V for social media analysis), ACL Findings 2024 (SoMeLVLM), "
                "WWW 2024 and COLING 2024 on political/social user modeling."
            )
        },
        {
            "Name": "Zengqing Wu",
            "Current Role & Affiliation": "M.Eng. Student, Kyoto University; Research Associate / Technical Staff, Osaka University",
            "Research Focus": [
                "agent-based modeling with LLMs",
                "computational social science",
                "complex systems",
                "social simulation"
            ],
            "Profiles": {
                "Homepage": "https://wuzengqing001225.github.io/",
                "Google Scholar": "https://scholar.google.com/citations?user=8p3HcqsAAAAJ",
                "GitHub": "https://github.com/wuzengqing001225",
                "Twitter(X)": "https://x.com/WuZengqing",
                "LinkedIn": "https://www.linkedin.com/in/zengqing-wu-4222861b9/"
                
                
            },
            "Notable": (
                "EMNLP 2025 (Main) to appear on disagreement/implicit consensus in long-horizon multi-agent settings; "
                "EMNLP Findings 2024 paper on spontaneous cooperation among competing LLM agents; "
                "NeurIPS 2024 work on LLM-agent personal mobility generation (LLMob); "
                "IEEE Transactions on Education 2024 on entropy-based assessment; "
                "active reviewer/service across NeurIPS/ICLR/ICML/ACL; "
                "NEC Corporation Award (DEIM 2024)."
            )
        },
        {
            "Name": "Jinsook Lee",
            "Current Role & Affiliation": "Ph.D. Candidate, Cornell University (Information Science, Future of Learning Lab)",
            "Research Focus": [
                "AI evaluation in education",
                "algorithmic fairness",
                "computational social science",
                "admissions policy analysis"
            ],
            "Profiles": {
                "Homepage": "https://jinsook-jennie-lee.github.io/",
                "Google Scholar": "https://scholar.google.com/citations?hl=en&user=6ZU8WIEAAAAJ",
                "GitHub": "https://github.com/Jinsook-Jennie-Lee"
            },
            "Notable": (
                "EAAMO 2024 on the impact of ending affirmative action on diversity/merit; "
                "British Journal of Educational Technology 2024 on the life cycle of LLMs in education and bias; "
                "Journal of Big Data 2024 on human vs. synthetic authorship; "
                "AIED 2023 workshop paper on NLP for holistic admissions; "
                "Cornell Center for Social Sciences grant (2024); "
                "accepted 2025 workshop submission on LLM alignment/steerability in admissions essays."
            )
        }
    ]

    
    # 根据query_spec过滤结果
    filtered_results = []
    for candidate in mock_results:
        # # 检查研究领域匹配
        # if query_spec.keywords:
        #     if not any(keyword.lower() in " ".join(candidate["Research Focus"]).lower() 
        #               for keyword in query_spec.keywords):
        #         continue
        
        # # 检查学位级别
        # if query_spec.degree_levels:
        #     role_lower = candidate["Current Role & Affiliation"].lower()
        #     if not any(degree.lower() in role_lower for degree in query_spec.degree_levels):
        #         continue
        
        filtered_results.append(candidate)
    
    # 限制到top_n结果
    return filtered_results[:query_spec.top_n]

def node_parse_query(state: ResearchState) -> Dict[str, Any]:
    """
    Node function for parsing queries in the research workflow
    
    Args:
        state: Current research state
        
    Returns:
        Updated state with parsed query
    """
    # 这个函数用于工作流系统
    # 暂时直接返回状态
    return state