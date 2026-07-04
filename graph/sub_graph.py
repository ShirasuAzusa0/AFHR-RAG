from langgraph.graph import StateGraph, END
from graph.state import SubGraphState
from graph.graph_nodes import classify_node, rag_node, evaluate_node, web_node, merge_node, route_after_eval

def build_subgraph():
    """
        构建子图（SubGraph），用于处理单个子问题的完整 RAG 流程

        工作流程：
            1. START → classify：识别应该查询哪个知识库
            2. classify → rag：执行 RAG 检索
            3. rag → evaluate：评估检索质量
            4. evaluate 条件路由：
               - "sufficient" → merge：检索充分，直接生成答案
               - "irrelevant" → merge：结果不相关，直接合并（避免错误回答）
               - "insufficient" → web → evaluate：检索不足，执行网络搜索降级，重新评估
               - 其他情况 → web → evaluate：默认走降级流程
            5. merge → END：合并文档生成最终答案

        循环控制：
            - web 节点会将 iteration + 1
            - route_after_eval 检查 iteration >= 5 时强制进入 merge
            - 避免无限循环

        返回：
            CompiledStateGraph: 编译后的子图实例，可被主图调用
    """
    builder=StateGraph[SubGraphState](SubGraphState)

    # 节点
    builder.add_node("classify", lambda state: classify_node(state))
    builder.add_node("rag", lambda state: rag_node(state))
    builder.add_node("evaluate", lambda state: evaluate_node(state))
    builder.add_node("web", lambda state: web_node(state))
    builder.add_node("merge", lambda state: merge_node(state))

    # 起点
    builder.set_entry_point("classify")

    # 主路径
    builder.add_edge("classify", "rag")
    builder.add_edge("rag", "evaluate")

    # 条件分支
    builder.add_conditional_edges("evaluate", route_after_eval)

    # 循环
    builder.add_edge("web", "evaluate")

    # 结束
    builder.add_edge("merge", END)

    return builder.compile()