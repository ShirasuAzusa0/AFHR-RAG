from dataclasses import dataclass
from typing import Optional

@dataclass
class DecisionRecord:
    timestamp: str
    iteration: int
    top_k: int
    doc_count: int
    selected_count: int
    total_tokens: int
    action: str                         # final action
    raw_response: str                   # LLM 原始输出
    reflection: Optional[str] = None    # override 信息
    error: Optional[str] = None         # parse / retry / fallback 信息