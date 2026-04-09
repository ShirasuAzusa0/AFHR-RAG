import json
import os
from pathlib import Path

class ChromaConfig:
    # Chroma 连接配置
    CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
    CHROMA_PORT = os.getenv('CHROMA_PORT', '8001')
    CHROMA_SSL = os.getenv('CHROMA_SSL', 'false').lower() == 'true'

    # 持久化配置（本地模式）
    CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', str(Path(__file__).parent.parent / 'chroma_data'))

    # 结合名称 Collection 配置 - 解析JSON字符串为字典
    _collections_str = os.getenv('CHROMA_COLLECTIONS', '{}')
    CHROMA_COLLECTIONS = json.loads(_collections_str) if _collections_str else {}

    # 连接方式
    CHROMA_COLLECTION_TYPE = os.getenv('CHROMA_CONNECTION_TYPE', 'http')

    @classmethod
    def get_chroma_settings(cls):
        # 获取 Chroma 设置
        if cls.CHROMA_COLLECTION_TYPE == 'http':
            return {
                'type': 'http',
                'host': cls.CHROMA_HOST,
                'port': cls.CHROMA_PORT,
                'ssl': cls.CHROMA_SSL,
                'path': cls.CHROMA_PERSIST_DIR,
                'collections': cls.CHROMA_COLLECTIONS
            }
        else:
            return {
                'type': 'persistent',
                'path': cls.CHROMA_PERSIST_DIR
            }