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


def test_load_passes_use_qwen_emo_for_auto_emotion(monkeypatch):
    """Finding (e2e): 自动情感 use_emo_text 依赖 QwenEmotion，构造 IndexTTS2 必须
    传 use_qwen_emo=True，否则真实推理时 RuntimeError。参考 CLI 亦如此。"""
    IndexTTSBackend._tts = None
    captured: dict = {}

    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # 提供假 indextts.infer_v2_5 模块（避免真实 torch 加载），并让 is_available 通过
    monkeypatch.setattr(IndexTTSBackend, "is_available", lambda self: True)
    import types

    fake_mod = types.ModuleType("indextts.infer_v2_5")
    fake_mod.IndexTTS2 = FakeIndexTTS2

    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "indextts.infer_v2_5" or name == "indextts":
            return fake_mod
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    backend = IndexTTSBackend(model_dir=Path("models/indextts"))
    backend.load()
    assert captured.get("use_qwen_emo") is True
    assert captured.get("use_bf16") is True
    IndexTTSBackend._tts = None  # 清理类级单例


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


# ---------- Final review：加载取消生命周期 + 合成 kwargs 路由 ----------


def test_load_cancel_after_construction_keeps_model(monkeypatch):
    """取消到达"构造完成后"检查点：不 unload，已构造模型保留供复用。"""
    IndexTTSBackend._tts = None
    import threading
    construct_entered = threading.Event()
    release_constructor = threading.Event()

    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            construct_entered.set()
            release_constructor.wait(10)  # 模拟构造耗时（真实约 264s）
            IndexTTSBackend._tts = self   # 模拟构造完成（真实代码构造后赋值）

    import types
    fake_mod = types.ModuleType("indextts.infer_v2_5")
    fake_mod.IndexTTS2 = FakeIndexTTS2
    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "indextts.infer_v2_5" or name == "indextts":
            return fake_mod
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(IndexTTSBackend, "is_available", lambda self: True)
    backend = IndexTTSBackend(model_dir=Path("models/indextts"))
    errors: list[Exception] = []

    def run():
        try:
            backend.load()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=run)
    t.start()
    assert construct_entered.wait(5)  # 已进入构造
    backend.cancel_load()             # 构造期间收到取消
    release_constructor.set()
    t.join(10)
    # 构造已完成：模型保留（不 unload），本次 load 因"已取消"退出
    assert backend.is_loaded()
    assert errors and "已取消" in str(errors[0])
    # 复用：同一实例再次 load 直接返回（模型已就绪，不再重复构造）
    backend.load()
    assert backend.is_loaded()
    IndexTTSBackend._tts = None


def test_load_cancel_before_construction_keeps_nothing(monkeypatch):
    """取消在构造前（import 期间）到达：模型不构造，加载抛"已取消"。"""
    IndexTTSBackend._tts = None
    import threading
    import_entered = threading.Event()
    release_import = threading.Event()
    constructed: list[str] = []

    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            constructed.append("constructed")

    import types
    fake_mod = types.ModuleType("indextts.infer_v2_5")
    fake_mod.IndexTTS2 = FakeIndexTTS2
    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "indextts.infer_v2_5" or name == "indextts":
            import_entered.set()
            release_import.wait(10)  # 模拟重依赖 import 耗时
            return fake_mod
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(IndexTTSBackend, "is_available", lambda self: True)
    backend = IndexTTSBackend(model_dir=Path("models/indextts"))
    errors: list[Exception] = []

    def run():
        try:
            backend.load()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=run)
    t.start()
    assert import_entered.wait(5)  # import 进行中（构造前）
    backend.cancel_load()          # 构造前取消
    release_import.set()
    t.join(10)
    assert constructed == []           # 未构造模型
    assert not backend.is_loaded()
    assert errors and "已取消" in str(errors[0])
    IndexTTSBackend._tts = None


@pytest.mark.asyncio
async def test_index_backend_synthesize_routes_emotion_kwargs(monkeypatch, tmp_path):
    """synthesize 的 kwargs 路由：auto → use_emo_text；手动模式 → emo_vector。

    纯离线：monkeypatch 假 _tts 记录 infer kwargs，不加载真实模型。
    """
    IndexTTSBackend._tts = None
    inferred: list[dict] = []

    class FakeTTS:
        def infer(self, **kwargs):
            inferred.append(kwargs)

    ref = tmp_path / "voice_01.wav"
    ref.write_bytes(b"fake-wav")
    monkeypatch.setattr(IndexTTSBackend, "is_available", lambda self: True)
    monkeypatch.setattr(IndexTTSBackend, "_tts", FakeTTS())
    backend = IndexTTSBackend(model_dir=tmp_path / "models",
                              spk_audio_prompt=ref)
    # 自动模式：use_emo_text=True + emo_alpha（强度）
    await backend.synthesize("你好。", "auto", 0.6, tmp_path / "o1.mp3")
    assert inferred[-1]["use_emo_text"] is True
    assert inferred[-1]["emo_alpha"] == 0.6
    # 手动模式：emo_vector 按强度缩放（悲伤第 3 维 0.8 × strength）
    await backend.synthesize("你好。", "悲伤", 0.5, tmp_path / "o2.mp3")
    vec = inferred[-1]["emo_vector"]
    assert vec[2] == pytest.approx(0.8 * 0.5)
    assert "use_emo_text" not in inferred[-1]
    assert inferred[-1]["lang"] == "ZH"
    assert inferred[-1]["spk_audio_prompt"] == str(ref)
    IndexTTSBackend._tts = None


# ---------- 模型卸载（显存释放） ----------


def test_unload_clears_class_singleton(monkeypatch):
    """unload 后类级单例置空，is_loaded() 为 False，返回 True。"""
    IndexTTSBackend._tts = object()
    assert IndexTTSBackend.unload() is True
    assert IndexTTSBackend._tts is None
    assert not IndexTTSBackend().is_loaded()


def test_unload_calls_cuda_empty_cache(monkeypatch):
    """unload 触发 torch.cuda.empty_cache() 真正释放显存。"""
    import sys
    import types
    IndexTTSBackend._tts = object()
    calls: list[str] = []

    class _FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def empty_cache():
            calls.append("empty_cache")

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = _FakeCuda()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert IndexTTSBackend.unload() is True
    assert calls == ["empty_cache"]
    IndexTTSBackend._tts = None


def test_unload_when_not_loaded_is_noop(monkeypatch):
    """未加载时 unload 安全返回 False，无副作用。"""
    IndexTTSBackend._tts = None
    assert IndexTTSBackend.unload() is False
    assert IndexTTSBackend._tts is None


def test_unload_without_cuda_skips_empty_cache(monkeypatch):
    """无 CUDA（is_available False）时 unload 不调 empty_cache、不抛异常。"""
    import sys
    import types
    IndexTTSBackend._tts = object()
    calls: list[str] = []

    class _FakeCuda:
        @staticmethod
        def is_available():
            return False

        @staticmethod
        def empty_cache():
            calls.append("empty_cache")

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = _FakeCuda()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert IndexTTSBackend.unload() is True
    assert calls == []
    IndexTTSBackend._tts = None
