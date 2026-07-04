# 检索链路服务
import hashlib
import json
import os
from typing import List

from models.embed_model import DataItem
from services.chunking_service import document_auto_split, get_document_type


class RAGService:
    # 保存唯一实例
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError('RAGService not initialized')
        if not isinstance(cls._instance, RAGService):
            raise RuntimeError(f'RAGService._instance is not a RAGService instance: {type(cls._instance)}')
        return cls._instance

    def __init__(
            self,
            llm_client,
            embedding_service,
            reranker_service,
            chroma_repo
    ):
        """
            初始化 RAG 服务

            Args:
                llm_client: LLM 服务实例
                embedding_service: 向量化服务实例
                reranker_service: 重排序服务实例
                chroma_repo: Chroma 仓库实例
        """
        self.llm_client = llm_client
        self.embedding_service = embedding_service
        self.reranker_service = reranker_service
        self.chroma_repo = chroma_repo

        self.folder_to_collection = json.loads(os.getenv('CHROMA_COLLECTIONS', '{}')) if os.getenv('CHROMA_COLLECTIONS', '{}') else {}

        RAGService._instance = self
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"RAGService initialized: {self}")
        logger.info(f"RAGService._instance type: {type(RAGService._instance)}")
        logger.info(f"embedding_service type: {type(self.embedding_service)}")

    def query_search(self, query_text, kb_id, top_k=10):
        """
            执行 RAG 查询检索

            流程：查询向量化 → 向量检索召回 → 重排 → 基于 token 限度和动态阈值筛选

            Args:
                query_text: 查询文本
                kb_id: 知识库 ID
                top_k: 召回数量，默认 10

            Returns:
                包含 documents 和 metrics 的字典
                    - documents: 筛选后的文档列表
                    - metrics: 筛选统计信息（threshold、selected_count、total_tokens）
        """
        # step1 查询向量化
        query_embedding = self.embedding_service.embed_texts([query_text])[0]

        # step2 向量检索召回
        kb_id_to_collection = {
            1: "legal_kb_vectors",
            2: "anti_fraud_kb_vectors",
            3: "health_rumor_busting_kb_vectors"
        }
        collection_name = kb_id_to_collection.get(kb_id, "legal_kb_vectors")
        results = self.chroma_repo.query(
            collection_name=collection_name,
            query_embedding=query_embedding,
            kb_id=kb_id,
            top_k=top_k
        )
        
        docs = []
        metas = []
        distances = []
        
        if isinstance(results, list):
            # 提取各个字段
            docs = [item.get('content', '') for item in results]
            metas = [item.get('metadata', {}) for item in results]
            distances = [item.get('score', '') for item in results]

        # step3 重排
        rerank_scores = self.reranker_service.rerank(query_text, docs)
        reranked = sorted(
            zip(docs, metas, distances, rerank_scores),
            key = lambda x: x[3],
            reverse=True
        )

        # step4 考虑token限度并基于动态阈值的重排后筛选
        selected_docs, metrics = self.reranker_service.select_top_documents(reranked_results=reranked)
        return {
            "documents": selected_docs,
            "metrics": metrics
        }

    @classmethod
    def assisted_query_stream(cls, prompt: str, conversation: str):
        instance = cls.get_instance()
        yield from instance._assisted_query_stream(prompt, conversation)

    def _assisted_query_stream(self, prompt, conversation):
        response = self.llm_client.chat.completions.create(
            model=os.getenv("LLM_OPENAI_MODEL_NAME", "MiniMax-Text-01"),
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": conversation
                }
            ],
            temperature=0.2,
            stream=True  # ← 唯一新增
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    @classmethod
    def assisted_query(cls, prompt: str, conversation: str) -> str:
        instance = cls.get_instance()
        return instance._assisted_query(prompt, conversation)

    def _assisted_query(self, prompt: str, conversation: str):
        response = self.llm_client.chat.completions.create(
            model=os.getenv('LLM_OPENAI_MODEL_NAME', 'MiniMax-Text-01'),
            messages = [
                {
                    'role': 'system',
                    'content': prompt
                },
                {
                    'role': 'user',
                    'content': conversation
                }
            ],
            temperature = 0.2
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _generate_document_id(file_path: str) -> int:
        """
            基于文件路径生成稳定的 document_id

            Args:
                file_path: 文件路径

            Returns:
                8位十六进制整数作为文档ID
        """
        hash_val = hashlib.md5(file_path.encode("utf-8")).hexdigest()
        return int(hash_val[:8], 16)

    def build_data_items_from_article_data(self) -> List[DataItem]:
        """
            扫描 static/article_data 目录下三个知识库文件夹，
            调用 chunking_service 分段，构造 DataItem 列表

            三个知识库映射：
                - legal_knowledge: 法律知识库
                - anti_fraud_knowledge: 反诈骗知识库
                - health_rumor_busting_knowledge: 健康辟谣知识库

            Returns:
                data_items 列表，每个包含 kb_id、document_id、collection_name、context
        """
        base_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "static", "article_data")
        )

        all_items = []

        for folder_name, collection_name in self.folder_to_collection.items():

            folder_path = os.path.join(base_path, folder_name)
            if not os.path.exists(folder_path):
                continue

            for root, _, files in os.walk(folder_path):
                for file in files:
                    if get_document_type(file) != "md":
                        print(f"跳过非 md 文件：{file}")
                        continue

                    file_path = os.path.join(root, file)

                    paragraphs = document_auto_split(file_path)

                    document_id = self._generate_document_id(file_path)

                    for p in paragraphs:
                        content = p.content.strip()
                        if not content:
                            continue

                        data_item = DataItem(
                            kb_id=1,  # 目前唯一知识库
                            document_id=document_id,
                            title=p.title  or "",
                            parent_chain=p.parentChain,
                            collection_name=collection_name,  # 划分 collection
                            context=content
                        )

                        all_items.append(data_item)

        return all_items

    def build_and_store_all_articles(self):
        """
            全量构建知识库向量

            流程：扫描文档 → 分块 → 向量化 → 存储到 Chroma
        """

        print("Start building article vectors...")

        data_items = self.build_data_items_from_article_data()

        if not data_items:
            print("No data found.")
            return

        print(f"Total segments: {len(data_items)}")

        success_count, failed = self.embedding_service.process_and_store(data_items)

        print(f"Stored: {success_count}")
        print(f"Failed: {len(failed)}")