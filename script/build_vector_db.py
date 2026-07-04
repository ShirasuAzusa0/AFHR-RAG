import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

load_dotenv()

from repositories.chroma_repository import ChromaRepository
from services.rag_service import RAGService
from services.embed_service import EmbeddingService
from services.rerank_service import RerankerService
from utils.model_loader import (get_embedding_model, get_reranker_model)


KB_MAPPING = {
    "legal_knowledge": 1,
    "anti_fraud_knowledge": 2,
    "health_rumor_busting_knowledge": 3
}


def build_rag():
    """
        构建 RAG 服务实例

        功能：初始化所有依赖组件并组装成 RAGService

        返回：
            RAGService: 配置好的 RAG 服务实例
    """
    chroma = ChromaRepository()
    emb_tok, emb_model = (get_embedding_model())
    rr = get_reranker_model()

    return RAGService(
        llm_client=OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_OPENAI_BASE_URL")
        ),
        embedding_service=EmbeddingService(emb_tok, emb_model, chroma),
        reranker_service=RerankerService(*rr),
        chroma_repo=chroma
    )


def main():
    """
        主函数：执行文档解析、向量化并写入知识库的完整流程

        流程：
            1. 初始化 RAG 服务
            2. 从文章数据解析数据块
            3. 显示各 Collection 的数据分布
            4. 根据文件夹名称映射知识库 ID
            5. 向量化并批量写入 Chroma
            6. 输出执行结果统计
    """

    print("\n========== 初始化 RAG ==========\n")

    rag = build_rag()

    print("========== 开始解析文档 ==========\n")

    items = (rag.build_data_items_from_article_data())

    print(f"\n解析完成，共生成 {len(items)} 个数据块\n")

    collection_counter = Counter(item.collection_name for item in items)

    print("========== Collection 分布 ==========\n")

    for name, count in (sorted(collection_counter.items())):
        print(f"{name:<35} {count}")

    print()
    print("========== 映射知识库 ==========\n")

    for item in tqdm(items, desc="知识库映射", unit="item"):
        folder = next(
            (
                k
                for k, v
                in rag.folder_to_collection.items()
                if v == item.collection_name
            ),
            None
        )

        if folder:
            item.kb_id = KB_MAPPING[folder]

    print("\n========== 开始向量化并写入 ==========\n")

    success, failed = (
        rag.embedding_service
        .process_and_store(items)
    )

    print("\n========== 执行完成 ==========\n")
    print(f"success={success}")
    print(f"failed={len(failed)}")

    if failed:
        print("\n失败样例：")

        for i, item in enumerate(failed[:10], start=1):
            print(f"{i}. {item}")


if __name__ == "__main__":
    main()