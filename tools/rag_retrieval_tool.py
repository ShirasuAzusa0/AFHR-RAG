from typing import Dict, Any
from services.rag_service import RAGService
from tools.base_tool import BaseTool

class RAGRetrievalTool(BaseTool):
    def __init__(self, rag_service: RAGService):
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
        result = self.rag_service.query_search(query_text=query, kb_id=kb_id)
        return {
            "tool_name": self.name,
            "documents": result["documents"],
            "metrics": result["metrics"]
        }