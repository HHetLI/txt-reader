"""TTS 后端统一接口：edge-tts（快速）与 IndexTTS2.5（情感朗读）可切换。"""

import os
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


#: 常见参考音频候选位置（按优先级）：CWD 相对、Task 1 克隆的 index-tts 仓库
_SPK_AUDIO_CANDIDATES = (
    Path("examples/voice_01.wav"),
    Path(r"E:/WorkSpace/index-tts/examples/voice_01.wav"),
)


def resolve_spk_audio_prompt(explicit: Path | None = None) -> Path | None:
    """解析 IndexTTS 参考音频（spk_audio_prompt）路径。

    优先级：显式构造参数 > 环境变量 INDEXTTS_REF_AUDIO > 常见位置
    （CWD 相对 examples/voice_01.wav、index-tts 克隆仓库内 examples/voice_01.wav）。
    显式参数是权威值——即使文件当前不存在也原样返回（存在性在 synthesize 时
    校验并报明确错误）；环境变量与常见位置只采纳真实存在的文件，全部缺失返回
    None（同样在 synthesize 时报错）。
    """
    if explicit is not None:
        return explicit.resolve()
    env = os.environ.get("INDEXTTS_REF_AUDIO")
    if env:
        env_path = Path(env)
        if env_path.is_file():
            return env_path.resolve()
    for candidate in _SPK_AUDIO_CANDIDATES:
        if candidate.is_file():
            # 转为绝对路径：构造与合成可能跨目录（合成时 CWD 未必还是构造时的 CWD）
            return candidate.resolve()
    return None


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

    def __init__(self, model_dir: Path | None = None,
                 spk_audio_prompt: Path | str | None = None):
        self._model_dir = model_dir or Path("models/indextts")
        # 参考音频路径可配置：显式参数 > INDEXTTS_REF_AUDIO > 常见位置（见
        # resolve_spk_audio_prompt）。不硬编码仓库外路径，缺失时 synthesize 报明确错误。
        self._spk_audio_prompt = resolve_spk_audio_prompt(
            Path(spk_audio_prompt) if spk_audio_prompt is not None else None)
        # 加载取消标记：worker 退役时置位，load() 在检查点快速抛错返回，
        # 避免退役线程在 30-60s 模型加载中长期滞留（QThread GC 崩溃窗口）
        self._load_cancelled = False
        if self._load_lock is None:
            import threading
            IndexTTSBackend._load_lock = threading.Lock()

    def cancel_load(self) -> None:
        """请求取消加载。线程安全（检查点轮询标志，非强制中断）。"""
        self._load_cancelled = True

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
        """加载模型（首次调用，约 30-60s）。线程安全，可被 cancel_load 取消。"""
        if IndexTTSBackend._tts is not None:
            return
        with self._load_lock:
            if IndexTTSBackend._tts is not None:
                return
            # 新加载尝试应允许重试（取消标志仅针对单次加载，须在首个检查点前重置）
            self._load_cancelled = False
            if self._load_cancelled:
                raise TTSBackendError("IndexTTS 模型加载已取消")
            try:
                from indextts.infer_v2_5 import IndexTTS2
                # 检查点：import（含 torch 等重依赖）结束后仍被取消则放弃
                if self._load_cancelled:
                    raise TTSBackendError("IndexTTS 模型加载已取消")
                IndexTTSBackend._tts = IndexTTS2(
                    cfg_path=str(self._model_dir / "config.yaml"),
                    model_dir=str(self._model_dir),
                    use_bf16=True,
                )
                # 检查点：构造期间收到取消 → 卸载并放弃，线程立即结束
                if self._load_cancelled:
                    self.unload()
                    raise TTSBackendError("IndexTTS 模型加载已取消")
            except TTSBackendError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise TTSBackendError(
                    f"IndexTTS2.5 模型加载失败: {exc}") from exc

    def unload(self) -> None:
        IndexTTSBackend._tts = None

    async def synthesize(self, text: str, emo_mode: str, emo_strength: float,
                         out_path: Path) -> None:
        prompt = self._spk_audio_prompt
        if prompt is None or not prompt.is_file():
            raise TTSBackendError(
                "参考音频缺失（voice_01.wav）：请设置环境变量 INDEXTTS_REF_AUDIO "
                "指向 index-tts 的 examples/voice_01.wav，或在 CWD 的 "
                "examples/ 目录放置参考音频")
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
                spk_audio_prompt=str(prompt),
                text=text, lang="ZH",
                output_path=str(out_path), **kwargs)

        try:
            await asyncio.to_thread(_run)
        except Exception as exc:  # noqa: BLE001
            raise TTSBackendError(str(exc)) from exc
