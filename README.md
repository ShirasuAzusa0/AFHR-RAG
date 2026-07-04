# AFHR-RAG

**AFHR-RAG**（Anti-Fraud & Health Rumor RAG）是一个基于 Agentic RAG（Agentic Retrieval-Augmented Generation） 构建、面向中老年用户群体的反诈与辟谣预防平台。

本部分是项目中的 RAG 能力层（RAG Engine） 实现，负责完成用户问题理解、多阶段知识获取、联网补充、结果融合与最终回答生成。

系统目标并非简单问答，而是通过 多智能体任务拆解 + 检索增强 + 联网校验 + 多轮决策机制，提高在反诈、防谣、科普等场景下的回答准确率与可信度。

## 项目架构
AFHR-RAG架构如下：
``` text
AFHR-RAG/
├── api/                     ← api层，实现对前端/主后端的接口对接
├── configs/                 ← 配置项
├── graph/                   ← LangGraph工作流编排层（MainGraph / SubGraph）
├── model/                   ← 本地部署的模型
├── models/                  ← models层，实现数据库表ORM实体映射
├── prompts/                 ← 提示词模板文件
├── repositories/            ← repositories层，对接数据库增删改查接口
├── script/                  ← 脚本文件
├── services/                ← services层，实现服务事务处理
├── tools/                   ← 工具层，包括联网搜索等多项工具
├── utils/                   ← 辅助工具函数、模型载入、响应模板、爬虫等高复用代码模块
├── .env                     ← 项目环境
├── .gitignore               ← Git忽略规则
├── main.py                  ← 项目入口
└── README.md                ← 项目说明
```

## 核心设计
系统整体采用双层 Graph 架构：
``` text
MainGraph
├── History Summarize
├── Query Rewrite
├── Query Dispatch
├── SubGraph（并行）
└── Final Merge
```
- MainGraph 负责整体任务控制；
- SubGraph 负责单个子问题处理；
- Service 层负责模型调用；
- Repository 层负责知识存储访问；
- Tool 层负责联网能力扩展。

## 运作逻辑

AFHR-RAG 采用 **MainGraph + SubGraph 的双层 Agentic RAG 编排架构**。

用户问题不会直接进入检索，而是经过问题理解、任务拆解、知识获取、结果评估与统一生成多个阶段完成回答。

```text
┌──────────────────────────────────────────────┐
│                 User Query                   │
│                用户输入问题                    │
└─────────────────────┬────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│            History Summarization             │
│           历史上下文提取与压缩                 │
└─────────────────────┬────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│               Query Rewrite                  │
│        问题重写｜歧义判断｜任务拆分             │
└─────────────────────┬────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌──────────────────┐     ┌────────────────────┐
│ Clarification    │     │ rewritten_questions│
│ 需要用户补充信息  │     │    子问题列表       │
└──────────────────┘     └─────────┬──────────┘
                                    │
                                    ▼
                    ┌──────────────────────────┐
                    │         Dispatch         │
                    │      Send → SubGraph     │
                    └──────────┬───────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
     ┌────────────┐    ┌────────────┐    ┌────────────┐
     │ SubGraph 1 │    │ SubGraph 2 │    │ SubGraph N │
     └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
           │                 │                 │
           ▼                 ▼                 ▼
┌──────────────────────────────────────────────┐
│           Knowledge Retrieval Flow           │
│                                              │
│   Classify → Retrieve → Rerank → Evaluate    │
│                     ↓                        │
│              Web Search (Optional)           │
│                     ↓                        │
│                 RAG Result                   │
└─────────────────────┬────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│                  Merge Node                  │
│     聚合子问题结果与参考来源信息               │
└─────────────────────┬────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│          Generate Final Answer               │
│        Prompt Build + LLM Generation         │
└─────────────────────┬────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│              Final Response                  │
│                                              │
│               answer                         │
│               references                     │
└──────────────────────────────────────────────┘
```
在评估后，若认为不足以回答，将会继续检索并调用工具获取更多相关信息已满足回答的需求

## 调用说明

具体的接口说明详见 Apifox 上的接口文档，以下为概要说明：
```text
接口类型：POST
接口前置URL：https://nonrotatable-chara-laterally.ngrok-free.dev
接口URL：/api/rag/v1/er/search
请求参数：query, history
返回参数：LLM 流式输出的 answer 和 references
```

## 主项目链接
https://gitee.com/deanyy/rag-legal-anti-fraud-system
