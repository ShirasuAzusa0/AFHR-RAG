from flask import jsonify, g
from typing import Any, Optional, Dict
import uuid

def api_response(
        data: Any = None,
        message: str = "Success",
        code: int = 200,
        request_id: Optional[str] = None,
) -> tuple:
    """
        统一成功响应格式

        Args:
            data: 响应数据，默认为 None
            message: 响应消息，默认 "Success"
            code: HTTP 状态码，默认 200
            request_id: 响应 id，默认为 None

        Returns:
            (response_json, status_code): Flask 响应对象和状态码
    """
    response = {
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id or getattr(g, 'request_id', None) or str(uuid.uuid4())
    }
    return jsonify(response), code

def api_error(
        message: str = "Bad request，响应出错",
        code: int = 400,
        errors: Optional[Dict] = None,
        request_id: Optional[str] = None,
) -> tuple:
    """
        统一错误响应格式

        Args:
            message: 错误消息，默认 "Error"
            code: HTTP 状态码，默认 400
            errors: 详细错误信息字典，默认为 None
            request_id: 响应 id，默认为 None

        Returns:
            (response_json, status_code): Flask 响应对象和状态码
    """
    response = {
        "code": code,
        "message": message,
        "errors": errors or {},
        "request_id": request_id or getattr(g, 'request_id', None) or str(uuid.uuid4())
    }
    return jsonify(response), code