# 🔍 Targeted Search Enhancement

## 新功能特性

### ✨ UI/UX 改进
- **更大的搜索框**: Search Query文本框高度增加到200px，便于输入详细的搜索需求
- **移除Demo Mode切换**: 现在直接显示demo结果，简化用户体验
- **主题适配**: 完美支持Dark/Light模式切换，与Resume Evaluation页面保持一致
- **响应式设计**: 优化了布局和间距，在不同屏幕尺寸下都有良好表现

### 🎯 默认搜索查询
系统预设了MSRA的标准搜索查询：
```
I am a recruiter from Microsoft Research Asia (MSRA). Please help me identify 10 potential rising star interns who are currently PhD or Master's students and are actively working on social simulation with large language models or multi-agent systems. Focus on candidates who have recent publications or accepted papers at top conferences (e.g., ACL, EMNLP, NAACL, NeurIPS, ICLR, ICML) or on OpenReview.
```

### 📊 Demo数据展示
- 集成了`backend/demo_data.json`中的10位候选人信息
- 包含详细的研究背景、当前职位、研究焦点和个人资料链接
- 自动显示候选人排名和"Rising Star"标签

### 🎨 主题支持
- **Light模式**: 清爽的白色背景，蓝色渐变主题
- **Dark模式**: 深色背景，适合夜间使用
- 自动检测系统主题设置
- 所有UI组件都针对两种主题进行了优化

### 📈 分析功能
- **候选人统计**: 总数、PhD候选人数量、GitHub链接数量、有显著成果的候选人数量
- **研究领域分布**: 可视化展示候选人的研究方向分布情况
- **导出功能**: 支持CSV和JSON格式导出搜索结果

### 🔧 技术改进
- 修复了DataFrame空值判断问题
- 优化了主题检测逻辑，与Resume Evaluation页面保持一致
- 改进了错误处理和用户反馈
- 增强了加载动画和进度指示

## 使用方法

1. **访问页面**: 在侧边栏点击"🔍 Targeted Search"
2. **查看搜索参数**: 默认加载MSRA搜索查询，可以根据需要修改
3. **设置过滤条件**: 选择地理位置、角色类型、经验水平等
4. **运行搜索**: 点击"Run Targeted Search"按钮
5. **查看结果**: 浏览候选人卡片，查看详细信息
6. **导出数据**: 使用CSV或JSON格式导出结果

## 文件结构
```
frontend/
├── targeted_search.py    # 主要的搜索页面组件
├── theme.py             # 增强的主题样式
└── navigation.py        # 导航组件

backend/
└── demo_data.json       # 演示候选人数据

app.py                   # 主应用文件，集成新组件
```

## 演示模式
当前版本运行在演示模式下，展示预设的10位AI研究领域的优秀候选人，包括：
- PhD和硕士研究生
- 专注于社会仿真、多智能体系统、大语言模型等领域
- 来自知名大学如University of Michigan、Renmin University、Fudan University等
- 有丰富的学术成果和开源贡献

## 下一步计划
- 集成真实的学术数据库API
- 添加更多筛选条件
- 实现候选人详情页面
- 添加收藏和标记功能
