# 小说阅读听书应用 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use supo-subagent-driven-development (recommended) or supo-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Windows 桌面应用：打开 txt 小说并按章节阅读，点击听书从当前章节开始使用 edge-tts 朗读。

**Architecture:** PySide6 GUI + 纯逻辑 core 模块（编码检测/章节切分/句子切分/进度存储）+ 独立 TTS 引擎（后台线程按句合成 mp3 → QMediaPlayer 顺序播放，预取队列保证低延迟）。UI 与 core 单向依赖，core 全部可离线单元测试。

**Tech Stack:** Python 3.10+、PySide6 (Qt6)、edge-tts（需联网）、charset-normalizer、pytest + pytest-qt

## Global Constraints

- Python >= 3.10；使用 `uv` 管理环境（`uv venv` / `uv pip install -e ".[dev]"`）
- 依赖版本：PySide6>=6.6、edge-tts>=6.1、charset-normalizer>=3.0、pytest>=8.0、pytest-qt>=4.4
- 所有源码位于 worktree：`E:/WorkSpace/t2voice/.worktrees/novel-reader`（分支 feature/novel-reader）
- 界面文案使用简体中文
- 源码文件一律 UTF-8 编码，无 BOM
- 工作目录中任何命令都在 `E:/WorkSpace/t2voice/.worktrees/novel-reader` 下执行
- 测试命令统一为：`QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v`（Windows 下若 bash 不可用，用 PowerShell：`$env:QT_QPA_PLATFORM="offscreen"; uv run pytest tests/ -v`）

---

### Task 1: 项目脚手架（pyproject + 依赖 + 目录）

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `.python-version`
- Create: `README.md`（占位，Task 11 完善）

**Interfaces:**
- Consumes: 无
- Produces: 可运行的 `uv` 项目与 pytest 环境；`tests/conftest.py` 提供 `qapp` fixture（session 级 QApplication，供 UI 冒烟测试复用）

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "t2voice"
version = "0.1.0"
description = "Windows desktop novel reader with edge-tts listening"
requires-python = ">=3.10"
dependencies = [
    "PySide6>=6.6",
    "edge-tts>=6.1",
    "charset-normalizer>=3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 写 .python-version**

```
3.11
```

- [ ] **Step 3: 写 tests/conftest.py**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app
```

- [ ] **Step 4: 创建占位 README.md（Task 11 完善）**

```markdown
# 小说阅读听书（t2voice）

Windows 桌面小说阅读听书应用。（说明文档待完善）
```

- [ ] **Step 5: 建目录并安装依赖**

```bash
mkdir -p core ui tests
uv venv
uv pip install -e ".[dev]"
```

预期输出：安装成功，无报错。

- [ ] **Step 6: 写冒烟测试 tests/test_smoke.py**

```python
def test_import_core_packages():
    import core  # noqa: F401
    import ui  # noqa: F401
```

- [ ] **Step 7: 运行测试验证**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v
```

预期：`1 passed`。

- [ ] **Step 8: 提交**

```bash
git add pyproject.toml .python-version tests/ README.md
git commit -m "chore: scaffold project with uv and pytest"
```

---

### Task 2: core/encoding.py — 编码检测与读取

**Files:**
- Create: `core/encoding.py`
- Create: `core/__init__.py`
- Test: `tests/test_encoding.py`

**Interfaces:**
- Consumes: charset-normalizer
- Produces:
  - `detect_encoding(data: bytes) -> str`：返回检测到的编码名，检测失败回退 `"utf-8"`
  - `read_text_file(path: str | Path) -> str`：读取 txt 全文，自动去 BOM

- [ ] **Step 1: 写失败测试 tests/test_encoding.py**

```python
import pytest
from core.encoding import detect_encoding, read_text_file


def test_detect_utf8():
    data = "你好，世界".encode("utf-8")
    assert detect_encoding(data) == "utf_8" or detect_encoding(data).lower() == "utf-8"


def test_detect_gbk():
    data = "你好，世界".encode("gbk")
    enc = detect_encoding(data).lower()
    assert "gb" in enc  # gb18030 / gbk / gb2312


def test_read_utf8_plain(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("第一章\n内容", encoding="utf-8")
    assert "第一章" in read_text_file(p)


def test_read_gbk_file(tmp_path):
    p = tmp_path / "b.txt"
    p.write_bytes("第一章\n内容".encode("gbk"))
    text = read_text_file(p)
    assert "第一章" in text


def test_read_strips_bom(tmp_path):
    p = tmp_path / "c.txt"
    p.write_bytes("\ufeff第一章".encode("utf-8"))
    text = read_text_file(p)
    assert not text.startswith("\ufeff")
    assert text.startswith("第一章")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_encoding.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'core.encoding'`。

- [ ] **Step 3: 写实现 core/encoding.py**

```python
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
```

同时创建空文件 `core/__init__.py`。

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_encoding.py -v
```

预期：`5 passed`。

- [ ] **Step 5: 提交**

```bash
git add core/encoding.py core/__init__.py tests/test_encoding.py
git commit -m "feat: encoding detection and txt reading"
```

---

### Task 3: core/chapter_splitter.py — 章节切分

**Files:**
- Create: `core/chapter_splitter.py`
- Test: `tests/test_chapter_splitter.py`

**Interfaces:**
- Consumes: 无（纯函数）
- Produces:
  - `split_chapters(text: str) -> list[dict]`：返回 `[{"title": str, "content": str}, ...]`；无章节标题时返回单章 `[{"title": "全文", "content": text}]`

**章节识别规则（正则，行首匹配）：**
- `第[0-9零〇一二三四五六七八九十百千万两]+[章回节卷集部篇]` + 任意副标题，如 `第一章 风起`、`第1章：相遇`、`第二百五十章 重逢`、`第12回`
- 英文 `Chapter`/`CHAPTER` + 数字
- 独立标题词 `序章|楔子|引子|序幕|尾声|后记|番外|正文`：要求独占一行或后跟空格/标点分隔的副标题（如 `楔子`、`番外 小花絮`），避免误匹配“正文内容。”这类以关键词开头的正文行

- [ ] **Step 1: 写失败测试 tests/test_chapter_splitter.py**

```python
from core.chapter_splitter import split_chapters


def test_split_basic_chapters():
    text = "第一章 风起\n这是第一章内容。\n第二章 云涌\n这是第二章内容。"
    chapters = split_chapters(text)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "第一章 风起"
    assert "第一章内容" in chapters[0]["content"]
    assert chapters[1]["title"] == "第二章 云涌"


def test_split_arabic_and_chinese_numerals():
    text = "第1章 相遇\n内容一\n第12章 离别\n内容二\n第二百五十章 重逢\n内容三"
    chapters = split_chapters(text)
    assert [c["title"] for c in chapters] == ["第1章 相遇", "第12章 离别", "第二百五十章 重逢"]


def test_split_english_chapter():
    text = "Chapter 1\nHello world.\nChapter 2\nBye world."
    chapters = split_chapters(text)
    assert [c["title"] for c in chapters] == ["Chapter 1", "Chapter 2"]


def test_split_special_titles():
    text = "楔子\n这是一个楔子。\n第一章 开始\n正文内容。\n番外 小花絮\n额外内容。"
    chapters = split_chapters(text)
    assert chapters[0]["title"] == "楔子"
    assert chapters[-1]["title"] == "番外 小花絮"


def test_no_chapter_headers_returns_single_chapter():
    text = "从前有座山，山里有座庙。\n庙里有个老和尚。"
    chapters = split_chapters(text)
    assert len(chapters) == 1
    assert chapters[0]["title"] == "全文"
    assert "老和尚" in chapters[0]["content"]


def test_title_with_colon_and_spaces():
    text = "第一章：相遇\n正文A\n第二章 重逢\n正文B"
    chapters = split_chapters(text)
    assert chapters[0]["title"] == "第一章：相遇"
    assert chapters[1]["title"] == "第二章 重逢"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_chapter_splitter.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'core.chapter_splitter'`。

- [ ] **Step 3: 写实现 core/chapter_splitter.py**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_chapter_splitter.py -v
```

预期：`6 passed`。

- [ ] **Step 5: 提交**

```bash
git add core/chapter_splitter.py tests/test_chapter_splitter.py
git commit -m "feat: auto chapter splitting"
```

---

### Task 4: core/sentence_splitter.py — 句子切分（TTS 用）

**Files:**
- Create: `core/sentence_splitter.py`
- Test: `tests/test_sentence_splitter.py`

**Interfaces:**
- Consumes: 无（纯函数）
- Produces:
  - `split_sentences(text: str) -> list[str]`：按 `。！？!?；;` 切分句子，分隔符保留在句尾，去除空白段。长句不强制再切（edge-tts 可处理 500 字符内句子；本应用按行内自然停顿切分，不做超长拆分）

- [ ] **Step 1: 写失败测试 tests/test_sentence_splitter.py**

```python
from core.sentence_splitter import split_sentences


def test_split_chinese_sentences():
    sentences = split_sentences("你好。世界！这是测试？")
    assert sentences == ["你好。", "世界！", "这是测试？"]


def test_keep_delimiter_with_sentence():
    sentences = split_sentences("第一句！第二句？第三句。")
    assert sentences[0] == "第一句！"
    assert sentences[1] == "第二句？"
    assert sentences[2] == "第三句。"


def test_semicolon_splits():
    sentences = split_sentences("甲；乙；丙。")
    assert sentences == ["甲；", "乙；", "丙。"]


def test_empty_input():
    assert split_sentences("") == []


def test_whitespace_only_input():
    assert split_sentences("   \n  ") == []
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_sentence_splitter.py -v
```

预期：FAIL，`ModuleNotFoundError`。

- [ ] **Step 3: 写实现 core/sentence_splitter.py**

```python
import re

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_sentence_splitter.py -v
```

预期：`5 passed`。

- [ ] **Step 5: 提交**

```bash
git add core/sentence_splitter.py tests/test_sentence_splitter.py
git commit -m "feat: sentence splitting for TTS"
```

---

### Task 5: core/progress_store.py — 阅读进度记忆

**Files:**
- Create: `core/progress_store.py`
- Test: `tests/test_progress_store.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `load_progress() -> dict`：返回 `{book_path: {"chapter": int, "scroll": int}}`，文件不存在或损坏返回 `{}`
  - `save_progress(book_path: str, chapter: int, scroll: int) -> None`：覆盖写入该书的进度
  - 存储位置：`~/.t2voice/progress.json`

- [ ] **Step 1: 写失败测试 tests/test_progress_store.py**

```python
import json
import pytest
from core import progress_store


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setattr(progress_store, "_store_path", lambda: tmp_path / "progress.json")
    yield


def test_load_empty_when_missing():
    assert progress_store.load_progress() == {}


def test_save_and_load_roundtrip():
    progress_store.save_progress("/x/a.txt", 3, 120)
    data = progress_store.load_progress()
    assert data["/x/a.txt"] == {"chapter": 3, "scroll": 120}


def test_save_overwrites_same_book():
    progress_store.save_progress("/x/a.txt", 1, 10)
    progress_store.save_progress("/x/a.txt", 2, 20)
    data = progress_store.load_progress()
    assert data["/x/a.txt"] == {"chapter": 2, "scroll": 20}


def test_save_keeps_other_books():
    progress_store.save_progress("/x/a.txt", 1, 10)
    progress_store.save_progress("/x/b.txt", 5, 50)
    data = progress_store.load_progress()
    assert set(data) == {"/x/a.txt", "/x/b.txt"}


def test_corrupted_json_returns_empty(tmp_path):
    (tmp_path / "progress.json").write_text("{not json", encoding="utf-8")
    assert progress_store.load_progress() == {}
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_progress_store.py -v
```

预期：FAIL，`AttributeError: module 'core.progress_store' has no attribute '_store_path'`。

- [ ] **Step 3: 写实现 core/progress_store.py**

```python
import json
from pathlib import Path


def _store_path() -> Path:
    return Path.home() / ".t2voice" / "progress.json"


def load_progress() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_progress(book_path: str, chapter: int, scroll: int) -> None:
    data = load_progress()
    data[book_path] = {"chapter": chapter, "scroll": scroll}
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_progress_store.py -v
```

预期：`5 passed`。

- [ ] **Step 5: 提交**

```bash
git add core/progress_store.py tests/test_progress_store.py
git commit -m "feat: reading progress persistence"
```

---

### Task 6: core/tts_engine.py — TTS 合成与播放引擎

**Files:**
- Create: `core/tts_engine.py`
- Test: `tests/test_tts_engine.py`

**Interfaces:**
- Consumes: `split_sentences`（Task 4）、edge-tts、PySide6.QtMultimedia
- Produces（供 UI 层使用）：
  - `TtsEngine(QObject)`，构造 `TtsEngine(parent=None)`
  - 信号：`playing(bool)`（播放/暂停状态）、`sentence_started(int)`（当前句在章节内索引）、`chapter_finished()`、`error(str)`
  - 方法：
    - `play_chapters(chapters: list[dict], start_index: int = 0, voice: str | None = None, rate: str | None = None) -> None`：从指定章节开始播
    - `toggle_play() -> None`：播放/暂停切换
    - `stop() -> None`：停止并清理临时文件
    - `next_chapter() / prev_chapter() -> None`：切章（从新章开头播）
    - `set_voice(voice: str) / set_rate(rate: str) -> None`：播放中改声线/语速，从当前句重新开始
    - `is_playing() -> bool`
    - `current_chapter_index() -> int`
  - 模块函数 `synthesize_sentence(sentence: str, voice: str, rate: str, out_path: Path) -> None`（async，单句合成；测试可 monkeypatch）

**设计要点：**
- `_SynthesisWorker(QThread)`：后台线程按序合成句子，每句就绪发 `sentence_ready(int, str)`；支持 `cancel()`；结束发 `all_done(int)`（总句数）
- 预取：主线程 `_ready: dict[int, str]` 记录已就绪句；QMediaPlayer 播完当前句（EndOfMedia）→ 若下一句已就绪则播放，否则等待 worker 信号
- 章节播完自动续播下一章；最后一章播完停止并 emit `chapter_finished()`
- 切声线/语速：从当前句（`next_index - 1`）开始重新合成播放，实现"重新开始当前句"
- 临时文件目录用 `tempfile.mkdtemp(prefix="t2voice_")`，`stop()` 和章节切换时清理

- [ ] **Step 1: 写失败测试 tests/test_tts_engine.py**

```python
import tempfile
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from core.tts_engine import TtsEngine, _SynthesisWorker


@pytest.fixture
def fake_synth(monkeypatch):
    """用写假 mp3 的合成函数替换真实 edge-tts，保证离线可测。"""

    async def fake_synthesize(sentence, voice, rate, out_path):
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", fake_synthesize)


def test_worker_synthesizes_in_order(qtbot, fake_synth):
    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    ready: list[tuple[int, Path]] = []
    worker.sentence_ready.connect(lambda i, p: ready.append((i, Path(p))))
    worker.start()
    qtbot.waitSignal(worker.all_done, timeout=5000)
    assert [i for i, _ in ready] == [0, 1, 2]
    assert all(p.exists() for _, p in ready)


def test_worker_respects_cancel(qtbot, fake_synth):
    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    worker.start()
    worker.cancel()
    qtbot.waitSignal(worker.all_done, timeout=5000)


def test_engine_plays_next_sentence_after_media_end(qtbot, fake_synth):
    """模拟播放结束信号，验证引擎顺序播放下一句（不依赖真实音频设备）。"""
    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)  # 第一句已开始
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)
    qtbot.waitUntil(lambda: len(started) >= 2, timeout=5000)  # 第二句开始
    assert started[:2] == [0, 1]
    engine.stop()


def test_engine_auto_advances_chapter(qtbot, fake_synth):
    """第一章最后一句播完后自动切到第二章。"""
    engine = TtsEngine()
    chapters = [
        {"title": "第一章", "content": "甲。"},
        {"title": "第二章", "content": "乙。"},
    ]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)  # 第一章播完
    qtbot.waitUntil(lambda: engine.current_chapter_index() == 1, timeout=5000)
    qtbot.waitUntil(lambda: len(started) >= 2, timeout=5000)  # 第二章第一句开始
    assert engine.current_chapter_index() == 1
    assert started[:2] == [0, 0]
    engine.stop()


def test_engine_stop_clears_session(qtbot, fake_synth):
    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: engine.has_session(), timeout=5000)
    engine.stop()
    assert not engine.has_session()
```

注意：测试通过手动调用 `engine._on_media_status(EndOfMedia)` 模拟播放结束，不依赖真实音频设备；播放无效 mp3 数据时 QMediaPlayer 可能报错，但不影响 `sentence_started` 信号的驱动逻辑。

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_tts_engine.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'core.tts_engine'`。

- [ ] **Step 3: 写实现 core/tts_engine.py**

```python
import asyncio
import tempfile
from pathlib import Path

import edge_tts
from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from core.sentence_splitter import split_sentences


async def synthesize_sentence(sentence: str, voice: str, rate: str, out_path: Path) -> None:
    """合成单句为 mp3 文件。独立函数便于测试替换。"""
    communicate = edge_tts.Communicate(sentence, voice, rate=rate)
    await communicate.save(str(out_path))


class _SynthesisWorker(QThread):
    sentence_ready = Signal(int, str)
    all_done = Signal(int)  # 参数：总句数（start_index + len）
    error_occurred = Signal(str)

    def __init__(self, sentences: list[str], voice: str, rate: str,
                 out_dir: Path, start_index: int = 0, parent=None):
        super().__init__(parent)
        self._sentences = sentences
        self._voice = voice
        self._rate = rate
        self._out_dir = out_dir
        self._start_index = start_index
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        async def synth_all() -> None:
            for i, sentence in enumerate(self._sentences):
                idx = self._start_index + i
                if self._cancel:
                    break
                if not sentence.strip():
                    continue
                path = self._out_dir / f"sentence_{idx:05d}.mp3"
                try:
                    await synthesize_sentence(sentence, self._voice, self._rate, path)
                except Exception as exc:  # noqa: BLE001
                    if self._cancel:
                        break
                    self.error_occurred.emit(str(exc))
                    return
                if self._cancel:
                    break
                self.sentence_ready.emit(idx, str(path))
            self.all_done.emit(self._start_index + len(self._sentences))

        asyncio.run(synth_all())


class TtsEngine(QObject):
    playing = Signal(bool)
    sentence_started = Signal(int)
    chapter_finished = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_media_status)

        self._worker: _SynthesisWorker | None = None
        self._ready: dict[int, str] = {}
        self._next_index = 0
        self._worker_done = False

        self._chapters: list[dict] = []
        self._chapter_index = 0
        self._out_dir: Path | None = None

        self._voice = "zh-CN-XiaoxiaoNeural"
        self._rate = "+0%"

    # ---------- 对外 API ----------

    def play_chapters(self, chapters: list[dict], start_index: int = 0,
                      voice: str | None = None, rate: str | None = None) -> None:
        self.stop()
        if not chapters:
            return
        self._chapters = chapters
        self._chapter_index = max(0, min(start_index, len(chapters) - 1))
        if voice:
            self._voice = voice
        if rate:
            self._rate = rate
        self._start_chapter(self._chapter_index)

    def toggle_play(self) -> None:
        if self._worker is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.playing.emit(False)
        else:
            self._player.play()
            self.playing.emit(True)

    def stop(self) -> None:
        self._player.stop()
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(1500)
            self._worker = None
        self._ready.clear()
        self._next_index = 0
        self._worker_done = False
        self._cleanup_temp()
        self.playing.emit(False)

    def next_chapter(self) -> None:
        if self._chapter_index + 1 < len(self._chapters):
            self._start_chapter(self._chapter_index + 1)

    def prev_chapter(self) -> None:
        if self._chapter_index - 1 >= 0:
            self._start_chapter(self._chapter_index - 1)

    def set_voice(self, voice: str) -> None:
        self._voice = voice
        self._restart_current_sentence()

    def set_rate(self, rate: str) -> None:
        self._rate = rate
        self._restart_current_sentence()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def has_session(self) -> bool:
        """是否存在未停止的播放会话（播放中或暂停中）。"""
        return self._worker is not None

    def current_chapter_index(self) -> int:
        return self._chapter_index

    # ---------- 内部 ----------

    def _start_chapter(self, index: int, start_sentence: int = 0) -> None:
        self.stop()
        self._chapter_index = index
        chapter = self._chapters[index]
        sentences = split_sentences(chapter["content"])
        if start_sentence >= len(sentences):
            start_sentence = max(0, len(sentences) - 1)
        remainder = sentences[start_sentence:]
        self._out_dir = Path(tempfile.mkdtemp(prefix="t2voice_"))
        self._ready = {}
        self._next_index = start_sentence
        self._worker_done = False
        self._worker = _SynthesisWorker(
            remainder, self._voice, self._rate, self._out_dir,
            start_index=start_sentence, parent=self,
        )
        self._worker.sentence_ready.connect(self._on_sentence_ready)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error_occurred.connect(self.error)
        self._worker.start()
        self.playing.emit(True)

    def _restart_current_sentence(self) -> None:
        if self._worker is None:
            return
        start = max(0, self._next_index - 1)
        self._start_chapter(self._chapter_index, start_sentence=start)

    def _on_sentence_ready(self, index: int, path: str) -> None:
        self._ready[index] = path
        if index == self._next_index:
            self._play_next()

    def _on_all_done(self, total: int) -> None:
        self._worker_done = True
        # 仅当所有句子均已合成、无可播的下一句、且播放器已停（最后一句播完）时才切章
        if (self._next_index >= total
                and self._next_index not in self._ready
                and self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState):
            self._finish_chapter()

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._next_index in self._ready:
                self._play_next()
            elif not self._worker_done:
                pass  # 等待 worker 合成下一句
            else:
                self._finish_chapter()

    def _play_next(self) -> None:
        if self._next_index not in self._ready:
            return
        path = self._ready.pop(self._next_index)
        self._next_index += 1
        self.sentence_started.emit(self._next_index - 1)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def _finish_chapter(self) -> None:
        if self._chapter_index + 1 < len(self._chapters):
            self._start_chapter(self._chapter_index + 1)
        else:
            self.playing.emit(False)
        self.chapter_finished.emit()

    def _cleanup_temp(self) -> None:
        if self._out_dir is not None and self._out_dir.exists():
            for f in self._out_dir.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                self._out_dir.rmdir()
            except OSError:
                pass
        self._out_dir = None
```

注意：`error_occurred` 信号在类中定义，并在 `_start_chapter` 中连接到引擎的 `error` 信号，保证断网/合成失败时 UI 能收到提示。

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_tts_engine.py -v
```

预期：`5 passed`（全部通过：2 个 worker 测试 + 3 个引擎测试，均通过模拟 EndOfMedia 驱动，不依赖真实音频设备）。若某引擎测试因 Qt 多媒体后端缺失失败，用 `QT_QPA_PLATFORM=offscreen` 重试或跳过该测试（`-k "not engine"`），在 Task 11 手动验证播放。

- [ ] **Step 5: 提交**

```bash
git add core/tts_engine.py tests/test_tts_engine.py
git commit -m "feat: tts engine with sentence queue playback"
```

---

### Task 7: ui/reader_view.py — 正文阅读区

**Files:**
- Create: `ui/reader_view.py`
- Create: `ui/__init__.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: PySide6
- Produces:
  - `ReaderView(QTextBrowser)`：
    - `show_chapter(title: str, content: str) -> None`：显示章节标题+正文（自动换行，`\n` 转 `<br>`）
    - `set_font_size(pt: int) -> None`：字号（pt）
    - `set_line_spacing(ratio: float) -> None`：行距倍数
    - `scroll_value() -> int` / `restore_scroll(value: int) -> None`：滚动位置读写

- [ ] **Step 1: 写失败测试（追加到 tests/test_ui_smoke.py）**

```python
from ui.reader_view import ReaderView


def test_reader_view_shows_chapter(qapp):
    view = ReaderView()
    view.show_chapter("第一章", "第一行\n第二行")
    html = view.toHtml()
    assert "第一章" in html
    assert "第一行" in html
    assert "第二行" in html


def test_reader_view_font_size_changes(qapp):
    view = ReaderView()
    view.set_font_size(24)
    assert view._font_size == 24
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'ui.reader_view'`。

- [ ] **Step 3: 写实现 ui/reader_view.py**

```python
from PySide6.QtWidgets import QTextBrowser


class ReaderView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self._font_size = 16
        self._line_spacing = 1.6
        self._apply_style()
        self.setPlaceholderText("打开一个 txt 小说文件开始阅读")

    def _apply_style(self) -> None:
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)
        self.document().setDefaultStyleSheet(
            f"body {{ font-size: {self._font_size}pt; line-height: {self._line_spacing:.1f}; }}"
        )

    def show_chapter(self, title: str, content: str) -> None:
        body = content.replace("\n", "<br>")
        self.setHtml(f"<h1>{title}</h1><br>{body}")
        self.verticalScrollBar().setValue(0)

    def set_font_size(self, pt: int) -> None:
        self._font_size = pt
        self._apply_style()

    def set_line_spacing(self, ratio: float) -> None:
        self._line_spacing = ratio
        self._apply_style()

    def scroll_value(self) -> int:
        return self.verticalScrollBar().value()

    def restore_scroll(self, value: int) -> None:
        self.verticalScrollBar().setValue(value)
```

同时创建空文件 `ui/__init__.py`。

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：`3 passed`（含 Task 1 的冒烟测试 1 个）。

- [ ] **Step 5: 提交**

```bash
git add ui/reader_view.py ui/__init__.py tests/test_ui_smoke.py
git commit -m "feat: reader view widget"
```

---

### Task 8: ui/chapter_panel.py — 章节列表

**Files:**
- Create: `ui/chapter_panel.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: PySide6
- Produces:
  - `ChapterPanel(QWidget)`：
    - 信号 `chapter_selected(int)`：用户点选章节时发出
    - `set_chapters(titles: list[str]) -> None`
    - `select_chapter(index: int) -> None`：程序化选中（不发信号）
    - `current_index() -> int`：当前选中行，无选中返回 -1
    - `toggle_visible() -> None`：折叠/展开列表

- [ ] **Step 1: 写失败测试（追加到 tests/test_ui_smoke.py）**

```python
from ui.chapter_panel import ChapterPanel


def test_chapter_panel_set_and_select(qapp):
    panel = ChapterPanel()
    panel.set_chapters(["第一章", "第二章", "第三章"])
    panel.select_chapter(1)
    assert panel.current_index() == 1


def test_chapter_panel_signal(qapp):
    from PySide6.QtCore import QSignalSpy
    panel = ChapterPanel()
    spy = QSignalSpy(panel.chapter_selected)
    panel.set_chapters(["a", "b"])
    panel._list.setCurrentRow(1)
    assert len(spy) == 1
    assert spy[0][0] == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'ui.chapter_panel'`。

- [ ] **Step 3: 写实现 ui/chapter_panel.py**

```python
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QPushButton,
                               QVBoxLayout, QWidget)


class ChapterPanel(QWidget):
    chapter_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self._toggle_btn = QPushButton("📕")
        self._toggle_btn.setToolTip("折叠/展开章节列表")
        self._toggle_btn.setFixedWidth(32)
        self._toggle_btn.clicked.connect(self.toggle_visible)
        top.addWidget(self._toggle_btn)
        top.addStretch()
        layout.addLayout(top)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._emit_selected)
        layout.addWidget(self._list)

    def _emit_selected(self, row: int) -> None:
        if row >= 0:
            self.chapter_selected.emit(row)

    def set_chapters(self, titles: list[str]) -> None:
        self._list.clear()
        self._list.addItems(titles)

    def select_chapter(self, index: int) -> None:
        self._list.setCurrentRow(index)

    def current_index(self) -> int:
        return self._list.currentRow()

    def toggle_visible(self) -> None:
        self._visible = not self._visible
        self._list.setVisible(self._visible)
        self._toggle_btn.setText("📖" if not self._visible else "📕")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：`5 passed`。

- [ ] **Step 5: 提交**

```bash
git add ui/chapter_panel.py tests/test_ui_smoke.py
git commit -m "feat: chapter panel widget"
```

---

### Task 9: ui/player_bar.py — 播放控制栏

**Files:**
- Create: `ui/player_bar.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: PySide6
- Produces:
  - `PlayerBar(QWidget)`：
    - 信号：`play_toggled()`、`prev_requested()`、`next_requested()`、`stop_requested()`、`voice_changed(str)`、`rate_changed(str)`
    - 控件：声线下拉（5 种中文声线）、语速下拉（-10% ~ +50% 步进 10%）、⏮ ▶/⏸ ⏭ ⏹ 按钮、状态标签
    - 方法：`set_status(text: str)`、`set_playing(bool)`、`voice() -> str`、`rate() -> str`

- [ ] **Step 1: 写失败测试（追加到 tests/test_ui_smoke.py）**

```python
from ui.player_bar import PlayerBar


def test_player_bar_defaults(qapp):
    bar = PlayerBar()
    assert bar.voice() == "zh-CN-XiaoxiaoNeural"
    assert bar.rate() == "+0%"


def test_player_bar_voice_change_signal(qapp):
    from PySide6.QtCore import QSignalSpy
    bar = PlayerBar()
    spy = QSignalSpy(bar.voice_changed)
    bar._voice.setCurrentIndex(1)
    assert len(spy) == 1
    assert spy[0][0] == "zh-CN-YunxiNeural"


def test_player_bar_status(qapp):
    bar = PlayerBar()
    bar.set_status("正在朗读：第一章")
    assert bar._status.text() == "正在朗读：第一章"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'ui.player_bar'`。

- [ ] **Step 3: 写实现 ui/player_bar.py**

```python
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QWidget)

VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓（女）"),
    ("zh-CN-YunxiNeural", "云希（男）"),
    ("zh-CN-YunjianNeural", "云健（男）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女）"),
    ("zh-CN-YunyangNeural", "云扬（男）"),
]
RATES = [f"{r:+d}%" for r in range(-10, 51, 10)]


class PlayerBar(QWidget):
    play_toggled = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    stop_requested = Signal()
    voice_changed = Signal(str)
    rate_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel("声线:"))
        self._voice = QComboBox()
        for code, label in VOICES:
            self._voice.addItem(label, code)
        self._voice.currentIndexChanged.connect(self._on_voice_changed)
        layout.addWidget(self._voice)

        layout.addWidget(QLabel("语速:"))
        self._rate = QComboBox()
        self._rate.addItems(RATES)
        self._rate.setCurrentText("+0%")
        self._rate.currentTextChanged.connect(self.rate_changed)
        layout.addWidget(self._rate)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setToolTip("上一章")
        self._prev_btn.clicked.connect(self.prev_requested)
        layout.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setToolTip("播放/暂停")
        self._play_btn.clicked.connect(self.play_toggled)
        layout.addWidget(self._play_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setToolTip("下一章")
        self._next_btn.clicked.connect(self.next_requested)
        layout.addWidget(self._next_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("停止")
        self._stop_btn.clicked.connect(self.stop_requested)
        layout.addWidget(self._stop_btn)

        self._status = QLabel("未打开书籍")
        layout.addWidget(self._status, 1)

    def _on_voice_changed(self) -> None:
        self.voice_changed.emit(self._voice.currentData())

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def voice(self) -> str:
        return self._voice.currentData()

    def rate(self) -> str:
        return self._rate.currentText()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：`8 passed`。

- [ ] **Step 5: 提交**

```bash
git add ui/player_bar.py tests/test_ui_smoke.py
git commit -m "feat: player control bar widget"
```

---

### Task 10: ui/main_window.py + main.py — 主窗口组装与入口

**Files:**
- Create: `ui/main_window.py`
- Create: `main.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `read_text_file`（Task 2）、`split_chapters`（Task 3）、`load_progress/save_progress`（Task 5）、`TtsEngine`（Task 6）、ReaderView/ChapterPanel/PlayerBar（Task 7-9）
- Produces:
  - `MainWindow(QMainWindow)`：菜单（文件→打开/退出；设置→字号+/-、行距+/-）、中央 splitter（章节面板+正文）、底部 PlayerBar
  - `MainWindow.open_file()`：文件对话框→读文本→切章→填充列表→恢复进度→显示章节
  - 播放联动：播放从当前选中章节开始；切章按钮同时驱动阅读视图与引擎；声线/语速实时生效；播放状态同步到状态栏
  - `closeEvent`：保存进度并清理 TTS 资源

- [ ] **Step 1: 写失败测试（追加到 tests/test_ui_smoke.py）**

```python
from ui.main_window import MainWindow


def test_main_window_constructs(qapp):
    win = MainWindow()
    assert win.windowTitle() == "小说阅读听书"
    assert win._reader is not None
    assert win._chapter_panel is not None
    assert win._player_bar is not None


def test_main_window_open_file_flow(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    book = tmp_path / "novel.txt"
    book.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()
    assert win._chapter_panel.current_index() == 0
    assert len(win._chapters) == 2
    assert win._chapter_panel._list.count() == 2
    assert "内容甲" in win._reader.toHtml()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_ui_smoke.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'ui.main_window'`。

- [ ] **Step 3: 写实现 ui/main_window.py**

```python
from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QFileDialog, QMainWindow, QMessageBox,
                               QSplitter, QVBoxLayout, QWidget)

from core.chapter_splitter import split_chapters
from core.encoding import read_text_file
from core.progress_store import load_progress, save_progress
from core.tts_engine import TtsEngine
from ui.chapter_panel import ChapterPanel
from ui.player_bar import PlayerBar
from ui.reader_view import ReaderView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说阅读听书")
        self.resize(1000, 700)

        self._engine = TtsEngine(self)
        self._chapters: list[dict] = []
        self._book_path: str | None = None

        self._chapter_panel = ChapterPanel()
        self._reader = ReaderView()
        self._player_bar = PlayerBar()

        splitter = QSplitter()
        splitter.addWidget(self._chapter_panel)
        splitter.addWidget(self._reader)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 780])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        layout.addWidget(self._player_bar)
        self.setCentralWidget(central)

        self._build_menu()
        self._connect_signals()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("文件")
        open_action = file_menu.addAction("打开...")
        open_action.triggered.connect(self.open_file)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

        settings_menu = menu.addMenu("设置")
        settings_menu.addAction("字号 +").triggered.connect(
            lambda: self._reader.set_font_size(self._reader._font_size + 1))
        settings_menu.addAction("字号 -").triggered.connect(
            lambda: self._reader.set_font_size(max(8, self._reader._font_size - 1)))
        settings_menu.addSeparator()
        settings_menu.addAction("行距 +").triggered.connect(
            lambda: self._reader.set_line_spacing(round(self._reader._line_spacing + 0.2, 1)))
        settings_menu.addAction("行距 -").triggered.connect(
            lambda: self._reader.set_line_spacing(max(1.0, round(self._reader._line_spacing - 0.2, 1))))

    def _connect_signals(self) -> None:
        self._chapter_panel.chapter_selected.connect(self._on_chapter_selected)
        self._player_bar.play_toggled.connect(self._on_play_toggled)
        self._player_bar.prev_requested.connect(self._on_prev)
        self._player_bar.next_requested.connect(self._on_next)
        self._player_bar.stop_requested.connect(self._on_stop)
        self._player_bar.voice_changed.connect(self._on_voice_changed)
        self._player_bar.rate_changed.connect(self._on_rate_changed)
        self._engine.playing.connect(self._player_bar.set_playing)
        self._engine.chapter_finished.connect(self._on_chapter_finished)
        self._engine.error.connect(
            lambda msg: QMessageBox.warning(self, "听书出错", msg))

    # ---------- 文件 ----------

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开小说", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if not path:
            return
        try:
            text = read_text_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", f"无法读取文件：\n{exc}")
            return
        self._chapters = split_chapters(text)
        self._book_path = str(Path(path).resolve())
        self._chapter_panel.set_chapters([c["title"] for c in self._chapters])
        progress = load_progress().get(self._book_path, {})
        index = progress.get("chapter", 0)
        self._chapter_panel.select_chapter(index)
        self._show_chapter(index)
        self._reader.restore_scroll(progress.get("scroll", 0))
        name = Path(path).name
        self._player_bar.set_status(f"已打开：{name}（{len(self._chapters)} 章）")

    def _show_chapter(self, index: int) -> None:
        chapter = self._chapters[index]
        self._reader.show_chapter(chapter["title"], chapter["content"])
        self._save_progress()

    def _save_progress(self) -> None:
        if self._book_path:
            save_progress(self._book_path,
                          self._chapter_panel.current_index(),
                          self._reader.scroll_value())

    # ---------- 播放 ----------

    def _on_chapter_selected(self, index: int) -> None:
        self._show_chapter(index)
        self._player_bar.set_status(f"当前章节：{self._chapters[index]['title']}")

    def _on_play_toggled(self) -> None:
        if not self._chapters:
            QMessageBox.information(self, "提示", "请先打开一本小说")
            return
        # 已存在会话（播放中或暂停中）→ 切换播放/暂停；否则从当前章节开始播
        if self._engine.has_session():
            self._engine.toggle_play()
            return
        index = self._chapter_panel.current_index()
        if index < 0:
            index = 0
        self._engine.play_chapters(
            self._chapters, start_index=index,
            voice=self._player_bar.voice(), rate=self._player_bar.rate())
        self._player_bar.set_status(f"正在朗读：{self._chapters[index]['title']}")

    def _on_prev(self) -> None:
        if not self._chapters:
            return
        index = self._chapter_panel.current_index()
        if index <= 0:
            return
        new_index = index - 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)
        if self._engine.is_playing():
            self._engine.prev_chapter()

    def _on_next(self) -> None:
        if not self._chapters:
            return
        index = self._chapter_panel.current_index()
        if index < 0 or index >= len(self._chapters) - 1:
            return
        new_index = index + 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)
        if self._engine.is_playing():
            self._engine.next_chapter()

    def _on_stop(self) -> None:
        self._engine.stop()
        self._player_bar.set_status("已停止")

    def _on_voice_changed(self, voice: str) -> None:
        if self._engine.is_playing():
            self._engine.set_voice(voice)

    def _on_rate_changed(self, rate: str) -> None:
        if self._engine.is_playing():
            self._engine.set_rate(rate)

    def _on_chapter_finished(self) -> None:
        idx = self._engine.current_chapter_index()
        if self._chapters and idx < len(self._chapters):
            self._chapter_panel.select_chapter(idx)
            self._show_chapter(idx)
            if idx + 1 < len(self._chapters):
                self._player_bar.set_status(f"正在朗读：{self._chapters[idx]['title']}")
            else:
                self._player_bar.set_status("全部朗读完毕")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._engine.stop()
        self._save_progress()
        super().closeEvent(event)
```

- [ ] **Step 4: 写入口 main.py**

```python
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("小说阅读听书")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行全部测试验证通过**

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v
```

预期：`10 passed`（含此前全部任务）。

- [ ] **Step 6: 提交**

```bash
git add ui/main_window.py main.py tests/test_ui_smoke.py
git commit -m "feat: main window assembly and app entry"
```

---

### Task 11: README 完善 + 端到端手动验证

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 全部模块
- Produces: 可运行文档与已验证的完整应用

- [ ] **Step 1: 完善 README.md**

````markdown
# 小说阅读听书（t2voice）

Windows 桌面小说阅读听书应用：打开 txt 小说自动分章阅读，支持 edge-tts 朗读。

## 功能

- 打开 txt 小说，自动检测编码（UTF-8/GBK 等），按章节自动划分
- 左侧章节列表选择章节阅读；字号/行距可调；记住每本书的阅读进度
- 从当前章节开始朗读：5 种中文声线、语速 -10%~+50%、播放/暂停/上一章/下一章/停止
- 自动连播下一章；朗读需联网（使用微软 Edge 在线 TTS 服务）

## 安装与运行

```bash
uv venv
uv pip install -e ".[dev]"
uv run python main.py
```

## 测试

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v
```

## 说明

- 听书依赖网络；断网时启动朗读会提示错误
- 进度保存在 `~/.t2voice/progress.json`
````

- [ ] **Step 2: 端到端手动验证清单（需要联网 + 本机音频）**

在本机运行 `uv run python main.py`，逐项验证：

1. 打开一个含"第一章/第二章…"的 GBK 编码 txt → 章节树正确、正文无乱码
2. 打开 UTF-8 带 BOM 文件 → 无乱码、无 BOM 字符
3. 点击章节 → 正文切换正确；重启应用后自动恢复到上次章节和滚动位置
4. 点 ▶ → 从当前章节开始朗读，1-2 秒内出声；状态栏显示章节名
5. 播放中 ⏸ → 暂停；再按 ▶ → 继续
6. 播放中切换声线 → 从当前句以新声线重读
7. 播放中调语速 +50% → 明显加速
8. ⏭ 下一章 / ⏮ 上一章 → 正常切换并朗读
9. 朗读完一章自动连播下一章；最后一章播完状态栏显示"全部朗读完毕"
10. 断开网络后点 ▶ → 弹出"听书出错"提示，界面不崩溃
11. 字号 +/-, 行距 +/- 菜单生效

- [ ] **Step 3: 若手动验证发现问题，回到对应任务修复并补充测试**

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: complete README with usage and verification"
```

---

## 自审记录（writing-plans self-review）

（执行计划后由主控在实现前填写/确认：规格覆盖、占位符、类型一致性三项检查结论）
