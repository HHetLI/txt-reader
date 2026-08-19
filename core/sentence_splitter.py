import re

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")
# 长句二次切分时的轻断点（保留给前段，语义优先）
_LIGHT_BREAKS = "，、；：,.，;:"


def split_sentences(text: str, max_len: int | None = None) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    sentences = [p.strip() for p in parts if p and p.strip()]
    if max_len is None:
        return sentences
    result: list[str] = []
    for s in sentences:
        result.extend(_chunk_sentence(s, max_len))
    return result


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
