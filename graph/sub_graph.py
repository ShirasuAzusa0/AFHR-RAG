from langgraph.graph import StateGraph, END
from state import SubGraphState
from graph_nodes import classify_node, rag_node, evaluate_node, web_node, merge_node, route_after_eval

def build_subgraph():
    builder=StateGraph(SubGraphState)

    # 节点
    builder.add_node("classify", classify_node)
    builder.add_node("rag", rag_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("web", web_node)
    builder.add_node("merge", merge_node)

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