import torch
import numpy as np
import logging

logger = logging.getLogger(__name__)

class RerankerService:
    def __init__(
        self,
        tokenizer,
        model,
        token_true_id,
        token_false_id,
        prefix_tokens,
        suffix_tokens,
        max_length
    ):
        """
        初始化函数
        """
        self.tokenizer = tokenizer
        self.model = model
        self.token_true_id = token_true_id
        self.token_false_id = token_false_id
        self.prefix_tokens = prefix_tokens
        self.suffix_tokens = suffix_tokens
        self.max_length = max_length
        self.device = next(model.parameters()).device

        logger.info(f"RerankerService initialized on {self.device}")

    @staticmethod
    def format_instruction(instruction, query, doc):
        """
            格式化指令、查询和文档为模型输入格式

            Args:
                instruction: 指令文本，为 None 时使用默认值
                query: 查询文本
                doc: 文档文本

            Returns:
                格式化后的字符串
        """
        if instruction is None:
            instruction = "Given a web search query, retrieve relevant passages that answer the query"

        return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"

    def process_inputs(self, pairs):
        """
            处理输入文本对，添加前缀后缀并进行padding

            Args:
                pairs: 输入文本列表

            Returns:
                处理后的token字典，包含 input_ids 和 attention_mask，已移至模型设备
        """
        inputs = self.tokenizer(
            pairs,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens)
        )

        for i, ele in enumerate(inputs["input_ids"]):
            inputs["input_ids"][i] = self.prefix_tokens + ele + self.suffix_tokens

        inputs = self.tokenizer.pad(
            inputs,
            padding=True,
            return_tensors="pt",
            max_length=self.max_length
        )

        for key in inputs:
            inputs[key] = inputs[key].to(self.model.device)

        return inputs

    @torch.no_grad()
    def rerank(self, query, documents, batch_size: int = 8):
        """
            对筛选的文档分段进行重排，返回相关性分数

            使用 instruction 格式构建查询-文档对，通过模型预测 yes/no 概率，
            并对原始分数进行 Z-score 校正，限制异常值范围。

            Args:
                query: 查询文本
                documents: 待排序的文档列表
                batch_size: 每批处理的文档数量，默认8，用于控制显存使用

            Returns:
                校正后的相关性分数列表，顺序与输入 documents 一致
        """
        if not documents:
            return []

        instruction = "Given a web search query, retrieve relevant passages that answer the query"

        pairs = [
            self.format_instruction(instruction, query, doc)
            for doc in documents
        ]

        all_scores = []

        # 分批推理，避免 GPU OOM
        for i in range(0, len(pairs), batch_size):
            batch_pairs = pairs[i:i + batch_size]

            inputs = self.process_inputs(batch_pairs)

            outputs = self.model(**inputs)
            batch_scores = outputs.logits[:, -1, :]

            yes_logits = batch_scores[:, self.token_true_id]
            no_logits = batch_scores[:, self.token_false_id]

            scores = (yes_logits - no_logits).cpu().tolist()
            all_scores.extend(scores)

        # Z-score 校正
        scores_array = np.array(all_scores)
        mean_score = np.mean(scores_array)
        std_score = np.std(scores_array)

        if std_score == 0:
            std_score = 1

        z_scores = (scores_array - mean_score) / std_score

        corrected_scores = []

        for score, z in zip(all_scores, z_scores):
            if z > 1.5:
                corrected_scores.append(mean_score + 1.5 * std_score)
            elif z < -1.5:
                corrected_scores.append(mean_score - 1.5 * std_score)
            else:
                corrected_scores.append(score)

        return corrected_scores

    @staticmethod
    def select_top_documents(
            reranked_results,
            max_tokens=3000,
            threshold_percentile=60
    ):
        """
            根据分数阈值和 token 限制筛选高质量文档

            使用百分位数确定分数阈值，过滤低分文档，再按 token 预算选择文档。

            Args:
                reranked_results: 重排序结果列表，每项格式为 (doc, metadata, distance, score)
                max_tokens: 最大 token 预算，默认3000
                threshold_percentile: 分数阈值百分位数，默认60

            Returns:
                (selected_documents, metrics): 筛选后的文档列表和统计信息
                    - selected_documents: 格式同输入的文档列表
                    - metrics: 包含 threshold、selected_count、total_tokens
        """
        scores = [r[3] for r in reranked_results]
        scores_array = np.array(scores)

        threshold = np.percentile(scores_array, threshold_percentile)
        mean_score = np.mean(scores_array)

        if threshold < mean_score * 0.6:
            threshold = mean_score * 0.7

        candidates = [r for r in reranked_results if r[3] >= threshold]

        if len(candidates) < 3:
            candidates = reranked_results[:6]

        def estimate_tokens(text):
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            english_words = len(text.split())
            return int(chinese_chars * 1.5 + english_words * 1.3)

        selected = []
        total_tokens = 0

        for doc, meta, distance, score in candidates:
            doc_tokens = estimate_tokens(doc)

            if total_tokens + doc_tokens <= max_tokens:
                selected.append((doc, meta, distance, score))
                total_tokens += doc_tokens

        if not selected and reranked_results:
            selected = [reranked_results[0]]

        metrics = {
            "threshold": float(threshold),
            "selected_count": len(selected),
            "total_tokens": total_tokens
        }

        return selected, metrics