import os
import requests
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from tools.rag_retrieval_tool import RAGRetrievalTool
from models.agent_decisionrecord import DecisionRecord

class AgentState:
    """Agent 状态管理类，维护检索过程中的动态状态"""
    def __init__(self, query: str, kb_id: int, initial_top_k: int):
        self.query = query
        self.kb_id = kb_id
        self.iteration = 0
        self.top_k = initial_top_k
        self.aggregated_documents: List[Dict] = []
        self.final_metrics: Dict[str, Any] = {}
        self.metrics_history: List[Dict[str, Any]] = []
        self.decision_history: List[DecisionRecord] = []
        self.strategy: Dict[str, Any] = {}
        self.used_tokens: int = 0
        self.budget: int = 0

class AgentService:
    """
        Agent 服务类，实现基于策略的智能检索决策

        功能：
            1. 根据查询复杂度动态调整检索策略
            2. 迭代检索并决策是否继续扩展搜索
            3. 管理 token 预算，避免超限
            4. 记录完整决策历史用于分析
    """
    def __init__(
            self,
            retrieval_tool: RAGRetrievalTool,
            api_key: str = os.getenv("LLM_API_KEY", ""),
            llm_url=os.getenv("LLM_OPENAI_BASE_URL", ""),
            max_iterations: int = 3,
            min_selected_docs: int = 3,
            min_total_tokens: int = 800,
            max_decision_retries: int = 1
    ):
        """
            初始化 Agent 服务

            Args:
                retrieval_tool: RAG 检索工具实例
                api_key: LLM API 密钥
                llm_url: LLM API 地址
                max_iterations: 最大迭代次数（会被策略覆盖）
                min_selected_docs: 最少筛选文档数（会被策略覆盖）
                min_total_tokens: 最少 token 数（会被策略覆盖）
                max_decision_retries: 决策重试最大次数
        """
        self.retrieval_tool = retrieval_tool
        self.api_key = api_key
        self.llm_url = llm_url
        self.max_iterations = max_iterations
        self .min_selected_docs = min_selected_docs
        self.min_total_tokens = min_total_tokens
        self.max_decision_retries = max_decision_retries
        try:
            self.min_select_gain = int(os.getenv("MIN_SELECTED_GAIN", 1))
        except ValueError:
            self.min_select_gain = 1

        try:
            self.min_token_gain = int(os.getenv("MIN_TOKEN_GAIN", 100))
        except ValueError:
            self.min_token_gain = 100

    def run(self, query: str, kb_id: int) -> Dict[str, Any]:
        """
            运行 Agent 主流程

            流程：评估查询复杂度 → 生成策略 → 迭代检索 → 决策 → 去重返回

            Args:
                query: 用户查询文本
                kb_id: 知识库 ID

            Returns:
                包含 documents、metrics、iterations、decision_history 的字典
        """
        complexity = self._estimate_query_complexity(query)
        strategy = self._generate_strategy(complexity)

        state = AgentState(query=query, kb_id=kb_id, initial_top_k=10)
        state.strategy = strategy
        state.budget = strategy["budget"]

        max_iterations = strategy["max_iterations"]

        while state.iteration < max_iterations:
            # 执行工具
            result = self._execute_retrieval(state)

            # 更新状态
            self._update_state(state, result)

            if state.used_tokens >= state.budget:
                break

            # 决策
            decision = self._decide_next_action(state)
            state.iteration += 1

            if decision == "finish":
                break

            if decision == "expand_search":
                state.top_k *= 2
                continue

        # 去重
        unique_docs = self._deduplicate(state.aggregated_documents)

        return {
            "documents": unique_docs,
            "metrics": state.final_metrics,
            "iterations": state.iteration,
            "decision_history": state.decision_history
        }

    @staticmethod
    def _load_prompt_template() -> str:
        """
            加载决策提示词模板

            Returns:
                提示词模板内容
        """
        prompt_path = Path("prompts/agent_decision_prompt.txt")
        return prompt_path.read_text(encoding="utf-8")

    def _call_llm(self, prompt: str) -> str:
        """
            调用 LLM (本项目中采用 MiniMax M2-her) 模型进行决策生成

            Args:
                prompt: 输入提示词

            Returns:
                模型生成的响应文本

            Raises:
                requests.RequestException: API 调用失败时抛出
        """
        url = f"{self.llm_url}/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "M2-her",
            "max_tokens": 512,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()

        # 安全读取响应内容
        if "content" in data and isinstance(data["content"], list):
            texts = [
                block.get("text", "")
                for block in data["content"]
                if block.get("type") == "text"
            ]
            return "".join(texts)

        # 若结构不符合预期，则返回空字符串
        return ""

    def _execute_retrieval(self, state: AgentState) -> Dict[str, Any]:
        """
            执行单次检索

            Args:
                state: 当前 Agent 状态

            Returns:
                检索结果，包含 documents 和 metrics
        """
        return self.retrieval_tool.run(
            query=state.query,
            kb_id=state.kb_id,
            top_k=state.top_k
        )

    @staticmethod
    def _update_state(state: AgentState, result: Dict[str, Any]) -> None:
        """
            更新 Agent 状态

            Args:
                state: 当前 Agent 状态
                result: 检索结果
        """
        documents = result.get("documents", [])
        metrics = result.get("metrics", {})

        state.aggregated_documents.extend(documents)
        state.final_metrics = metrics
        state.metrics_history.append(metrics.copy())

        if len(state.metrics_history) >= 1:
            prev_total = state.metrics_history[-1].get("total_tokens", 0)
            curr_total = metrics.get("total_tokens", 0)
            delta = max(curr_total - prev_total, 0)
        else:
            delta = metrics.get("total_tokens", 0)

        state.used_tokens += delta

    def _has_marginal_gain(self, state: AgentState) -> bool:
        """"
            判断当前迭代是否仍有明显收益

            比较最近两轮的 selected_count 和 total_tokens 增量

            Args:
                state: 当前 Agent 状态

            Returns:
                True 表示有边际收益，False 表示无收益
        """
        if len(state.metrics_history) < 2:
            return True  # 第一轮无法比较，默认有收益

        prev = state.metrics_history[-2]
        curr = state.metrics_history[-1]

        delta_selected = curr.get("selected_count", 0) - prev.get("selected_count", 0)
        delta_tokens = curr.get("total_tokens", 0) - prev.get("total_tokens", 0)

        # 可调参数
        if delta_selected >= self.min_select_gain:
            return True

        if delta_tokens >= self.min_token_gain:
            return True

        return False

    @staticmethod
    def _estimate_query_complexity(query: str) -> Dict[str, Any]:
        """
            评估查询复杂度

            基于查询长度、实体数量、比较词、推理词计算复杂度分数

            Args:
                query: 用户查询文本

            Returns:
                包含 level 和 score 的字典
                    - level: simple / medium / complex
                    - score: 复杂度分数
        """
        length = len(query)

        multi_entity = (
                query.count("和") +
                query.count("与") +
                query.lower().count("vs")
        )

        has_compare = any(
            k in query.lower()
            for k in ["对比", "区别", "compare", "difference"]
        )

        has_reason = any(
            k in query.lower()
            for k in ["为什么", "原理", "how", "why"]
        )

        score = 0

        if length > 40:
            score += 1
        if multi_entity >= 1:
            score += 1
        if has_compare:
            score += 1
        if has_reason:
            score += 1

        if score <= 1:
            level = "simple"
        elif score == 2:
            level = "medium"
        else:
            level = "complex"

        return {
            "level": level,
            "score": score
        }

    @staticmethod
    def _generate_strategy(complexity: Dict[str, Any]) -> Dict[str, Any]:
        """
            根据查询复杂度生成检索策略

            Args:
                complexity: 复杂度评估结果

            Returns:
                策略配置，包含 max_iterations、min_selected_docs、min_total_tokens、budget
        """
        level = complexity["level"]

        if level == "simple":
            return {
                "max_iterations": 2,
                "min_selected_docs": 2,
                "min_total_tokens": 500,
                "budget": 1500
            }

        elif level == "medium":
            return {
                "max_iterations": 3,
                "min_selected_docs": 3,
                "min_total_tokens": 800,
                "budget": 2500
            }

        else:  # complex
            return {
                "max_iterations": 5,
                "min_selected_docs": 5,
                "min_total_tokens": 1200,
                "budget": 4000
            }

    def _decide_next_action(self, state: AgentState) -> str:
        """
            决策下一步动作

            流程：
                1. 检查边际收益，无收益则直接结束
                2. 调用 LLM 决策（带重试机制）
                3. 验证响应 schema
                4. 降级处理
                5. 自我反思防护（确保满足最低要求）
                6. 记录决策历史

            Args:
                state: 当前 Agent 状态

            Returns:
                决策结果："finish" 或 "expand_search"
        """
        # 如果没有边际收益，直接停止
        if not self._has_marginal_gain(state):
            decision_record = DecisionRecord(
                timestamp=datetime.now().isoformat(),
                iteration=state.iteration,
                top_k=state.top_k,
                doc_count=len(state.aggregated_documents),
                selected_count=state.final_metrics.get("selected_count", 0),
                total_tokens=state.final_metrics.get("total_tokens", 0),
                action="finish",
                raw_response="",
                reflection="stopped_due_to_no_marginal_gain",
                error=None
            )

            state.decision_history.append(decision_record)
            return "finish"

        # 加载提示词模板
        prompt_template = self._load_prompt_template()

        selected_count = state.final_metrics.get("selected_count", 0)
        total_tokens = state.final_metrics.get("total_tokens", 0)
        doc_count = len(state.aggregated_documents)

        prompt = prompt_template.format(
            iteration=state.iteration,
            top_k=state.top_k,
            doc_count=doc_count,
            selected_count=selected_count,
            total_tokens=total_tokens,
            min_selected_docs=state.strategy.get(
                "min_selected_docs",
                self.min_selected_docs
            ),
            min_total_tokens=state.strategy.get(
                "min_total_tokens",
                self.min_total_tokens
            )
        )

        # 重试逻辑
        retries = 0
        llm_action: Optional[str] = None
        raw_response: str = ""
        error_message: Optional[str] = None
        used_fallback = False

        while retries <= self.max_decision_retries:

            try:
                raw_response = self._call_llm(prompt)

                decision_json = json.loads(raw_response)

                # Schema 严格校验
                if (
                        isinstance(decision_json, dict)
                        and list(decision_json.keys()) == ["action"]
                        and decision_json["action"] in ["expand_search", "finish"]
                ):
                    llm_action = decision_json["action"]
                    break
                else:
                    raise ValueError("Schema validation failed")

            except Exception as e:
                error_message = f"Retry {retries}: {str(e)}"
                retries += 1

                if retries > self.max_decision_retries:
                    used_fallback = True
                    break

        # fallback 降级逻辑：LLM 决策失败时使用规则判断
        if llm_action is None:
            if not self._is_sufficient(state):
                final_action = "expand_search"
            else:
                final_action = "finish"
        else:
            final_action = llm_action

        # Self-reflection guardrail，自我反思防护：如果决策为结束但指标不足，强制扩展
        reflection_note = None

        if final_action == "finish" and not self._is_sufficient(state):
            reflection_note = "override_finish_to_expand_due_to_insufficient_metrics"
            final_action = "expand_search"

        # Decision logging，记录决策历史
        decision_record = DecisionRecord(
            timestamp=datetime.now().isoformat(),
            iteration=state.iteration,
            top_k=state.top_k,
            doc_count=doc_count,
            selected_count=selected_count,
            total_tokens=total_tokens,
            action=final_action,
            raw_response=raw_response,
            reflection=reflection_note,
            error=error_message if used_fallback else None
        )

        state.decision_history.append(decision_record)

        return final_action

    def _is_sufficient(self, state: AgentState) -> bool:
        """
            规则判断（兜底处理），判断当前检索结果是否满足最低要求

            Args:
                state: 当前 Agent 状态

            Returns:
                True 表示满足要求，False 表示不满足
        """
        metrics = state.final_metrics

        selected_count = metrics.get("selected_count", 0)
        total_tokens = metrics.get("total_tokens", 0)

        min_selected_docs = state.strategy.get(
            "min_selected_docs",
            self.min_selected_docs
        )

        min_total_tokens = state.strategy.get(
            "min_total_tokens",
            self.min_total_tokens
        )

        if selected_count < min_selected_docs:
            return False

        if total_tokens < min_total_tokens:
            return False

        return True

    @staticmethod
    def _deduplicate(documents: List[Dict]) -> List[Dict]:
        """
            对文档列表进行去重

            基于文档 content 字段进行去重

            Args:
                documents: 原始文档列表

            Returns:
                去重后的文档列表
        """
        seen = set()
        unique = []

        for doc in documents:
            content = doc.get("content")
            if content not in seen:
                seen.add(content)
                unique.append(doc)

        return unique