from pathlib import Path

def load_prompt(prompt_name: str):
    """
        加载指定名称的提示词模板文件

        功能：从项目根目录的 prompts 文件夹中读取提示词模板

        Args:
            prompt_name: 提示词文件名（如 "system_prompt.txt"）

        Returns:
            str: 提示词模板内容（去除首尾空白）

        Raise:
            FileNotFoundError: 当提示词文件不存在时抛出
    """
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    prompt_path = project_root / 'prompts' / prompt_name
    if not project_root.exists():
        raise FileNotFoundError(f"Prompt 文件不存在：{prompt_path}")
    return prompt_path.read_text(encoding='utf-8').strip()