import hashlib

import torch
import torch.nn.functional as f
from torch import Tensor
import logging
from typing import List, Dict, Tuple

from models.embed_model import DataItem

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
        构造函数
    """
    def __init__(self, tokenizer, model, chroma_repo):
        self.tokenizer = tokenizer
        self.model = model
        self.chroma_repo = chroma_repo
        self.device = next(model.parameters()).device

        logger.info(f"EmbeddingService initialized on {self.device}")

    @staticmethod
    def last_token_pool(last_hidden_states: Tensor, attention_mask: Tensor) -> Tensor:
        """
            取最后一个有效 token 的隐藏状态作为句向量

            Args:
                last_hidden_states: 最后一层隐藏状态，形状 (batch_size, seq_len, hidden_size)
                attention_mask: 注意力掩码，形状 (batch_size, seq_len)，1表示有效token

            Returns:
                池化后的句向量，形状 (batch_size, hidden_size)

            Note:
                自动区分 left padding 和 right padding 场景
        """
        left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])

        if left_padding:
            return last_hidden_states[:, -1]
        else:
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]

            return last_hidden_states[
                torch.arange(batch_size, device=last_hidden_states.device),
                sequence_lengths
            ]

    @torch.no_grad()
    def _embed_texts(self, texts: List[str], max_length: int = 8192):
        """
            将文本列表转换为向量嵌入

            Args:
                texts: 待编码的文本列表
                max_length: 最大序列长度，默认8192

            Returns:
                文本向量数组，形状 (len(texts), hidden_size)
        """
        batch_dict = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        )

        batch_dict = {k: v.to(self.device) for k, v in batch_dict.items()}

        outputs = self.model(**batch_dict)

        embeddings = self.last_token_pool(
            outputs.last_hidden_state,
            batch_dict["attention_mask"]
        )

        embeddings = f.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()

    def _batch_embed(self, texts: List[str], batch_size=None):
        """
            批量将文本列表转换为向量嵌入，支持动态 batch size

            Args:
                texts: 待编码的文本列表
                batch_size: 每批处理的文本数量
                    - 为 None 时自动检测 GPU 显存并设置：
                      * 显存 < 8GB: batch_size = 4
                      * 显存 < 16GB: batch_size = 8
                      * 显存 ≥ 16GB: batch_size = 16
                      * 无 GPU: batch_size = 4
                    - 指定数值时使用该值

            Returns:
                文本向量列表，每个元素为形状 (hidden_size,) 的向量
        """
        # 动态 batch 适配 GPU
        if batch_size is None:
            if torch.cuda.is_available():
                total_mem = torch.cuda.get_device_properties(0).total_memory

                if total_mem < 8 * 1024 ** 3:
                    batch_size = 4
                elif total_mem < 16 * 1024 ** 3:
                    batch_size = 8
                else:
                    batch_size = 16
            else:
                batch_size = 4

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self._embed_texts(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def process_and_store(
            self,
            data_items: List[DataItem]
    ) -> Tuple[int, List[Dict]]:
        """
            处理传输过来的原始数据，构造ID、生成metadata，批量embedding并存入Chroma

            Args:
                data_items: 待处理的数据项列表，每项包含 kb_id、document_id、context

            Returns:
                (success_count, failed_items): 成功处理数量与失败项列表
        """
        if not data_items:
            return 0, []

        from collections import defaultdict

        grouped_items = defaultdict(list)
        for item in data_items:
            grouped_items[item.collection_name].append(item)

        total_success = 0
        failed_items = []

        for collection_name, items in grouped_items.items():

            ids = []
            documents = []
            metadatas = []
            texts_to_embed = []

            for item in items:
                try:
                    # 生成稳定 hash
                    content = item.context.strip()
                    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

                    unique_id = f"{item.kb_id}_{item.document_id}_{content_hash}"
                    metadata = {
                        "kb_id": item.kb_id,
                        "document_id": item.document_id,
                        "collection_name": item.collection_name
                    }

                    ids.append(unique_id)
                    documents.append(item.context)
                    metadatas.append(metadata)
                    texts_to_embed.append(item.context)

                except Exception as e:
                    logger.error(f"Prepare failed: {str(e)}")
                    failed_items.append({
                        "kb_id": item.kb_id,
                        "document_id": item.document_id,
                        # 预览前 100 字符
                        "context_preview": item.context[:100] if item.context else "",
                        "error": str(e)
                    })

            if not texts_to_embed:
                continue

            try:
                embeddings = self._batch_embed(texts_to_embed)
                self.chroma_repo.add_vectors(
                    collection_name=collection_name,
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
                total_success += len(ids)
            except Exception as e:
                logger.error(f"Processing failed: {str(e)}")

        return total_success, failed_items

    def delete_vector(self, id_type: str, data_id: int):
        """
            根据知识库 ID 或文档 ID 删除对应的向量数据

            Args:
                id_type: 删除类型，'kb' 表示按知识库ID删除，其他值表示按文档ID删除
                data_id: 对应的知识库ID或文档ID

            Returns:
                是否删除成功
        """
        if id_type == 'kb':
            return self.chroma_repo.delete_by_kb_id(data_id)
        else:
            return self.chroma_repo.delete_by_document_id(data_id)

    def get_statistics(self):
        """
           获取当前向量总数和服务健康状态

           Returns:
               包含 total_vectors 和 status 的字典
       """
        total = self.chroma_repo.count()
        return {
            "total_vectors": total,
            "status": "healthy"
        }

    def embed_texts(self, texts: List[str]):
        """
            将文本列表批量转换为向量嵌入（总入口）

            Args:
                texts: 待编码的文本列表

            Returns:
                文本向量列表，每个元素为形状 (hidden_size,) 的向量
        """
        return self._batch_embed(texts)