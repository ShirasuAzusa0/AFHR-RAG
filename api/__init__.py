from flask import Flask
from flask_cors import CORS
import logging

from repositories.chroma_repository import ChromaRepository
from services.rag_service import RAGService
from services.embed_service import EmbeddingService
from services.rerank_service import RerankerService
from utils.model_loader import get_embedding_model, get_reranker_model
from rag_routes import create_rag_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """
        创建并配置 Flask 应用实例

        初始化 Chroma 仓库、Embedding 模型、Reranker 模型，
        注册路由并返回配置好的应用对象。

        Returns:
            配置完成的 Flask 应用实例
    """
    app = Flask(__name__)

    # 解决跨域问题
    CORS(app)

    logger.info("Initializing application...")

    # 初始化 Chroma Repository
    chroma_repo = ChromaRepository()

    # 加载 embedding 模型
    embedding_tokenizer, embedding_model = get_embedding_model()

    # 加载 reranker 模型
    reranker_tokenizer, reranker_model, token_true_id, token_false_id, prefix_tokens, suffix_tokens, max_length = get_reranker_model()

    # 创建 Service
    rag_service = RAGService(
        embedding_service=EmbeddingService(
            embedding_tokenizer,
            embedding_model,
            chroma_repo
        ),
        reranker_service=RerankerService(
            reranker_tokenizer,
            reranker_model,
            token_true_id,
            token_false_id,
            prefix_tokens,
            suffix_tokens,
            max_length
        ),
        chroma_repo=chroma_repo
    )

    app.rag_service = rag_service

    # 注册路由
    rag_bp = create_rag_routes(rag_service)
    app.register_blueprint(rag_bp)

    @app.route("/")
    def index():
        return {
            "service": "AFHR RAG Service",
            "status": "running"
        }

    return app