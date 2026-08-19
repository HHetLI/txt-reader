import re

_CHAPTER_RE = re.compile(
    r"^\s*(?:"
    r"(?:第\s*[0-9零〇一二三四五六七八九十百千万两]+\s*[章回节卷集部篇](?:\s*.*)?)"
    r"|(?:chapter\s*\d+(?:\s*.*)?)"
    r"|(?:序章|楔子|引子|序幕|尾声|后记|番外|正文)(?:\s+.*|[：:.、\-—].*)?"
    r")\s*$",
    re.IGNORECASE,
)


def split_chapters(text: str) -> list[dict]:
    lines = text.splitlines()
    chapters: list[dict] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and _CHAPTER_RE.match(line):
            if current_title is not None:
                chapters.append({"title": current_title, "content": "\n".join(current_lines)})
            current_title = stripped
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        chapters.append({"title": current_title, "content": "\n".join(current_lines)})

    if not chapters:
        return [{"title": "全文", "content": text.strip()}]
    return chapters
