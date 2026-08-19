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
