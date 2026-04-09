from typing import Dict, Any
from services.rag_service import RAGService
from tools.base_tool import BaseTool

class RAGRetrievalTool(BaseTool):
    """
    RAG 检索工具
    封装 RAG 服务的检索功能，作为 Agent 可调用的工具
    """
    def __init__(self, rag_service: RAGService):
        """
            初始化 RAG 检索工具

            Args:
                rag_service: RAG 服务实例
        """
        super().__init__(
            name="rag_retrieval",
            description="Perform vector retrieval and rerank from knowledge base"
        )
        self.rag_service = rag_service

    def run(
            self,
            query: str,
            kb_id: int,
            top_k: int = 10
    ) -> Dict[str, Any]:
        """
            执行 RAG 检索

            Args:
                query: 查询文本
                kb_id: 知识库 ID
                top_k: 召回数量，默认 10

            Returns:
                包含 tool_name、documents、metrics 的字典
                    - tool_name: 工具名称
                    - documents: 检索到的文档列表
                    - metrics: 检索指标（阈值、筛选数量、总 token 数等）
        """
        result = self.rag_service.query_search(query_text=query, kb_id=kb_id)
        return {
            "tool_name": self.name,
            "documents": result["documents"],
            "metrics": result["metrics"]
        }