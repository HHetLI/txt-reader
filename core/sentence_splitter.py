import re

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]
