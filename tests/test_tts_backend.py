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


def test_load_after_cancel_resets_flag(monkeypatch):
    """Finding: cancel_load() 后同一实例再次 load() 必须重置取消标志，
    越过首个检查点（异常来自 import 失败，而非"已取消"）。"""
    IndexTTSBackend._tts = None  # 防御：确保类级单例为空
    backend = IndexTTSBackend(model_dir=Path("models/indextts"))
    assert not backend.is_loaded()

    backend.cancel_load()
    assert backend._load_cancelled is True

    # 模型可用（避免任何可用性短路），但 indextts import 抛哨兵异常
    monkeypatch.setattr(IndexTTSBackend, "is_available", lambda self: True)

    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "indextts" or name.startswith("indextts."):
            raise ImportError("sentinel-import-error")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(TTSBackendError) as exc_info:
        backend.load()
    # 关键断言：已越过首个取消检查点 → 异常来自 import 失败，而非"已取消"
    assert "已取消" not in str(exc_info.value)
    assert backend._load_cancelled is False


# ---------- Task 6: 参考音频（spk_audio_prompt）可配置 ----------


def test_index_backend_accepts_spk_audio_prompt_param(tmp_path):
    """构造参数显式指定参考音频路径（权威值，即使文件不存在也原样保留）。"""
    ref = tmp_path / "voice_01.wav"
    ref.write_bytes(b"fake-wav")
    backend = IndexTTSBackend(model_dir=tmp_path / "models",
                              spk_audio_prompt=ref)
    assert backend._spk_audio_prompt == ref


def test_index_backend_resolves_spk_audio_prompt_from_env(monkeypatch, tmp_path):
    """未显式指定时优先从环境变量 INDEXTTS_REF_AUDIO 解析。"""
    ref = tmp_path / "voice_01.wav"
    ref.write_bytes(b"fake-wav")
    monkeypatch.setenv("INDEXTTS_REF_AUDIO", str(ref))
    backend = IndexTTSBackend(model_dir=tmp_path / "models")
    assert backend._spk_audio_prompt == ref


def test_index_backend_no_prompt_env_keeps_default_resolution(monkeypatch, tmp_path):
    """环境变量指向不存在的文件时不采纳，继续走常见位置候选。"""
    monkeypatch.setenv("INDEXTTS_REF_AUDIO", str(tmp_path / "missing.wav"))
    # 构造真实存在的候选：CWD 下建 examples/voice_01.wav
    examples = tmp_path / "examples"
    examples.mkdir()
    ref = examples / "voice_01.wav"
    ref.write_bytes(b"fake-wav")
    monkeypatch.chdir(tmp_path)
    backend = IndexTTSBackend(model_dir=tmp_path / "models")
    assert backend._spk_audio_prompt == ref


@pytest.mark.asyncio
async def test_index_backend_missing_spk_audio_prompt_raises(tmp_path):
    """参考音频缺失时 synthesize 报明确错误（不依赖机器上是否存在克隆仓库）。"""
    backend = IndexTTSBackend(model_dir=tmp_path / "models",
                              spk_audio_prompt=tmp_path / "no_such.wav")
    with pytest.raises(TTSBackendError) as exc_info:
        await backend.synthesize("你好。", "auto", 0.6, tmp_path / "o.mp3")
    assert "INDEXTTS_REF_AUDIO" in str(exc_info.value)
