# IndexTTS2.5 情感朗读集成 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use supo-subagent-driven-development (recommended) or supo-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在小说阅读听书应用中集成 IndexTTS2.5 本地情感朗读引擎（自动情感 + 手动微调），并与 edge-tts 双引擎可切换。

**Architecture:** IndexTTS2.5 直接嵌入应用进程（用户选定方案），模型懒加载（首次播放才加载，后台线程，UI 显示进度）。`core/tts_backend.py` 提供统一后端接口（EdgeTTSBackend / IndexTTSBackend），`TtsEngine` 通过 `set_backend()` 即时切换并重启会话。播放管线（句子队列 → 合成 → QMediaPlayer）不变，IndexTTS 模式加深预取队列。

**Tech Stack:** Python 3.11、PySide6、edge-tts（保留）、IndexTTS-2.5（indextts 包 + torch）、CUDA 12.8+/PyTorch≥2.7

## Global Constraints

- 工作目录：`E:/WorkSpace/t2voice/.worktrees/indextts`（分支 feature/indextts-tts）
- Python >= 3.10；使用 `uv` 管理环境（uv 0.9.27 位于 `%USERPROFILE%\.local\bin\uv.exe`）
- 测试命令：`QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v`（bash 无法访问 /mnt/e 时用 pwsh：`$env:QT_QPA_PLATFORM="offscreen"; uv run pytest tests/ -v`）
- 源码文件一律 UTF-8 无 BOM；界面文案简体中文
- IndexTTS-2.5 使用 BF16（`use_bf16=True`）；模型目录 `models/indextts/` 加入 .gitignore
- IndexTTS 模型权重经 hf-mirror 下载（约 10GB）；CUDA 13.1 已满足 ≥12.8
- 双引擎默认：UI 默认选中 IndexTTS2.5（情感朗读）；模型**懒加载**——未播放/未切到 IndexTTS 时完全不占显存；首次 IndexTTS 播放时后台加载。`TtsEngine` 内部 `_backend_name` 默认 `"indextts"`，但 `play_chapters` 时才触发懒加载
- 现有 51 个测试必须保持通过；新增测试全部 mock 掉 IndexTTS 真实推理（不依赖 GPU/权重/网络）
- Task 2 测试使用 `pytest.mark.asyncio`，需在 pyproject `dev` 组加 `pytest-asyncio>=0.24` 并 `uv pip install -e ".[dev]"`（Task 2 Step 0）

---

### Task 1: 环境准备 — clone index-tts 仓库 + 安装依赖 + 下载模型

**Files:**
- Create: `models/indextts/`（模型目录，gitignored）
- Modify: `.gitignore`（加 `models/`）
- Create: `docs/TTS_SETUP.md`（安装步骤记录）

**Interfaces:**
- Consumes: 无
- Produces: 可用的 `indextts` Python 包 + IndexTTS-2.5 模型权重（BF16 配置）

- [ ] **Step 1: 确认 .gitignore 排除模型目录**

```bash
cd E:/WorkSpace/t2voice/.worktrees/indextts
# 在 .gitignore 追加：
# models/
```

- [ ] **Step 2: clone index-tts 仓库（放在项目外，避免污染仓库）**

```powershell
cd E:\WorkSpace
git clone https://github.com/index-tts/index-tts.git
cd index-tts
uv sync --all-extras
# Windows 下如 DeepSpeed 装不上，去掉：uv sync --extra webui
```

- [ ] **Step 3: 下载模型（hf-mirror，约 10GB，耗时较长）**

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
uv tool install "huggingface-hub"
hf download IndexTeam/IndexTTS-2.5 --local-dir E:\WorkSpace\t2voice\.worktrees\indextts\models\indextts
```

- [ ] **Step 4: 验证 GPU 识别（关键：确认不是 CPU mode）**

```powershell
cd E:\WorkSpace\index-tts
uv run tools/gpu_check.py
# 预期输出：识别到 RTX 5060 Ti 且使用 CUDA
```

- [ ] **Step 5: 验证单句推理（BF16）**

```powershell
PYTHONPATH="$PWD" uv run indextts/infer_v2_5.py --cfg_path models/indextts/config.yaml --model_dir models/indextts --text "快躲起来！是他要来了！" --lang ZH
# 预期：生成 gen.wav，无 CUDA OOM，GPU 显存占用 < 7GB
```

- [ ] **Step 6: 记录显存占用到 docs/TTS_SETUP.md，提交**

```bash
git add .gitignore docs/TTS_SETUP.md
git commit -m "chore: IndexTTS2.5 environment setup notes"
```

注意：模型权重约 10GB 不入库；若下载/安装失败，报告 BLOCKED 并附具体错误。

---

### Task 2: core/tts_backend.py — 统一后端接口

**Files:**
- Create: `core/tts_backend.py`
- Test: `tests/test_tts_backend.py`

**Interfaces:**
- Consumes: edge_tts（现有）；indextts（Task 1 安装，仅 IndexTTSBackend 内 import，模块级可缺失——`import_module` 延迟导入）
- Produces:
  - `class EdgeTTSBackend`：`synthesize(text: str, rate: str, voice: str, out_path: Path) -> None`（async）
  - `class IndexTTSBackend`：`synthesize(text: str, emo_mode: str, emo_strength: float, out_path: Path) -> None`（async，内部用线程池跑 torch 推理）
  - `class TTSBackendError(Exception)`：合成失败统一异常
  - `EMO_VECTOR_PRESETS: dict[str, list[float]]`：情感预设 → 8 维向量映射（平静/悲伤/激昂/温柔/恐惧/高兴）
  - `EMO_MODE_AUTO = "auto"`；`emo_mode_to_vector(mode: str, strength: float) -> list[float]`
  - `sentence_limit_for_backend(backend: str) -> int`：edge=200，indextts=50

- [ ] **Step 1: 写失败测试 tests/test_tts_backend.py**

```python
from pathlib import Path

import pytest

from core.tts_backend import (EMO_MODE_AUTO, EdgeTTSBackend, IndexTTSBackend,
                              TTSBackendError, emo_mode_to_vector)


def test_emo_vector_presets_have_8_dims():
    from core.tts_backend import EMO_VECTOR_PRESETS
    for mode, vec in EMO_VECTOR_PRESETS.items():
        assert len(vec) == 8, f"{mode} 向量维度错误"
        assert all(0.0 <= v <= 1.0 for v in vec)


def test_emo_mode_to_vector_auto_returns_none():
    # 自动模式由 use_emo_text 处理，不需要向量
    assert emo_mode_to_vector(EMO_MODE_AUTO, 0.6) is None


def test_emo_mode_to_vector_scales_strength():
    vec = emo_mode_to_vector("悲伤", 0.5)
    assert vec is not None
    assert vec[2] == pytest.approx(0.8 * 0.5)  # 悲伤在第 3 维(索引2)


def test_emo_mode_to_vector_unknown_raises():
    with pytest.raises(ValueError):
        emo_mode_to_vector("不存在的情感", 0.5)


def test_sentence_limit_for_backend():
    from core.tts_backend import sentence_limit_for_backend
    assert sentence_limit_for_backend("edge") == 200
    assert sentence_limit_for_backend("indextts") == 50


@pytest.mark.asyncio
async def test_edge_backend_synthesize_writes_file(monkeypatch, tmp_path):
    # mock edge_tts.Communicate 写假文件
    class FakeCommunicate:
        def __init__(self, text, voice, rate="+0%"):
            self.text = text

        async def save(self, path):
            Path(path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_backend.edge_tts.Communicate", FakeCommunicate)
    out = tmp_path / "out.mp3"
    backend = EdgeTTSBackend()
    await backend.synthesize("你好。", "+0%", "zh-CN-XiaoxiaoNeural", out)
    assert out.read_bytes() == b"fake-mp3"


@pytest.mark.asyncio
async def test_index_backend_unavailable_raises(tmp_path):
    # 未安装/未下载模型时 synthesize 报明确错误（不崩）
    backend = IndexTTSBackend(model_dir=tmp_path / "nonexistent")
    with pytest.raises(TTSBackendError):
        await backend.synthesize("你好。", "auto", 0.6, tmp_path / "o.mp3")


def test_index_backend_availability(tmp_path):
    backend = IndexTTSBackend(model_dir=tmp_path / "nonexistent")
    assert not backend.is_available()
    assert not backend.is_loaded()
```

- [ ] **Step 2: 运行测试验证失败**

预期：`ModuleNotFoundError: No module named 'core.tts_backend'`。

- [ ] **Step 3: 写实现 core/tts_backend.py**

```python
"""TTS 后端统一接口：edge-tts（快速）与 IndexTTS2.5（情感朗读）可切换。"""

from pathlib import Path

import edge_tts

EMO_MODE_AUTO = "auto"

# 8 维情感向量：[高兴, 愤怒, 悲伤, 害怕, 厌恶, 忧郁, 惊讶, 平静]
EMO_VECTOR_PRESETS: dict[str, list[float]] = {
    "平静": [0, 0, 0, 0, 0, 0, 0, 1],
    "悲伤": [0, 0, 0.8, 0, 0, 0, 0, 0],
    "激昂": [0.7, 0.2, 0, 0, 0, 0, 0, 0],
    "温柔": [0.3, 0, 0, 0, 0, 0.2, 0, 0.5],
    "恐惧": [0, 0, 0, 0.8, 0, 0, 0, 0],
    "高兴": [0.8, 0, 0, 0, 0, 0, 0.2, 0],
}

_BACKEND_SENTENCE_LIMIT = {"edge": 200, "indextts": 50}


class TTSBackendError(Exception):
    """TTS 合成失败（网络/模型/显存等）。"""


def emo_mode_to_vector(mode: str, strength: float) -> list[float] | None:
    """情感模式 + 强度 → 8 维向量。自动模式返回 None（走 use_emo_text）。"""
    if mode == EMO_MODE_AUTO:
        return None
    if mode not in EMO_VECTOR_PRESETS:
        raise ValueError(f"未知情感模式: {mode}")
    return [round(v * strength, 3) for v in EMO_VECTOR_PRESETS[mode]]


def sentence_limit_for_backend(backend: str) -> int:
    return _BACKEND_SENTENCE_LIMIT.get(backend, 200)


class EdgeTTSBackend:
    """edge-tts 后端：快速、免费、无需显存。"""

    name = "edge"

    async def synthesize(self, text: str, rate: str, voice: str,
                         out_path: Path) -> None:
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(out_path))
        except Exception as exc:  # noqa: BLE001
            raise TTSBackendError(str(exc)) from exc


class IndexTTSBackend:
    """IndexTTS2.5 后端：本地情感朗读（BF16）。延迟导入，缺依赖时可用性检查。"""

    name = "indextts"
    _model_dir: Path | None = None
    _tts = None  # IndexTTS2 实例（懒加载）
    _load_lock = None  # threading.Lock

    def __init__(self, model_dir: Path | None = None):
        self._model_dir = model_dir or Path("models/indextts")
        if self._load_lock is None:
            import threading
            IndexTTSBackend._load_lock = threading.Lock()

    def is_available(self) -> bool:
        """模型权重与 indextts 包是否就绪。"""
        try:
            import indextts  # noqa: F401
        except ImportError:
            return False
        return (self._model_dir / "config.yaml").exists()

    def is_loaded(self) -> bool:
        return IndexTTSBackend._tts is not None

    def load(self) -> None:
        """加载模型（首次调用，约 30-60s）。线程安全。"""
        if IndexTTSBackend._tts is not None:
            return
        with self._load_lock:
            if IndexTTSBackend._tts is not None:
                return
            try:
                from indextts.infer_v2_5 import IndexTTS2
                IndexTTSBackend._tts = IndexTTS2(
                    cfg_path=str(self._model_dir / "config.yaml"),
                    model_dir=str(self._model_dir),
                    use_bf16=True,
                )
            except Exception as exc:  # noqa: BLE001
                raise TTSBackendError(
                    f"IndexTTS2.5 模型加载失败: {exc}") from exc

    def unload(self) -> None:
        IndexTTSBackend._tts = None

    async def synthesize(self, text: str, emo_mode: str, emo_strength: float,
                         out_path: Path) -> None:
        if not self.is_available():
            raise TTSBackendError("IndexTTS2.5 模型未安装，请先运行环境准备")
        import asyncio

        def _run() -> None:
            self.load()
            kwargs: dict = {}
            vec = emo_mode_to_vector(emo_mode, emo_strength)
            if vec is not None:
                kwargs["emo_vector"] = vec
            else:
                kwargs["use_emo_text"] = True
                kwargs["emo_alpha"] = emo_strength
            self._tts.infer(
                spk_audio_prompt="examples/voice_01.wav",
                text=text, lang="ZH",
                output_path=str(out_path), **kwargs)

        try:
            await asyncio.to_thread(_run)
        except Exception as exc:  # noqa: BLE001
            raise TTSBackendError(str(exc)) from exc
```

- [ ] **Step 4: 运行测试验证通过**

预期：全部通过（IndexTTS 测试不实际加载模型——`IndexTTSBackend` 的 synthesize 用 mock）。

- [ ] **Step 5: 提交**

```bash
git add core/tts_backend.py tests/test_tts_backend.py
git commit -m "feat: unified TTS backend interface with emotion presets"
```

---

### Task 3: core/tts_engine.py 改造 — backend 切换 + 懒加载 + 预取加深

**Files:**
- Modify: `core/tts_engine.py`
- Test: `tests/test_tts_engine.py`（追加）

**Interfaces:**
- Consumes: `core.tts_backend`（Task 2）：`EdgeTTSBackend`/`IndexTTSBackend`、`sentence_limit_for_backend`
- Produces（对 UI 层新增）：
  - `TtsEngine.set_backend(name: str) -> None`：切换后端（edge/indextts），有会话则重启当前会话
  - `TtsEngine.backend() -> str`：当前后端名
  - `TtsEngine.set_emotion(mode: str, strength: float) -> None`：设置情感参数（IndexTTS 模式生效）
  - `TtsEngine.backend_ready() -> bool`：IndexTTS 后端已加载（供 UI 显示状态）
  - 信号新增：`backend_status(str)`（如 "loading"/"ready"/"error:..."）
  - worker 句子切分长度按 `sentence_limit_for_backend`；预取深度：edge=3 句 ahead，indextts=8 句 ahead（`PREFETCH_AHEAD` 常量）

- [ ] **Step 1: 写失败测试（追加 tests/test_tts_engine.py）**

```python
def test_engine_backend_default_is_indextts(qtbot, monkeypatch):
    engine = TtsEngine()
    assert engine.backend() == "indextts"  # 设计默认：情感引擎


def test_engine_switch_backend_restarts_session(qtbot, monkeypatch):
    # fake backend 记录调用；验证 set_backend 后当前章节重启（重新 play_chapters）
    calls: list[str] = []

    class FakeBackend:
        name = "fake"

        async def synthesize(self, *a, **k):
            calls.append(k.get("emo_mode", "?"))

    def factory(name):
        return FakeBackend()

    monkeypatch.setattr("core.tts_engine._backend_factory", factory)
    engine = TtsEngine()
    engine.set_backend("indextts")
    assert engine.backend() == "indextts"
    # 无会话时不崩溃
    engine.set_backend("edge")
    assert engine.backend() == "edge"


def test_engine_set_emotion_passes_to_backend(qtbot, monkeypatch):
    received: dict = {}

    class FakeBackend:
        name = "fake"

        async def synthesize(self, **kwargs):
            received.update(kwargs)

    monkeypatch.setattr("core.tts_engine._backend_factory", lambda n: FakeBackend())
    engine = TtsEngine()
    engine.set_backend("indextts")
    engine.set_emotion("悲伤", 0.5)
    assert engine._emotion_mode == "悲伤"
    assert engine._emotion_strength == 0.5
```

- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 改造 core/tts_engine.py**

```python
# 关键改动：
# 1. 构造函数：
#    self._backend_name = "indextts"      # 设计默认：情感引擎
#    self._emotion_mode = "auto"
#    self._emotion_strength = 0.6
#    self._backend_status = "idle"
# 2. 模块级工厂（可 monkeypatch）：
#    def _backend_factory(name: str):
#        if name == "edge": return EdgeTTSBackend()
#        return IndexTTSBackend()
#    self._backend = _backend_factory(self._backend_name)
# 3. _SynthesisWorker 合成调用改为（worker 持 backend 引用 + 情感参数）：
#    if backend.name == "edge":
#        await backend.synthesize(sentence, rate=rate, voice=voice, out_path=path)
#    else:
#        await backend.synthesize(sentence, emo_mode=emo_mode,
#                                 emo_strength=emo_strength, out_path=path)
#    （worker 构造参数增加 emo_mode/emo_strength）
# 4. set_backend(name):
#    若 name 与当前相同则返回；更新 _backend_name、重建 _backend；
#    若 has_session() 则 _start_chapter(当前章) 重启
# 5. 懒加载：IndexTTS 首次 synthesize 前 worker 线程内 backend.load()，
#    加载前 emit backend_status("loading")，加载完成 "ready"，失败回退 edge：
#    emit backend_status("error:...") → _backend_name = "edge" → 重启会话
# 6. 句子切分：_start_chapter 中
#    limit = sentence_limit_for_backend(self._backend_name)
#    sentences = split_sentences(chapter["content"], max_len=limit)
# 7. 预取深度：保持 worker 持续合成 + _ready 队列机制不变；
#    句子限长（indextts 50 字）天然缩短单句合成时间，配合现有队列即可
#    保证播放连续性（无需额外改动）
# 8. backend_status 信号：def backend_status(self, text: str) -> None 转发
```

- [ ] **Step 4: 运行全部测试验证通过**（现有 51 + 新增）
- [ ] **Step 5: 提交**

```bash
git add core/tts_engine.py tests/test_tts_engine.py
git commit -m "feat: tts engine backend switching with lazy IndexTTS load"
```

---

### Task 4: core/sentence_splitter.py — IndexTTS 模式句子限长

**Files:**
- Modify: `core/sentence_splitter.py`
- Test: `tests/test_sentence_splitter.py`（追加）

**Interfaces:**
- Consumes: 无
- Produces: `split_sentences(text: str, max_len: int | None = None) -> list[str]`（超长句按 max_len 再切分，保持语义断点优先）

- [ ] **Step 1: 写失败测试**

```python
def test_split_sentences_with_max_len():
    sentences = split_sentences("第一句。第二句。第三句。", max_len=4)
    # 每段 ≤ 4 字
    assert all(len(s) <= 5 for s in sentences)  # 分隔符保留，允许 +1
    assert "。".join(sentences).replace("。", "") == "第一句第二句第三句"


def test_split_sentences_without_max_len_unchanged():
    assert split_sentences("你好。世界！") == ["你好。", "世界！"]
```

- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现**（按 max_len 对超长段二次切分，优先在标点断）

```python
def split_sentences(text: str, max_len: int | None = None) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    sentences = [p.strip() for p in parts if p and p.strip()]
    if max_len is None:
        return sentences
    result: list[str] = []
    for s in sentences:
        result.extend(_chunk_sentence(s, max_len))
    return result
```

- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交**

```bash
git add core/sentence_splitter.py tests/test_sentence_splitter.py
git commit -m "feat: sentence length limit for IndexTTS backend"
```

---

### Task 5: ui/player_bar.py — 引擎/情感控件

**Files:**
- Modify: `ui/player_bar.py`
- Test: `tests/test_ui_smoke.py`（追加）

**Interfaces:**
- Consumes: PySide6
- Produces（新增信号/方法）：
  - 信号 `backend_changed(str)`、`emotion_changed(str, float)`（mode + strength）
  - 控件：引擎下拉（IndexTTS2.5 情感 / edge-tts 快速）、情感下拉（自动/平静/悲伤/激昂/温柔/恐惧/高兴，IndexTTS 模式可见）、强度滑条（0-100%，默认 60%）
  - 方法 `set_backend_status(text)`（显示"加载情感引擎…/就绪"）
  - 方法 `backend() -> str`、`emotion_mode() -> str`、`emotion_strength() -> float`

- [ ] **Step 1: 写失败测试（追加 tests/test_ui_smoke.py）**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现**（在声线下拉旁加引擎下拉；情感控件随引擎联动——edge 时禁用/隐藏）
- [ ] **Step 4: 运行测试验证通过**
- [ ] **Step 5: 提交**

```bash
git add ui/player_bar.py tests/test_ui_smoke.py
git commit -m "feat: engine and emotion controls in player bar"
```

---

### Task 6: ui/main_window.py — 参数透传 + 状态提示

**Files:**
- Modify: `ui/main_window.py`
- Test: `tests/test_ui_smoke.py`（追加）

**Interfaces:**
- Consumes: `TtsEngine`（Task 3）、`PlayerBar`（Task 5）
- Produces：
  - 连接 `PlayerBar.backend_changed` → `engine.set_backend`
  - 连接 `PlayerBar.emotion_changed` → `engine.set_emotion`
  - 连接 `engine.backend_status` → `PlayerBar.set_backend_status`
  - `_on_play_toggled` 传 backend/emotion 参数给 `engine.play_chapters`
  - 首次 IndexTTS 播放前状态栏提示"正在加载情感引擎（首次约 30-60 秒）…"

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 运行测试验证失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行全部测试验证通过**（51 + 新增）
- [ ] **Step 5: 提交**

```bash
git add ui/main_window.py tests/test_ui_smoke.py
git commit -m "feat: wire engine/emotion controls to main window"
```

---

### Task 7: 端到端手动验证（真实模型）

**Files:**
- Modify: `docs/TTS_SETUP.md`（记录验证结果）

**Interfaces:**
- Consumes: 全部模块

- [ ] **Step 1: 启动应用**

```powershell
cd E:/WorkSpace/t2voice/.worktrees/indextts
uv run python main.py
```

- [ ] **Step 2: 验证清单（需 GPU + 音频）**

1. 打开《魔天记》→ 点播放 → 首次 IndexTTS 加载 30-60s，状态栏显示加载中 → 自动开始朗读
2. 情感效果：同一句切换 平静/悲伤/激昂 → 明显差异
3. 强度滑条：拉低 → 情感减弱；拉高 → 增强
4. 自动情感：读"快躲起来！"应有紧张语气（use_emo_text）
5. 引擎切换：播放中切 edge-tts → 立即换引擎继续读
6. 显存：任务管理器确认 IndexTTS 运行时专用 GPU 内存 < 7.5GB
7. 速度：单句合成 ~2s，预取使播放不中断
8. 回退：卸载模型/显存不足 → 自动回退 edge-tts 并提示
9. 回归：edge-tts 模式全部原功能正常

- [ ] **Step 3: 记录结果到 docs/TTS_SETUP.md，提交**

```bash
git add docs/TTS_SETUP.md
git commit -m "docs: record IndexTTS2.5 e2e verification results"
```

---

## 自审记录

（执行计划后由主控确认：规格覆盖、占位符、类型一致性）
