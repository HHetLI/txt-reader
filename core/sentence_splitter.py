import re

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")
# 长句二次切分时的轻断点（保留给前段，语义优先）
_LIGHT_BREAKS = "，、；：,.，;:"


def split_sentences(text: str, max_len: int | None = None) -> list[str]:
    """按标点切句；max_len 对长句二次切分。返回句子文本列表。"""
    return [s for s, _ in split_sentences_with_offsets(text, max_len)]


def split_sentences_with_offsets(
        text: str, max_len: int | None = None) -> list[tuple[str, int]]:
    """切句并返回每句的起始字符偏移（相对 text）。

    与 split_sentences 的切分结果完全一致，额外提供句子在原文中的位置，
    供 UI 在渲染文档中按偏移定位高亮（渲染文档与原文字符 1:1 映射）。
    """
    parts = _SENTENCE_RE.split(text)
    result: list[tuple[str, int]] = []
    pos = 0
    for p in parts:
        stripped = p.strip()
        if not stripped:
            pos += len(p)
            continue
        idx = text.find(p, pos)
        if idx < 0:  # 防御：理论不出现
            idx = pos
        start = idx + (len(p) - len(p.lstrip()))
        if max_len is None:
            result.append((stripped, start))
        else:
            result.extend(_chunk_sentence_with_offsets(stripped, start, max_len))
        pos = idx + len(p)
    return result


def _chunk_sentence_with_offsets(
        sentence: str, start: int, max_len: int) -> list[tuple[str, int]]:
    """单句二次切分，并计算每个 chunk 的偏移（chunks 在原文中连续）。"""
    max_len = max(max_len, 1)
    chunks: list[tuple[str, int]] = []
    offset = start
    for chunk in _chunk_sentence(sentence, max_len):
        chunks.append((chunk, offset))
        offset += len(chunk)
    return chunks


def _chunk_sentence(sentence: str, max_len: int) -> list[str]:
    """把单句按 max_len 二次切分，优先在标点处断开（标点保留给前段）。"""
    max_len = max(max_len, 1)  # 防呆：<=0 退化为 1，避免死循环
    if len(sentence) <= max_len:
        return [sentence]
    chunks: list[str] = []
    rest = sentence
    while len(rest) > max_len:
        # 在 max_len 窗口内找最后一个轻标点，断在其后
        cut = max_len
        for i in range(max_len - 1, -1, -1):
            if rest[i] in _LIGHT_BREAKS:
                cut = i + 1
                break
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        chunks.append(rest)
    return chunks
