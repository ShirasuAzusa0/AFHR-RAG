from pathlib import Path

def load_prompt(prompt_name: str):
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    prompt_path = project_root / 'prompt' / prompt_name
    if not project_root.exists():
        raise FileNotFoundError(f"Prompt 文件不存在：{prompt_path}")
    return prompt_path.read_text(encoding='utf-8').strip()