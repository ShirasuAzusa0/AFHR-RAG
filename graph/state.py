from typing import TypedDict, Annotated, Callable
import operator

class AgentState(TypedDict, total=False):
    """
        Agentic RAG 主状态管理类

        负责在整个 Agent 执行流程中维护全局状态，包括用户输入、对话历史、
        中间结果和最终输出。使用 TypedDict 确保类型安全，total=False 表示所有字段均为可选。
    """
    query: str                                      # 用户输入
    raw_history: list                               # 原始历史记忆
    conversation_history: str                       # 历史对话文本总结
    rewritten_questions: list[str]                  # query rewrite 结果
    clarification_needed: str                       # 不清晰问题提示
    sub_results: Annotated[list, operator.add]      # 多个 SubGraph 自动聚合
    answer: str                                     # 最终生成的回答内容
    references: list                                # 引用来源表
    stream_callback: Callable[[str], None]          # 流式输出回调函数，接收字符串参数，用于实时推送 token 给前端


class SubGraphState(TypedDict, total=False):
    """
        SubGraph（子图）状态管理类

        用于管理单个子问题的处理流程状态，每个 SubGraph 独立处理一个子问题，
        包含从问题理解、检索、评估到生成答案的完整链路。
    """
    subquestion: str                                # 当前子问题
    conversation_history: str                       # 上下文
    iteration: int                                  # 循环次数
    kb_id: int                                      # classify结果
    rag_result: dict                                # 检索结果
    retrieval_decision: str                         # evaluate 结果（accept, rewrite or fallback）
    references: list                                # 当前子图的最终引用文档列表
    answer: str                                     # 当前子图生成的子回答内容