# AFHR-RAG
一个基于 Agentic RAG(Decision-Centric Iterative Hybrid Agentic RAG)的面向中老年用户群体的反诈、辟谣预防平台，本仓库所存储的是该项目的RAG部分实现

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

目前为简单的 classic RAG 版本，有待后续优化