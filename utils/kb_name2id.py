# 知识库映射
COLLECTION_TO_KB_ID = {
    "legal_kb_vectors": 1,
    "anti_fraud_kb_vectors": 2,
    "health_rumor_busting_kb_vectors": 3,
}

def kb_name2id(kb_name: str) -> int:
    """
        根据知识库名称获取对应的知识库 ID

        功能: 将 Collection 名称映射为数字 ID

        Args:
            kb_name: 知识库名称（如 "legal_kb_vectors"）

        Returns:
            int: 对应的知识库 ID，如果未找到则返回 -1
    """
    kb_id = COLLECTION_TO_KB_ID.get(kb_name)
    if kb_id:
        return kb_id
    else:
        return -1
