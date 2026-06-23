from typing import TypedDict
from typing import Annotated
import operator


class AgentState(TypedDict):

    # 用户输入
    query: str

    # 历史总结
    conversation_history: str

    # query rewrite结果
    rewritten_questions: list[str]

    # 不清晰问题提示
    clarification_needed: str

    # 多个SubGraph自动聚合
    sub_results: Annotated[
        list,
        operator.add
    ]


class SubGraphState(TypedDict):

    # 当前子问题
    subquestion: str

    # 上下文
    conversation_history: str

    # 循环次数
    iteration: int

    # classify结果
    kb_id: int

    # 检索结果
    rag_result: dict

    # evaluate结果
    retrieval_decision: str

    # 最终引用
    references: list

    answer: str