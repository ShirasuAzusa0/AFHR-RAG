from graph.state import SubGraphState

def classify_node(state: SubGraphState):
    """
        知识库分类节点

        功能：
            根据当前子问题判断应该查询哪个知识库 / 数据源

        输入：
            state["subquestion"]: 当前子问题文本

        输出：
            state["kb_id"]: 知识库分类 ID，用于后续检索

        逻辑：
            调用 AgentService.classify_kb 进行智能分类
    """
    from services.agent_service import AgentService
    result=AgentService.classify_kb(state["subquestion"])
    return {
        "kb_id": result["current_data"]
    }

def rag_node(state: SubGraphState):
    """
        RAG 检索节点

        功能：
            基于子问题和知识库ID执行向量检索，获取相关文档片段

        输入：
            state["subquestion"]: 当前子问题文本
            state["kb_id"]: 知识库分类ID（由 classify_node 产出）

        输出：
            state["rag_result"]: 检索结果，包含文档列表和元数据
            格式：{"documents": [...], "scores": [...], ...}

        逻辑：
            调用 AgentService.rag_search 执行检索
    """
    from services.agent_service import AgentService
    result=AgentService.rag_search(state["subquestion"], state["kb_id"])
    return {
        "rag_result": result
    }

def evaluate_node(state: SubGraphState):
    """
        检索质量评估节点

        功能：
            评估 RAG 检索结果的质量，决定是否接受、重写或降级处理

        输入：
            state["subquestion"]: 当前子问题文本
            state["rag_result"]: RAG 检索结果
            state["conversation_history"]: 对话上下文

        输出：
            state["retrieval_decision"]: 决策结果
                - "sufficient": 检索充分，可直接生成答案
                - "irrelevant": 检索结果不相关，需要降级处理
                - "insufficient": 检索不充分，需要重新检索或改写查询
            state["references"]: 评估后筛选出的引用列表（如果有）

        逻辑：
            调用 AgentService.evaluate_retrieval 进行质量评估
    """
    from services.agent_service import AgentService
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
    """
        网络搜索降级节点（Fallback）

        功能：
            当 RAG 检索质量不足时，执行网络搜索作为降级方案

        输入：
            state["subquestion"]: 当前子问题文本
            state["conversation_history"]: 对话上下文
            state["iteration"]: 当前迭代次数

        输出：
            state["rag_result"]: 将网络搜索结果转换为 RAG 格式
            格式：{"documents": [{"content": "搜索结果文本"}]}

            state["references"]: 网络搜索的引用来源列表
            state["iteration"]: 迭代次数 + 1（用于控制循环上限）

        逻辑：
            调用 AgentService.web_search 执行网络搜索
    """
    from services.agent_service import AgentService
    answer, references = AgentService.web_search(
        state["subquestion"],
        state["conversation_history"]
    )
    return {
        "rag_result": {"documents": [{"content": answer}]},
        "references": references,
        "iteration": state["iteration"]+1
    }

def merge_node(state: SubGraphState):
    """
        答案合并节点

        功能：将检索到的文档内容合并为最终答案字符串

        输入：
            state["rag_result"]: 包含 documents 列表的检索结果
            state["references"]: 引用列表

        输出：
            state["answer"]: 合并后的答案文本（去除多余空白）
            state["references"]: 保持原有引用不变
            state["rag_result"]: 保持原有检索结果不变

        处理逻辑：
            1. 遍历 documents 列表，提取文本内容
            2. 兼容多种文档格式（tuple、dict、list、str）
            3. 将所有内容拼接为单个字符串
            4. 去除首尾空白字符
    """
    documents = state["rag_result"].get("documents", [])

    answer = ""
    for doc in documents:
        if isinstance(doc, tuple):
            content = doc[0] if len(doc) > 0 else ""
        elif isinstance(doc, dict):
            content = doc.get("content", "")
        else:
            continue
        
        # 确保 content 是字符串
        if isinstance(content, list):
            content = "".join(str(c) for c in content)
        elif not isinstance(content, str):
            content = str(content)
            
        answer += content + "\n"

    return {
        "answer": answer.strip(),
        "references": state["references"],
        "rag_result": state["rag_result"]
    }

def route_after_eval(state: SubGraphState):
    """
        路由决策节点（条件边）

        功能：
            根据评估结果决定下一步执行哪个节点

        输入：
            state["retrieval_decision"]: 评估决策结果
            state["iteration"]: 当前迭代次数

        返回：
            str: 下一个要执行的节点名称
                - "merge": 直接进入合并节点，生成答案
                - "web": 进入网络搜索降级节点

        路由逻辑：
            1. 如果 decision == "sufficient"（检索充分）→ 合并
            2. 如果 decision == "irrelevant"（结果不相关）→ 合并（避免无效循环）
            3. 如果 iteration >= 5（超过最大重试次数）→ 合并（防止死循环）
            4. 其他情况（如 "insufficient"）→ 进入 web 节点尝试降级搜索
    """
    decision=state["retrieval_decision"]

    if decision=="sufficient":
        return "merge"

    if decision=="irrelevant":
        return "merge"

    if state["iteration"]>=5:
        return "merge"
    return "web"