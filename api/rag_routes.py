from flask import Blueprint, request

from utils.api_response import api_response


def create_rag_routes(rag_service):
    """
    带依赖注入的 Blueprint 工厂函数，设置路由前缀为'/api/rag/v1/er'
    """
    rag_bp = Blueprint(
        'rag_routes',
        __name__,
        url_prefix='/api/rag/v1/er',
    )

    """--------------------- HTTP 接口 ----------------------"""
    @rag_bp.route('/search', methods=['POST'])
    def search():
        data = request.get_json()
        query = data['query']
        kb_id = data['kb_id']

        # agentic RAG mode
        # result = rag_service.run(query, kb_id)

        # classic RAG mode
        result = rag_service.query_search(query, kb_id)
        return api_response(data=result)

    return rag_bp