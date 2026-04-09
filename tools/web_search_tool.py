import os
import json
import requests
from pathlib import Path
from typing import Dict, Any, List


class WebSearchTool:
    """
    基于 LLM 的外部知识补充工具（Synthetic Web Search）

    不是调用真实搜索引擎，
    而是利用 LLM 生成高质量补充知识。
    """
    def __init__(
        self,
        api_key: str = os.getenv("WEB_SEARCH_API_KEY", ""),
        llm_url: str = os.getenv("WEB_SEARCH_BASE_URL", ""),
        model: str = "M2-her",
        max_tokens: int = 800,
        temperature: float = 0.3
    ):
        self.api_key = api_key
        self.llm_url = llm_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def run(self, query: str, top_k: int = 5) -> Dict[str, Any]:

        prompt = self._build_prompt(query, top_k)

        raw_text = self._call_llm(prompt)

        documents = self._parse_response(raw_text, top_k)

        total_tokens = sum(
            len(doc.get("content", "")) // 4
            for doc in documents
        )

        return {
            "documents": documents,
            "metrics": {
                "selected_count": len(documents),
                "total_tokens": total_tokens
            }
        }

    @staticmethod
    def _load_prompt_template() -> str:
        prompt_path = Path("prompts/web_expansion_prompt.txt")
        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(self, query: str, top_k: int) -> str:
        template = self._load_prompt_template()
        return template.format(
            query=query,
            top_k=top_k
        )

    def _call_llm(self, prompt: str) -> str:

        url = f"{self.llm_url}/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": "You generate structured external knowledge expansions.",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "content" in data:
            texts = [
                block.get("text", "")
                for block in data["content"]
                if block.get("type") == "text"
            ]
            return "".join(texts)

        return ""

    @staticmethod
    def _parse_response(raw_text: str, top_k: int) -> List[Dict]:

        try:
            parsed = json.loads(raw_text)
            items = parsed.get("results", [])[:top_k]

            documents = []
            for item in items:
                content = item.get("content", "")
                if content:
                    documents.append({
                        "content": content,
                        "source": "llm_web_expansion",
                        "score": 0.5
                    })

            return documents

        except Exception:
            return []