import chromadb
from typing import List, Dict, Any
import logging

from configs.chroma_config import ChromaConfig

logger = logging.getLogger(__name__)

class ChromaRepository:

    _client = None
    _collections = {}

    def __init__(self):
        """
            初始化 Chroma 仓库，加载配置，创建或复用 Client 与 Collections
        """
        self.config = ChromaConfig()

        if ChromaRepository._client is None:
            ChromaRepository._client = self._create_client()
            logger.info("Chroma client created")

        self.client = ChromaRepository._client

        # 初始化所有 collection
        if not ChromaRepository._collections:
            for kb_name, collection_name in self.config.CHROMA_COLLECTIONS.items():
                ChromaRepository._collections[collection_name] = self._get_or_create_collection(collection_name)

        self.collections = ChromaRepository._collections
        logger.info(f"Collection initialized: {self.config.CHROMA_COLLECTIONS}")

    def _create_client(self) -> chromadb.Client():
        """
            根据配置创建 HttpClient 或 PersistentClient

            Returns:
                Chroma 客户端实例
        """
        if self.config.CHROMA_COLLECTION_TYPE == 'http':
            return chromadb.HttpClient(
                host=self.config.CHROMA_HOST,
                port=self.config.CHROMA_PORT,
                ssl=self.config.CHROMA_SSL
            )
        else:
            return chromadb.PersistentClient(
                path=self.config.CHROMA_PERSIST_DIR
            )

    def _get_or_create_collection(self, collection_name: str):
        """
            初始化阶段使用的内部方法，获取已存在的集合，若不存在则创建新集合（默认 cosine 距离）

            Args:
                collection_name: 集合名称

            Returns:
                Chroma 集合实例
        """
        existing_collections = {
            col.name: col
            for col in self.client.list_collections()
        }

        if collection_name in existing_collections:
            return existing_collections[collection_name]

        logger.info(f"Creating collection: {collection_name}")

        return self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def _get_collection(self, collection_name: str):
        """
            运行阶段使用的内部方法，从字典里安全取出对应 collection

            Args:
                collection_name: 集合真实名称

            Returns:
                Chroma 集合实例

            Raises:
                ValueError: 知识库名称未配置时抛出
        """
        if collection_name not in self.collections:
            raise ValueError(f"Knowledge base '{collection_name}' not configured")

        return self.collections[collection_name]

    def add_vectors(
            self,
            collection_name: str,
            ids: List[str],
            embeddings: List[List[float]],
            metadatas: List[Dict[str, Any]],
            documents: List[str]
    ):
        """
            向指定集合中批量添加向量数据、元数据以及原始文本

            Args:
                collection_name: 集合显示名称
                ids: 向量唯一标识符列表
                embeddings: 向量列表
                metadatas: 元数据字典列表
                documents: 原始文本列表
        """
        collection = self._get_collection(collection_name)

        batch_size = 5000

        for start in range(0, len(ids), batch_size):
            end = min(
                start + batch_size,
                len(ids)
            )

            collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
                documents=documents[start:end]
            )

            logger.info(
                f"[{collection_name}] "
                f"{end}/{len(ids)} inserted"
            )

    def delete_all_in_collection(self, collection_name: str):
        """
           根据集合名称 collection_name 删除对应向量数据

           Args:
               collection_name: 集合显示名称
        """
        collection = self._get_collection(collection_name)
        collection.delete(where={})

    def delete_by_document_id(self, collection_name: str, document_id: int):
        """
            根据知识库中的文档的 document_id 和集合名称 collection_name 删除对应向量数据

            Args:
                collection_name: 集合显示名称
                document_id: 文档ID
        """
        collection = self._get_collection(collection_name)
        collection.delete(where={"document_id": document_id})

    def count(self, collection_name: str):
        """
            返回指定集合中存储的向量总数量

            Args:
                collection_name: 集合显示名称

            Returns:
                向量总数
        """
        collection = self._get_collection(collection_name)
        return collection.count()

    def query(
            self,
            collection_name: str,
            query_embedding: List[float],
            top_k: int,
            kb_id: int = None
    ):
        """
            根据 embedding 后的 query 在指定知识库中进行向量检索

            Args:
                collection_name: 集合显示名称
                query_embedding: 查询向量
                top_k: 返回结果数量
                kb_id: 知识库ID，用于过滤，为 None 时不过滤

            Returns:
                检索结果列表，每项包含 id、content、metadata、score

            Raises:
                ValueError: 查询参数错误时抛出
        """
        try:
            collection = self._get_collection(collection_name)

            where_clause = {"kb_id": kb_id} if kb_id is not None else None

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause
            )

            # 统一整理返回结构
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]

            formatted_results = []

            for i in range(len(documents)):
                formatted_results.append({
                    "id": ids[i],
                    "content": documents[i],
                    "metadata": metadatas[i],
                    # 距离转相似度
                    "score": 1 - distances[i]
                })

            return formatted_results

        except ValueError as e:
            logger.error(f"Query error: {e}")
            raise