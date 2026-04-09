import os
import torch
from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM
import logging

logger = logging.getLogger(__name__)

# 设备检测
device = "cuda" if torch.cuda.is_available() else "cpu"

# 模型单例
_embedding_model = None
_reranker_model = None

def get_embedding_model(model_path: str = None):
    """
    获取embedding模型单例
    """
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    if model_path is None:
        model_path = os.getenv('EMBEDDING_MODEL_PATH', './model/embedding')

    model_path = os.path.abspath(model_path)
    logger.info(f"📦 Loading embedding model from: {model_path} on {device}")

    # 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        padding_side="left",
        local_files_only=True,
        trust_remote_code=True
    )

    # 模型加载参数
    model_kwargs = {
        'trust_remote_code': True,
        'local_files_only': True
    }

    if device == 'cuda':
        model_kwargs.update({
            'attn_implementation': 'sdpa',
            'dtype': torch.float16
        })

    # 加载模型
    model = AutoModel.from_pretrained(
        model_path,
        **model_kwargs
    ).to(device)

    model.eval()

    _embedding_model = (tokenizer, model)
    logger.info(f"✅ Loaded embedding model from {model_path}")

    return _embedding_model

def get_reranker_model(model_path: str = None):
    """
    获取reranker模型单例
    """
    global _reranker_model

    if _reranker_model is not None:
        return _reranker_model

    if model_path is None:
        model_path = os.getenv('RERANKER_MODEL_PATH', './model/reranker')

    model_path = os.path.abspath(model_path)
    logger.info(f"📦 Loading reranker model from: {model_path} on {device}")

    # 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        padding_side="left",
        local_files_only=True,
        trust_remote_code=True
    )

    # 模型加载参数
    model_kwargs = {
        'trust_remote_code': True,
        'local_files_only': True
    }

    if device == 'cuda':
        model_kwargs.update({
            'attn_implementation': 'sdpa',
            'dtype': torch.float16
        })

    # 加载模型
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        **model_kwargs
    ).to(device)

    model.eval()

    # 加载reranker特殊token
    token_false_id = tokenizer.convert_tokens_to_ids("no")
    token_true_id = tokenizer.convert_tokens_to_ids("yes")

    prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
    suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)

    _reranker_model = (
        tokenizer,
        model,
        token_true_id,
        token_false_id,
        prefix_tokens,
        suffix_tokens,
        8192                # max length
    )

    logger.info(f"✅ Loaded reranker model from {model_path}")

    return _reranker_model