import json
import logging
import operator
from typing import Dict, Any, List, TypedDict, Annotated
from models.message_model import MMDataItem
from graph.main_graph import build_main_graph
from services.rag_service import RAGService
from tools.web_searcher import call_agent_search
from utils.kb_name2id import kb_name2id
from utils.prompt_loader import load_prompt
from langgraph.types import Send

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    query: str                                      # 用户原始提问输入
    conversation_history: str                       # 总结后的历史消息
    rewritten_questions: list[str]                  # 对 query 重写后的子问题
    clarification_needed: str                       # 对用户下一步要求
    sub_results: Annotated[list, operator.add]

class SubGraphState(TypedDict):
    subquestion: str
    conversation_history: str
    iteration: int
    rag_result: dict
    references: list

class AgentService:
    @staticmethod
    def _summarize_history(raw_history: List[MMDataItem]) -> Dict[str, Any]:
        """
            对用户历史对话进行总结，生成 conversation_history
            :param raw_history: 用户模型聊天历史记录
            :return: 经 LLM 总结过的 conversation_history
        """
        # 对话轮数过少时，不需要进行总结
        if len(raw_history) < 3:
            return {"conversation_history": ""}

        # 过滤有效信息（仅保留user、system 和 assistant）
        relevant_msgs = [
            msg for msg in raw_history
            if msg.role.lower() in ["user", "assistant"]
        ]

        # 若没有有效消息，也无需总结
        if not relevant_msgs:
            return {"conversation_history": ""}

        # 只取最近 6 条消息草拟与总结
        relevant_msgs = relevant_msgs[-6:]

        # 构造对话文本
        conversation = "Conversation history:\n"
        for msg in relevant_msgs:
            role = "User" if msg.role.lower() == "User" else "Assistant"
            conversation += f"{role}: {msg.text}\n"

        # 载入 prompt
        prompt_content = load_prompt('llm_summary_prompt.txt')

        # 调用 LLM 进行总结
        summary_response = RAGService.assisted_query(prompt_content, conversation)
        if summary_response is not None:
            return {"conversation_history": summary_response}
        else:
            return {"conversation_history": ""}


    @staticmethod
    def rewrite_query(query: str, conversation_history: str = "") -> dict:
        """
            重写用户问题：
            1. 改写为检索友好的形式
            2. 必要时拆分为多个子问题
            3. 如果问题不清晰，则要求用户补充
            :param query: 用户问题
            :param conversation_history: LLM 对话记录（已总结）
            :return: 问题重写结果（字典类型）
        """
        # 构建输入内容
        context_section = (
            f"Conversation Context:\n{conversation_history}\n"
            if conversation_history and conversation_history.strip()
            else ""
        ) + f"User Query:\n{query}\n"

        # 载入 prompt
        prompt_content = load_prompt('rewrite_query_prompt.txt')

        # 调用 LLM
        response_text = RAGService.assisted_query(prompt_content, context_section)

        # 解析 JSON
        try:
            result = json.loads(response_text)
        except Exception:
            return {
                "function_type": "rewrite_query",
                "is_clear": False,
                "original_data": query,
                "current_data": [],
                "clarification_needed": "I need more information to understand your question."
            }

        # 提取字段
        is_clear = result.get("is_clear", False)
        questions = result.get("questions", [])
        clarification_needed = result.get("clarification_needed", "")

        # 若问题清晰
        if is_clear and questions:
            return {
                "function_type": "rewrite_query",
                "is_clear": True,
                "original_data": query,
                "rewritten_data": questions,
                "clarification_needed": ""
            }

        # 若问题不清晰
        if not clarification_needed or len(clarification_needed.strip()) < 10:
            clarification_needed = "I need more information to understand your question."

        return {
            "function_type": "rewrite_query",
            "is_clear": False,
            "original_data": query,
            "rewritten_data": [],
            "clarification_needed": clarification_needed
        }


    @staticmethod
    def _route_after_query_rewrite(state: dict):
        """
            判断问题是否清晰：
            - True  -> 进入并行子图
            - False -> 请求用户补充信息
        """
        if state.get("question_is_clear"):
            return "sub_graphs"
        return "clarify"

    @staticmethod
    def _route_to_sub_graphs(state: dict):
        """
            为 rewritten_questions 中的每个子问题创建一个并行任务。
        """
        return [
            Send(
                "agent_subgraph",
                {
                    "subquestion": question,
                    "original_query": state.get("original_query", ""),
                    "conversation_history": state.get("conversation_history", "")
                }
            )
            for question in state.get("rewritten_questions", [])
        ]

    @staticmethod
    def classify_kb(rewritten_query: str):
        """
            基于每个 rewrite_query 匹配合适的知识库（循环外置在 run 中）
        """
        if rewritten_query is not None:
            # 载入 prompt
            prompt_content = load_prompt('classify_kb_prompt.txt')

            # 调用 LLM
            response_text = RAGService.assisted_query(prompt_content, rewritten_query)

            try:
                result = json.loads(response_text)
            except Exception:
                return {
                    "function_type": "classify_kb",
                    "is_clear": False,
                    "original_data":rewritten_query,
                    "current_data": None,
                    "clarification_needed": ""
                }

            kb_name = result.get("kb_collection", "")
            if kb_name:
                kb_id = kb_name2id(kb_name)
                if kb_id > 0:
                    return {
                        "function_type": "classify_kb",
                        "is_clear": True,
                        "original_data":rewritten_query,
                        "current_data": kb_id,
                        "clarification_needed": ""
                    }

            return {
                "function_type": "classify_kb",
                "is_clear": False,
                "original_data":rewritten_query,
                "current_data": None,
                "clarification_needed": "I need more information to classify your knowledge base."
            }

        return {
            "function_type": "classify_kb",
            "is_clear": False,
            "original_data":rewritten_query,
            "current_data": None,
            "clarification_needed": "I can't rewritten any query text"
        }

    @staticmethod
    def rag_search(query_text, kb_id, top_k=10):
        """
            向量库检索
        """
        return RAGService.query_search(query_text, kb_id, top_k)

    @staticmethod
    def web_search(query_text, history):
        """
            联网搜索
        """
        return call_agent_search(query_text, history)

    @staticmethod
    def evaluate_retrieval(query: str, search_result: dict, conversation_history: str):
        """
            评估当前 RAG 检索结果是否足够回答用户问题

            decision:
                - sufficient   -> 知识库内容足够回答
                - insufficient -> 有一定相关性，但信息不足，需要联网
                - irrelevant   -> 检索内容无关，需要用户补充问题
        """
        # 提取 documents
        documents = search_result.get("documents", [])

        # 检索结果为空
        if not documents:
            return {
                "function_type": "evaluate_retrieval",
                "decision": "insufficient",
                "original_data": query,
                "current_data": [],
                "clarification_needed": "documents not found"
            }

        # 保存 references
        references = []

        # 构建 RAG Context
        rag_context = "以下是与用户问题相关的参考资料：\n\n"
        for idx, doc in enumerate(documents, start=1):
            """
                doc 结构：
                (
                    content,
                    metadata,
                    distance,
                    rerank_score
                )
            """
            # 安全处理
            if not isinstance(doc, (list, tuple)):
                continue
            if len(doc) < 2:
                continue

            content = doc[0]
            metadata = doc[1]

            # reference
            references.append({
                "index": idx,
                "metadata": metadata
            })

            # 拼接 RAG 上下文
            rag_context += f"【参考资料{idx}】\n"
            rag_context += f"{content}\n\n"

        # evaluator 输入
        evaluation_input = (
            f"Conversation History:\n"
            f"{conversation_history}\n\n"
            f"User Question:\n"
            f"{query}\n\n"
            f"{rag_context}"
        )

        # 加载 Prompt
        prompt_content = load_prompt('evaluate_retrieval_prompt.txt')
        # 调用 LLM
        response_text = RAGService.assisted_query(prompt_content, evaluation_input)
        # JSON 解析
        try:
            result = json.loads(response_text)
        except Exception:
            return {
                "function_type": "evaluate_retrieval",
                "decision": "insufficient",
                "original_data": query,
                "current_data": [],
                "clarification_needed": "unexpected wrong appear in json parsing"
            }

        # 提取 decision
        decision = result.get(
            "decision",
            "insufficient"
        )

        # 合法 decision
        valid_decisions = [
            "sufficient",
            "insufficient",
            "irrelevant"
        ]

        if decision not in valid_decisions:
            decision = "insufficient"

        return {
            "function_type": "evaluate_retrieval",
            "decision": decision,
            "original_data": query,
            "current_data": documents,
            "references": references,
            "clarification_needed": result.get(
                "clarification_needed",
                ""
            )
        }

    @staticmethod
    def run(query: str, raw_history: List[MMDataItem],  max_iterations: int = 5) -> Dict[str, Any]:
        """
            运行 Agent 主流程

            流程：
            1. 对话历史总结（如有）
            2. 问题重写与清晰度判断
            3. 并行执行：知识库检索 + 联网搜索（如需要）
            4. 检索结果评估与决策
            5. 答案生成（融合多源信息）
            6. 后处理与返回

            Args:
                query: 用户查询文本
                raw_history: 原始对话历史
                max_iterations: 最大迭代次数（防止死循环）

            Returns:
                包含答案、参考资料、决策历史等的字典
        """
        graph = build_main_graph()

        try:
            result = graph.invoke({
                "query": query,
                "raw_history": raw_history,
                "conversation_history": "",
                "rewritten_questions": [],
                "clarification_needed": "",
                "sub_results": []
            })

            references = []

            for item in result.get("sub_results", []):
                references.extend(item.get("references", []))

            answer = "\n\n".join([
                item.get("answer", "")
                for item in result.get("sub_results", [])
                if item.get("answer")
            ])

            return {
                "success": True,
                "answer": answer,
                "references": references,
                "conversation_history": result.get("conversation_history", ""),
                "rewritten_questions": result.get("rewritten_questions", [])
            }

        except Exception as e:
            return {
                "success": False,
                "answer": "",
                "references": [],
                "conversation_history": "",
                "rewritten_questions": [],
                "error": str(e)
            }