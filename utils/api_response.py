from flask import jsonify
from typing import Any, Optional, Dict

def api_response(
        data: Any = None,
        message: str = "响应数据返回成功",
        code: int = 200,
        status: str = "success"
) -> tuple:
    """
        统一成功响应格式

        Args:
            data: 响应数据，默认为 None
            message: 响应消息，默认 "Success"
            code: HTTP 状态码，默认 200
            status: 状态标识，默认 "success"

        Returns:
            (response_json, status_code): Flask 响应对象和状态码
    """
    response = {
        "status": status,
        "code": code,
        "message": message,
        "data": data
    }
    return jsonify(response), code

def api_error(
        message: str = "Bad request，响应出错",
        code: int = 400,
        status: str = "error",
        errors: Optional[Dict] = None
) -> tuple:
    """
        统一错误响应格式

        Args:
            message: 错误消息，默认 "Error"
            code: HTTP 状态码，默认 400
            status: 状态标识，默认 "error"
            errors: 详细错误信息字典，默认为 None

        Returns:
            (response_json, status_code): Flask 响应对象和状态码
    """
    response = {
        "status": status,
        "code": code,
        "message": message,
        "errors": errors or {}
    }
    return jsonify(response), code