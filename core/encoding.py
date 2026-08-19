from pathlib import Path

from charset_normalizer import from_bytes


def detect_encoding(data: bytes) -> str:
    result = from_bytes(data).best()
    if result is None:
        return "utf-8"
    return result.encoding


def read_text_file(path: str | Path) -> str:
    data = Path(path).read_bytes()
    encoding = detect_encoding(data)
    text = data.decode(encoding, errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text
