from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from state import AgentState
from sub_graph import build_subgraph
from services.agent_service import AgentService


# 编译SubGraph
SUBGRAPH = build_subgraph()

# history summarize
def summarize_history_node(state: AgentState):
    history = state.get("raw_history", [])
    result = AgentService._summarize_history(history)

    return {
        "conversation_history": result
    }


# rewrite
def rewrite_node(state: AgentState):
    result = AgentService.rewrite_query(
        state["query"],
        state["conversation_history"]
    )

    rewritten = result.get("rewritten_questions", [])
    clarification = result.get("clarification_needed", "")

    return {
        "rewritten_questions": rewritten,
        "clarification_needed": clarification
    }

# rewrite route
def rewrite_router(state: AgentState) -> Literal["dispatch", END]:
    if state.get("clarification_needed"):
        return END
    return "dispatch"

# dispatch
def dispatch_node(state: AgentState):
    tasks = []

    for q in state.get("rewritten_questions", []):
        tasks.append(
            Send(
                "subgraph",
                {
                    "subquestion": q,
                    "conversation_history": state["conversation_history"],
                    "iteration": 0,
                    "references": []
                }
            )
        )
    return tasks

# subgraph wrapper
def subgraph_node(state):
    result = SUBGRAPH.invoke(state)

    return {
        "sub_results": [
            {
                "question": state["subquestion"],
                "rag_result": result.get("rag_result", {}),
                "references": result.get("references", [])
            }
        ]
    }

# merge
def merge_node(state: AgentState):
    answers = []
    references = []

    for item in state.get("sub_results", []):
        rag = item.get("rag_result", {})

        docs = rag.get("documents", [])

        if docs:
            for d in docs:
                content = d.get("content", "")
                if content:
                    answers.append(content)

        refs = item.get("references", [])
        references.extend(refs)

    return {
        "answer": "\n\n".join(answers),
        "references": references
    }

# build graph
def build_main_graph():
    builder = StateGraph(AgentState)

    # nodes
    builder.add_node("history", summarize_history_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("subgraph", subgraph_node)
    builder.add_node("merge", merge_node)

    # flow
    builder.add_edge(START,"history")
    builder.add_edge("history","rewrite")

    builder.add_conditional_edges(
        "rewrite",
        rewrite_router,
        {
            "dispatch":
                "dispatch",
            END:
                END
        }
    )

    builder.add_edge("dispatch","subgraph")
    builder.add_edge("subgraph", "merge")
    builder.add_edge("merge", END)

    return builder.compile()