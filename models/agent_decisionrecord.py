from dataclasses import dataclass
from typing import Optional

@dataclass
class DecisionRecord:
    """
    Agent 决策记录数据结构
    用于记录每次迭代的检索状态和 LLM 决策结果，便于调试和分析
    """
    timestamp: str                      # 决策时间戳，ISO 格式字符串
    iteration: int                      # 当前迭代次数
    top_k: int                          # 当前使用的召回数量
    doc_count: int                      # 累积的文档总数（去重前）
    selected_count: int                 # 经过筛选后的文档数量
    total_tokens: int                   # 当前累积的总 token 数
    action: str                         # 最终决策动作："finish" 或 "expand_search"
    raw_response: str                   # LLM 原始输出
    reflection: Optional[str] = None    # 自我反思防护信息，记录 action 被覆盖 override 的原因
    error: Optional[str] = None         # 错误信息，记录解析失败、重试或降级相关信息