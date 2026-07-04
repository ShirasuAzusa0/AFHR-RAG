from typing import Literal
from langgraph.graph import StateGraph, START, END
from graph.state import AgentState
from graph.sub_graph import build_subgraph

# 编译 SubGraph（子图实例，用于处理单个子问题）
SUBGRAPH = build_subgraph()


# history summarize
def summarize_history_node(state: AgentState):
    """
        历史总结节点

        功能：
            将原始对话历史压缩为简洁的文本摘要，用于后续上下文理解

        输入：
            state["raw_history"]: 原始对话历史列表
            格式：[{"role": "user/assistant", "content": "..."}]

        输出：
            state["conversation_history"]: 压缩后的对话历史文本摘要

        逻辑：
            调用 AgentService.summarize_history 进行历史总结
    """
    history = state.get("raw_history", [])
    from services.agent_service import AgentService
    result = AgentService.summarize_history(history)
    return result


# rewrite
def rewrite_node(state: AgentState):
    """
        问题改写节点（Query Rewrite）

        功能：
            基于用户原始问题和对话上下文，对问题进行改写和澄清

        输入：
            state["query"]: 用户原始问题
            state["conversation_history"]: 对话历史摘要

        输出：
            state["rewritten_questions"]: 改写后的问题列表（可能多个候选）
            state["clarification_needed"]: 如需澄清，返回澄清提示信息

        处理逻辑：
            1. 调用 AgentService.rewrite_query 进行问题改写
            2. 如果改写结果为空，返回空列表和澄清信息
            3. 否则返回改写后的问题列表

        注意：
            当 clarification_needed 非空时，表示问题不清晰，需要用户补充信息
    """
    from services.agent_service import AgentService
    result = AgentService.rewrite_query(
        state["query"],
        state["conversation_history"]
    )

    rewritten = result.get("rewritten_questions", [])
    clarification = result.get("clarification_needed", "")

    if not rewritten:
        return {
            "rewritten_questions": [],
            "clarification_needed": clarification
        }

    return {
        "rewritten_questions": rewritten,
        "clarification_needed": clarification
    }


# rewrite route
def rewrite_router(state: AgentState) -> Literal["dispatch", "merge"]:
    """
        改写路由决策节点（条件边）

        功能：
            根据问题改写结果决定下一步流程

        输入：
            state["rewritten_questions"]: 改写后的问题列表

        返回：
            "dispatch": 有改写结果 → 分发到子图处理
            "merge": 无改写结果 → 直接进入合并节点（可能返回澄清信息）

        路由逻辑：
            - 如果 rewritten_questions 非空 → 进入 dispatch 节点，并行处理多个子问题
            - 如果 rewritten_questions 为空 → 直接进入 merge 节点
              （此时 clarification_needed 可能包含提示信息）
    """
    if state.get("rewritten_questions"):
        return "dispatch"
    return "merge"


# dispatch
def dispatch_node(state: AgentState):
    """
        分发调度节点

        功能：
            将改写后的多个问题分发到 SubGraph 子图中独立处理

        输入：
            state["rewritten_questions"]: 改写后的多个问题列表
            state["conversation_history"]: 对话上下文

        输出：
            state["sub_results"]: 子问题处理结果聚合列表
            每个元素包含：
            {
                "question": 子问题,
                "rag_result": 检索结果,
                "references": 引用列表
            }

        处理逻辑：
            1. 遍历每个改写后的问题
            2. 为每个问题构建子图状态（包含 subquestion、conversation_history、iteration 等）
            3. 调用 SUBGRAPH.invoke 执行子图（内部包含 classify → rag → evaluate → merge 流程）
            4. 收集所有子图结果到 sub_results 列表
            5. 如果没有问题，返回空字典

        注意：
            SubGraph 内部已处理迭代控制和降级逻辑，此处只负责并行调度
    """
    questions = state.get("rewritten_questions", [])
    
    if not questions:
        return {}
    
    sub_results = []

    for q in questions:
        subgraph_state = {
            "subquestion": q,
            "conversation_history": state["conversation_history"],
            "iteration": 0,
            "references": []
        }
        
        result = SUBGRAPH.invoke(subgraph_state)
        
        sub_results.append({
            "question": q,
            "rag_result": result.get("rag_result", {}),
            "references": result.get("references", [])
        })
    
    return {
        "sub_results": sub_results
    }


# merge
def merge_node(state: AgentState):
    """
        最终答案生成节点

        功能：
            综合所有子问题的处理结果，生成最终的完整回答

        输入：
            state["query"]: 用户原始问题
            state["sub_results"]: 所有子问题的处理结果列表
            state["conversation_history"]: 对话上下文
            state["stream_callback"]: 流式回调函数

        输出：
            state["answer"]: 最终生成的答案文本
            state["references"]: 合并后的所有引用列表

        逻辑：
            调用 AgentService.generate_final_answer 生成最终答案
    """
    from services.agent_service import AgentService
    result = AgentService.generate_final_answer(
        query=state["query"],
        sub_results=state.get("sub_results", []),
        conversation_history=state.get("conversation_history", ""),
        stream_callback = state.get("stream_callback")
    )

    return {
        "answer": result.get("answer", ""),
        "references": result.get("references", [])
    }


# build graph
def build_main_graph():
    """
        构建主 Agentic RAG 流程图

        工作流程：
            1. START → history：总结对话历史
            2. history → rewrite：改写用户问题
            3. rewrite 条件路由：
               - 有改写结果 → dispatch：分发到子图并行处理
               - 无改写结果 → merge：直接生成答案（可能返回澄清信息）
            4. dispatch → merge：收集所有子图结果
            5. merge → END：生成最终答案

        子图结构（SUBGRAPH）：
            START → classify → rag → evaluate → [sufficient/irrelevant → merge] → [insufficient → web → merge]

        返回：
            CompiledStateGraph: 编译后的 LangGraph 图实例
    """
    builder = StateGraph[AgentState](AgentState)

    # nodes
    builder.add_node("history", lambda state: summarize_history_node(state))
    builder.add_node("rewrite", lambda state: rewrite_node(state))
    builder.add_node("dispatch", lambda state: dispatch_node(state))
    builder.add_node("merge", lambda state: merge_node(state))

    # flow
    builder.add_edge(START, "history")
    builder.add_edge("history", "rewrite")

    builder.add_conditional_edges(
        "rewrite",
        rewrite_router,
        {
            "dispatch": "dispatch",
            "merge": "merge"
        }
    )

    builder.add_edge("dispatch", "merge")
    builder.add_edge("merge", END)

    return builder.compile()
