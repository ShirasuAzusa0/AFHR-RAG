from typing import Dict, Any, List
from tools.rag_retrieval_tool import RAGRetrievalTool

class AgentService:
    def __init__(
            self,
            retrieval_tool: RAGRetrievalTool,
            max_iterations: int = 3,
            min_selected_docs: int = 3,
            min_total_tokens: int = 800
    ):
        self.retrieval_tool = retrieval_tool
        self.max_iterations = max_iterations
        self .min_selected_docs = min_selected_docs
        self.min_total_tokens = min_total_tokens

    def run(self, query: str, kb_id: int) -> Dict[str, Any]:
        iteration = 0
        top_k = 10

        aggregated_documents: List[Dict] = []
        final_metrics = {}

        while iteration < self.max_iterations:
            result = self.retrieval_tool.run(
                query=query,
                kb_id=kb_id,
                top_k=top_k
            )

            documents = result["documents"]
            metrics = result["metrics"]

            aggregated_documents.extend(documents)
            final_metrics = metrics

            if self._is_sufficient(metrics):
                break

            # 信息不足时，扩大搜索范围
            top_k *= 2
            iteration += 1

        # 去重
        unique_docs = self._deduplicate(aggregated_documents)

        return {
            "documents": unique_docs,
            "metrics": final_metrics,
            "iterations": iteration + 1
        }

    def _is_sufficient(self, metrics: Dict[str, Any]) -> bool:

        selected_count = metrics.get("selected_count", 0)
        total_tokens = metrics.get("total_tokens", 0)

        if selected_count < self.min_selected_docs:
            return False

        if total_tokens < self.min_total_tokens:
            return False

        return True

    @staticmethod
    def _deduplicate(documents: List[Dict]) -> List[Dict]:

        seen = set()
        unique = []

        for doc in documents:
            content = doc.get("content")
            if content not in seen:
                seen.add(content)
                unique.append(doc)

        return unique
