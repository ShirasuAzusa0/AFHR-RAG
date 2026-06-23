from state import SubGraphState
from services.agent_service import AgentService

def classify_node(state: SubGraphState):
    result=AgentService.classify_kb(state["subquestion"])
    return {
        "kb_id": result["current_data"]
    }

def rag_node(state: SubGraphState):
    result=AgentService.rag_search(state["subquestion"], state["kb_id"])
    return {
        "rag_result": result
    }

def evaluate_node(state: SubGraphState):
    result=AgentService.evaluate_retrieval(
        state["subquestion"],
        state["rag_result"],
        state["conversation_history"]
    )
    return {
        "retrieval_decision": result["decision"],
        "references": result.get("references", [])
    }

def web_node(state: SubGraphState):
    result=AgentService.web_search(
        state["subquestion"],
        state["conversation_history"]
    )
    return {
        "rag_result": result,
        "iteration": state["iteration"]+1
    }

def merge_node(state: SubGraphState):
    documents = state["rag_result"].get("documents", [])

    answer = "\n".join([doc.get("content", "") for doc in documents])

    return {
        "answer": answer,
        "references": state["references"]
    }

def route_after_eval(state: SubGraphState):
    decision=state["retrieval_decision"]

    if decision=="sufficient":
        return "merge"

    if decision=="irrelevant":
        return "merge"

    if state["iteration"]>=5:
        return "merge"
    return "web"