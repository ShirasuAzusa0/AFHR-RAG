import os

import requests
import json

API_KEY = os.getenv('WEB_SEARCH_API_KEY', "")
BOT_ID = os.getenv('WEB_SEARCH_AGENT_ID', "")
API_URL = os.getenv('WEB_SEARCH_BASE_URL', "")

def call_agent_search(query, history):
    """
        调用火山引擎联网问答 Agent，支持多轮对话记忆
        Args:
            query (str): 当前用户问题
            history (list, optional): 历史对话列表，格式为 [{"role": "user/assistant", "content": "..."}]
        Returns:
            full_response: 响应结果
            references: 参考引用，数据信息来源
    """
    if history is None:
        history = []

    if type(history) == str:
        history = [{"role": "user", "content": history}]

    # 构造完整的消息列表
    messages = history + [{"role": "user", "content": query}]

    if len(messages) > 10:
        if messages and messages[0].get("role") == "system":
            messages = [messages[0]] + messages[-9:]
        else:
            messages = messages[-10:]

    # 构造请求体
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "bot_id": BOT_ID,
        "messages": messages
    }

    # 发送请求
    response = requests.post(API_URL, headers=headers, json=payload, stream=True)
    response.encoding = "utf-8"

    # 处理流式响应
    full_response = ""
    references = []

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        # 处理 SSE 数据行
        if line.startswith("data:"):
            data_str = line[5:].strip()

            # 流结束标识
            if data_str == "[DONE]":
                break

            # 解析JSON数据
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # 提取引用信息
            if "references" in chunk and chunk["references"]:
                references = chunk["references"]

            # 提取增量内容
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    # 确保 content 是字符串
                    if isinstance(content, list):
                        content = "".join(str(c) for c in content)
                    elif not isinstance(content, str):
                        content = str(content)
                    # print(content, end="", flush=True)  # 实时打印
                    full_response += content

                    # print("\n")
    return full_response, references