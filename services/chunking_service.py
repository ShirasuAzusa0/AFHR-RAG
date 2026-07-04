import re
import os
from dataclasses import dataclass
from typing import List, Optional
from docx import Document

@dataclass
class ChunkingRule:
    """分块规则数据结构"""
    regex: str                      # 正则表达式
    order: int                      # 匹配优先级顺序
    rule_type: str = "other"        # "markdown" 或 "other"

@dataclass
class Segment:
    """分割片段数据结构"""
    content: str                    # 片段内容
    titleFromRule: Optional[str]    # 从规则中提取的标题

@dataclass
class ParagraphInfo:
    """分段信息数据结构"""
    content: str                    # 分段内容
    title: Optional[str]            # 分段标题
    parentChain: List[str]          # 父级标题链（递进关系）

def get_chunking_rules() -> List[ChunkingRule]:
    """
        获取分块规则列表

        按优先级顺序定义 Markdown 标题、章、节、条等分割规则

        Returns:
            分块规则列表
    """
    regex_list = [
        r'(?<=^)# .*|(?<=\n)# .*',
        r'(?<=\n)(?<!#)## (?!#).*|(?<=^)(?<!#)## (?!#).*',
        r'(?<=\n)(?<!#)### (?!#).*|(?<=^)(?<!#)### (?!#).*',
        r'(?<=\n)(?<!#)#### (?!#).*|(?<=^)(?<!#)#### (?!#).*',
        r'(?<=\n)(?<!#)##### (?!#).*|(?<=^)(?<!#)##### (?!#).*',
        r'(?<=\n)(?<!#)###### (?!#).*|(?<=^)(?<!#)###### (?!#).*',
        r'[第][一二三四五六七八九十]+[章]',
        r'[第][一二三四五六七八九十]+[节]',
        r'[一二三四五六七八九十1-9]+[、.][1-9]*[.]*[1-9]*',
        r'[第][一二三四五六七八九十]+[条]',
        #r'(?<! )- .*',
        #r'(?<! ) (?! )',
        #r'(?<!；)；(?!；)',
        #r'(?<!，)，(?!，)',
        #r'(?<!。)。(?!。)',
        #r'(?<!！)！(?!！)',
        r'(?<!\n)\n\n(?!\n)',
        r'(?<!\n)\n(?!\n)'
    ]

    rules: List[ChunkingRule] = []
    for i, r in enumerate(regex_list):
        if i <= 5:
            rules.append(ChunkingRule(regex=r, order=i, rule_type="markdown"))
        else:
            rules.append(ChunkingRule(regex=r, order=i, rule_type="other"))
    return rules

def get_document_type(filename: Optional[str]) -> str:
    """
        根据文件名获取文档类型（文件扩展名）

        Args:
            filename: 文件名

        Returns:
            文件扩展名（小写），无法识别时返回 "unknown"
    """
    if not filename or '.' not in filename:
        return "unknown"
    return filename.rsplit('.', 1)[1].lower()

def build_rule_sequence(
        doc_type: str,
        content: str,
        rules_list: List[ChunkingRule]
) -> List[ChunkingRule]:
    """
        根据文档类型和内容构建适用的规则序列

        Args:
            doc_type: 文档类型（文件扩展名）
            content: 文档内容
            rules_list: 全量规则列表

        Returns:
            适用于当前文档的规则序列
    """
    sorted_rules = sorted(rules_list, key=lambda x: x.order)
    existing_headings = []

    for cr in sorted_rules:
        try:
            if re.search(cr.regex, content, flags=re.MULTILINE):
                existing_headings.append(cr)
        except re.error:
            pass

    lower_type = (doc_type or "").lower()
    if lower_type in ("markdown", "md", "pdf", "doc", "docx"):
        return existing_headings
    else:
        if len(rules_list) > 13:
            return [rules_list[13]]
        else:
            return [rules_list[-1]]

def split_by_rule(content: str, rule: ChunkingRule) -> List[Segment]:
    """
        根据指定规则分割内容

        Args:
            content: 待分割内容
            rule: 分割规则

        Returns:
            分割后的片段列表
    """
    result: List[Segment] = []

    if rule.rule_type == "markdown":
        try:
            pattern = re.compile(rule.regex, flags=re.MULTILINE)
            matches = list(pattern.finditer(content))
        except re.error:
            return [Segment(content, None)]

        if not matches:
            return [Segment(content, None)]

        last_heading_end = -1
        last_title = None

        for m in matches:
            start = m.start()
            end = m.end()

            if last_heading_end != -1:
                between = content[last_heading_end:start]
                if between.strip():
                    result.append(Segment(between, last_title))
            else:
                if start > 0:
                    leading = content[:start]
                    if leading.strip():
                        result.append(Segment(leading, None))

            heading_line = content[start:end]
            title = re.sub(r'^#+\s+', '', heading_line).strip()
            last_title = title if title else None
            last_heading_end = end

        if last_heading_end != -1 and last_heading_end < len(content):
            remaining = content[last_heading_end:]
            if remaining.strip():
                result.append(Segment(remaining, last_title))

        return result

    else:
        try:
            parts = re.split(rule.regex, content, flags=re.MULTILINE)
        except re.error:
            parts = [content]

        for p in parts:
            if p.strip():
                result.append(Segment(p, None))

        if not result:
            result.append(Segment(content, None))

        return result

def may_contain_rule(content: str, rule: ChunkingRule) -> bool:
    """
        判断内容是否可能包含指定规则

        Args:
            content: 待检查内容
            rule: 规则

        Returns:
            是否包含该规则
    """
    try:
        return re.search(rule.regex, content, flags=re.MULTILINE) is not None
    except re.error:
        return False

def recursive_split(
        content: str,
        rule_sequence: List[ChunkingRule],
        index: int,
        current_title: Optional[str],
        parent_chain: List[str]
) -> List[ParagraphInfo]:
    """
        递归分割文档内容，构建带标题层级的分块

        Args:
            content: 待分割内容
            rule_sequence: 规则序列
            index: 当前规则索引
            current_title: 当前标题
            parent_chain: 父级标题链

        Returns:
            分段信息列表
    """
    if index >= len(rule_sequence):
        full_path = parent_chain.copy()
        if current_title:
            full_path.append(current_title)
        return [ParagraphInfo(content, current_title, full_path)]

    current_rule = rule_sequence[index]
    segments = split_by_rule(content, current_rule)

    if not segments:
        full_path = parent_chain.copy()

        if current_title:
            full_path.append(current_title)

        return [
            ParagraphInfo(
                content,
                current_title,
                full_path
            )
        ]

    if len(segments) <= 1 and segments[0].titleFromRule is None:
        return recursive_split(content, rule_sequence, index + 1, current_title, parent_chain)

    result: List[ParagraphInfo] = []

    for seg in segments:
        if seg.titleFromRule is not None:
            new_title = seg.titleFromRule
            new_parent_chain = parent_chain.copy()
            if current_title:
                new_parent_chain.append(current_title)
        else:
            new_title = current_title
            new_parent_chain = parent_chain.copy()

        if index + 1 < len(rule_sequence) and may_contain_rule(seg.content, rule_sequence[index + 1]):
            result.extend(recursive_split(seg.content, rule_sequence, index + 1, new_title, new_parent_chain))
        else:
            full_path = new_parent_chain.copy()
            if new_title:
                full_path.append(new_title)
            result.append(ParagraphInfo(seg.content, new_title, full_path))

    return result

def split_long_paragraphs(paragraphs: List[ParagraphInfo]) -> List[ParagraphInfo]:
    """
        分割过长的分段（超过1000字符）

        Args:
            paragraphs: 分段信息列表

        Returns:
            处理后的分段列表
    """
    result: List[ParagraphInfo] = []
    for p in paragraphs:
        if len(p.content) > 1000:
            content = p.content
            length = len(content)
            start = 0
            while start < length:
                end = min(start + 800, length)
                sub_content = content[start:end]
                result.append(ParagraphInfo(sub_content, p.title, p.parentChain.copy()))
                start = end
        else:
            result.append(p)
    return result

def merge_short_paragraphs(paragraphs: List[ParagraphInfo]) -> List[ParagraphInfo]:
    """
        合并过短的分段（少于100字符且同标题）

        Args:
            paragraphs: 分段信息列表

        Returns:
            处理后的分段列表
    """
    if not paragraphs:
        return paragraphs

    result: List[ParagraphInfo] = []
    current = paragraphs[0]

    for next_p in paragraphs[1:]:
        if (len(current.content) < 100
                and current.title == next_p.title
                and len(current.content) + len(next_p.content) <= 1000):
            merged_content = current.content + next_p.content
            current = ParagraphInfo(merged_content, current.title, current.parentChain.copy())
        else:
            result.append(current)
            current = next_p

    result.append(current)
    return result

def post_process_paragraphs(paragraphs: List[ParagraphInfo]) -> List[ParagraphInfo]:
    """
        分段后处理：分割过长的分段，合并过短的分段

        Args:
            paragraphs: 分段信息列表

        Returns:
            处理后的分段列表
    """
    return merge_short_paragraphs(split_long_paragraphs(paragraphs))

def document_auto_split(file_path: str) -> List[ParagraphInfo]:
    """
        自动分割文档为分段（分段操作总入口）

        根据文档类型和内容自动选择分割规则，生成带标题层级的分段信息

        Args:
            file_path: 文档文件路径

        Returns:
            分段信息列表
    """
    content = None
    doc_type = get_document_type(os.path.basename(file_path))

    if doc_type == "docx":
        try:
            doc = Document(file_path)

            content = "\n".join(
                p.text.strip()
                for p in doc.paragraphs
                if p.text.strip()
            )

        except Exception as e:
            raise ValueError(f"无法解析 DOCX 文件：{file_path}\n{e}")

    else:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

    if content is None:
        raise UnicodeDecodeError("unknown", b"", 0, 1, f"无法解析文件编码：{file_path}")

    doc_type = get_document_type(os.path.basename(file_path))
    rule_list = get_chunking_rules()
    rule_sequence = build_rule_sequence(doc_type, content, rule_list)
    paragraphs = recursive_split(content, rule_sequence, 0, None, [])

    return post_process_paragraphs(paragraphs)