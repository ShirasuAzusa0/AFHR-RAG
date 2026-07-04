from flask import Blueprint, request, Response, stream_with_context
from queue import Queue
from threading import Thread
import json

from utils.api_response import api_response

# def create_rag_routes(rag_service):
def create_rag_routes(agent_service):
    """
        带依赖注入的 Blueprint 工厂函数，设置路由前缀为'/api/rag/v1/er'
        Args:
            agent_service: Agentic RAG 服务实例
        Returns:
            rag_bp: Flask Blueprint 对象，注册后可通过 '/api/rag/v1/er/search' 访问
    """
    rag_bp = Blueprint(
        'rag_routes',
        __name__,
        url_prefix='/api/rag/v1/er',
    )

    """--------------------- HTTP 接口 ----------------------"""
    @rag_bp.route('/search', methods=['POST'])
    def search():
        """
            Agentic RAG 流式响应搜索接口，AFHR-RAG 模块调用总入口
            Request:
                query: str，必须项，用户查询问题文本
                history: list，必须项，用户历史对话列表
            Returns:
                Response: SSE 流式响应对象，mimetype 为 text/event-stream
        """
        # 1. 解析请求参数
        data = request.get_json()
        query = data['query']
        history = data['history']

        # 2. 创建队列用于线程间通信（主线程 <-> 工作线程）
        q = Queue()

        # 3. 定义回调函数：工作线程每生成一个 token 就放入队列
        def callback(token):
            q.put(token)

        # 4. 工作线程：执行 RAG 服务调用，将结果和结束标记放入队列
        def worker():
            sse_result = agent_service.run(
                query=query,
                raw_history=history,
                stream_callback=callback  # ← 这里才真正赋值
            )

            q.put({
                "__end__": True,
                "references": sse_result.get("references", []),
                "conversation_history": sse_result.get("conversation_history", ""),
                "rewritten_questions": sse_result.get("rewritten_questions", [])
            })

        # 5. 启动工作线程（非阻塞）
        Thread(target=worker).start()

        # 6. 生成器函数：从队列中读取数据并格式化为 SSE
        def generate():
            while True:
                item = q.get()

                if isinstance(item, dict) and item.get("__end__"):
                    yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                    break

                yield "data: " + json.dumps({
                    "type": "token",
                    "content": item
                }, ensure_ascii=False) + "\n\n"

        # 7. 返回流式响应（使用 stream_with_context 保持上下文）
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream"
        )

        # agentic RAG mode
        # result = agent_service.run(query, history)

        # classic RAG mode
        # result = rag_service.query_search(query, history)
        # return api_response(data=result)

    return rag_bp