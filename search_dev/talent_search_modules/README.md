# Talent Search System - 模块化版本

这是一个模块化的AI人才搜索系统，用于识别顶尖会议（如ICLR、ICML、NeurIPS等）的优秀学生候选人。

## 🏗️ 系统架构

系统被拆分为以下独立的模块：

| 模块 | 功能 |
|------|------|
| `config.py` | 配置和常量定义 |
| `utils.py` | 通用工具函数（URL处理、文本清理、日志等） |
| `schemas.py` | Pydantic数据模型（QuerySpec, ResearchState等） |
| `llm.py` | LLM配置和封装（vLLM集成、结构化输出） |
| `search.py` | 搜索功能（SearXNG、URL选择、内容抓取） |
| `extraction.py` | 抽取功能（作者提取、候选人过滤） |
| `graph.py` | LangGraph工作流（节点定义、路由逻辑） |
| `main.py` | 主入口点（完整流程集成） |

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- SearXNG (http://127.0.0.1:8888)
- vLLM (http://localhost:8000/v1)
- 依赖包：`pip install requests trafilatura beautifulsoup4 langchain-openai pydantic langgraph`

### 2. 基本用法

```python
import sys
sys.path.append('/path/to/talent_search_modules')

import main

# 运行完整搜索流程
result = main.talent_search(
    "Find 10 current PhD students working on social simulation at top AI conferences"
)

print(f"Found {len(result['candidates'])} candidates")
```

### 3. 单独使用模块

```python
# 导入特定模块
import search
import extraction
import schemas

# 创建查询规格
spec = schemas.QuerySpec(
    top_n=5,
    keywords=["machine learning", "AI"],
    venues=["ICLR", "NeurIPS"],
    must_be_current_student=True
)

# 构建搜索查询
search_terms = search.build_conference_queries(spec, search.DEFAULT_CONFERENCES)

# 搜索内容
results = search.searxng_search("machine learning conference papers 2024")

print(f"Generated {len(search_terms)} search terms")
print(f"Found {len(results)} search results")
```

## 📊 工作流程

### 阶段1：查询解析
```python
# 自然语言查询 → 结构化参数
query = "Find PhD students in AI research"
spec = llm.parse_query(query)  # 使用LLM解析
```

### 阶段2：搜索规划
```python
# 基于查询构建搜索词
search_terms = search.build_conference_queries(spec, config.DEFAULT_CONFERENCES)
```

### 阶段3：内容搜索
```python
# 使用SearXNG搜索
serp_results = []
for term in search_terms:
    results = search.searxng_search(term)
    serp_results.extend(results)
```

### 阶段4：智能选择
```python
# 选择最相关的URL
selected_urls = search.heuristic_pick_urls(serp_results, spec.keywords)
```

### 阶段5：内容抓取
```python
# 抓取和提取内容
sources = {}
for url in selected_urls:
    text = search.fetch_text(url)
    if len(text) > 50:  # 过滤太短的内容
        sources[url] = text
```

### 阶段6：作者提取
```python
# 从论文中提取作者
authors = extraction.extract_authors_from_sources(sources, spec)
```

### 阶段7：候选人合成
```python
# 生成结构化的候选人信息
candidates = extraction.synthesize_candidates(sources, spec)
```

## 🔧 配置说明

### 主要配置参数 (`config.py`)

```python
# 输出设置
SAVE_DIR = "/path/to/save/results"

# SearXNG配置
SEARXNG_BASE_URL = "http://127.0.0.1:8888"
SEARXNG_ENGINES = "google"
SEARXNG_PAGES = 3

# LLM配置
LOCAL_OPENAI_BASE_URL = "http://localhost:8000/v1"
LOCAL_OPENAI_MODEL = "Qwen3-8B"

# 搜索参数
MAX_ROUNDS = 3          # 最大迭代轮数
SEARCH_K = 8           # 每查询的搜索结果数
SELECT_K = 16          # 每轮选择抓取的URL数
```

### 默认会议库

系统内置了对以下会议的支持：

- **ICLR**: ["ICLR"]
- **ICML**: ["ICML"]
- **NeurIPS**: ["NeurIPS", "NIPS"]
- **ACL**: ["ACL"]
- **EMNLP**: ["EMNLP"]
- **NAACL**: ["NAACL"]
- **KDD**: ["KDD"]
- **WWW**: ["WWW", "The Web Conference", "WebConf"]

## 🧪 测试和开发

### 运行测试

```bash
cd talent_search_modules
python test_modules.py
```

### 使用Jupyter Notebook

打开 `talent_search_demo.ipynb` 来交互式地测试和开发：

```bash
jupyter notebook talent_search_demo.ipynb
```

### 模块独立测试

```python
# 测试搜索功能
import search
results = search.searxng_search("AI conference papers 2024")
print(f"Found {len(results)} results")

# 测试查询构建
import schemas
spec = schemas.QuerySpec(keywords=["machine learning"])
queries = search.build_conference_queries(spec, config.DEFAULT_CONFERENCES)
print(f"Generated {len(queries)} search queries")
```

## 📈 扩展开发

### 添加新功能

1. **新的搜索源**: 在 `search.py` 中添加新的搜索引擎
2. **新的数据源**: 在 `extraction.py` 中添加新的解析器
3. **新的过滤规则**: 在 `extraction.py` 中修改 `postfilter_candidates`
4. **新的LLM模型**: 在 `llm.py` 中添加新的模型配置

### 自定义工作流

```python
# 创建自定义工作流
import graph
from langgraph.graph import StateGraph

# 构建自定义图
custom_graph = StateGraph(graph.ResearchState)

# 添加自定义节点
custom_graph.add_node("my_custom_step", my_custom_function)
# ... 添加更多节点和边

# 编译图
app = custom_graph.compile()
```

## 📝 使用示例

### 基本搜索

```python
import main

query = "Find 10 PhD students working on reinforcement learning at ICLR and NeurIPS 2024"
result = main.talent_search(query)

print(f"Found {len(result['candidates'])} candidates")
for candidate in result['candidates']:
    print(f"- {candidate['name']}: {candidate['current_role_affiliation']}")
```

### 高级搜索

```python
from schemas import QuerySpec
import search

# 自定义查询规格
spec = QuerySpec(
    top_n=20,
    years=[2024, 2025],
    venues=["ICLR", "ICML", "NeurIPS"],
    keywords=["graph neural networks", "attention mechanisms"],
    must_be_current_student=True,
    degree_levels=["PhD", "Master"],
    author_priority=["first", "corresponding"]
)

# 构建查询
queries = search.build_conference_queries(spec, config.DEFAULT_CONFERENCES)
print(f"Generated {len(queries)} search queries")

# 执行搜索
all_results = []
for query in queries[:5]:  # 限制数量用于测试
    results = search.searxng_search(query)
    all_results.extend(results)

print(f"Total search results: {len(all_results)}")
```

## ⚠️ 注意事项

1. **服务依赖**: 需要SearXNG和vLLM服务运行
2. **网络要求**: 内容抓取需要稳定的网络连接
3. **速率限制**: 搜索和抓取操作有内置延迟
4. **内容过滤**: 系统会过滤太短或无效的内容
5. **隐私考虑**: 确保遵守网站的robots.txt和服务条款

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个系统！

## 📄 许可证

MIT License
