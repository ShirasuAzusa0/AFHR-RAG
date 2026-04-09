# AFHR-RAG
一个基于 Agentic RAG(Decision-Centric Iterative Agentic RAG)的面向中老年用户群体的反诈、辟谣预防平台，本仓库所存储的是该项目的RAG部分实现

AFHR-RAG架构如下：
```
AFHR-RAG/
├── api/                     ← api层，实现对前端/主后端的接口对接
├── configs/                 ← 配置项
├── model/                   ← 本地部署的模型
├── models/                  ← models层，实现数据库表映射
├── prompts/                 ← 提示词文件
├── repositories/            ← repositories层，对接数据库增删改查接口
├── script/                  ← 脚本文件
├── services/                ← services层，实现服务事务处理
├── tools/                   ← 工具层
├── utils/                   ← 辅助工具函数、模型载入、响应模板、爬虫等高复用代码模块
├── main.py                  ← 项目入口
└── README.md                ← 项目说明
```

AFHR-RAG的全局架构图为：
```
┌──────────────────────────────────────────────┐
│                    User                      │
└──────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────┐
│                 AgentService                 │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │            Strategy Engine             │  │
│  │  - Query Complexity Estimator          │  │
│  │  - Strategy Generator                  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │          Iterative Controller          │  │
│  │  - Budget Control                      │  │
│  │  - Marginal Gain Detector              │  │
│  │  - State Manager                       │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │          Decision Engine (LLM)         │  │
│  │  - agent_decision_prompt.txt           │  │
│  │  - Schema Validation                   │  │
│  │  - Retry                               │  │
│  │  - Self Reflection Guard               │  │
│  │  - Decision Logging                    │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │          Tool Router Layer             │  │
│  │   ├─ RAGRetrievalTool                  │  │
│  │   └─ WebSearchTool (LLM Expansion)     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────┐
│                 LLM (MiniMax M2-her)         │
│   - 决策                                      │
│   - Web Expansion                            │
└──────────────────────────────────────────────┘
```
整体的流程为：
> 输入 Query -> 自适应策略制定（执行检索召回 -> 更新状态 -> 收益控制检测 -> LLM决策（调用LLM -> 严格 Schema 校验 -> Fallback 兜底 -> 自反思 -> 写入日志） -> 执行动作） -> 决策完成 -> （Hybrid 阶段，进行 Web Fallback） -> 文档去重 -> 输出结果