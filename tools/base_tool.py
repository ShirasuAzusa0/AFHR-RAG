from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """
    工具基类
    所有 Agent 可调用的工具都需要继承此类并实现 run 方法
    """
    def __init__(self, name: str, description: str):
        """
            初始化工具

            Args:
                name: 工具名称，用于标识和调用
                description: 工具描述，供 Agent 理解工具功能
        """
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
            执行工具逻辑

            Args:
                **kwargs: 工具执行所需的参数

            Returns:
                标准格式的返回结果，必须包含 tool_name 等关键字段

            Raises:
                NotImplementedError: 子类必须实现此方法
        """
        pass