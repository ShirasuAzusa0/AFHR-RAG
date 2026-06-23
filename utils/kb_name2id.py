# 知识库映射
COLLECTION_TO_KB_ID = {
    "legal_kb_vectors": 1,
    "anti_fraud_kb_vectors": 2,
    "health_rumor_busting_kb_vectors": 3,
}

def kb_name2id(kb_name: str) -> int:
    kb_id = COLLECTION_TO_KB_ID.get(kb_name)
    if kb_id:
        return kb_id
    else:
        return -1
