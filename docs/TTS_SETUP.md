# IndexTTS2.5 环境部署记录

日期：2026-08-19

## 硬件
- GPU: RTX 5060 Ti 8GB (8151 MiB)，驱动 591.86，CUDA 13.1
- CPU: i5-14600K，内存 32GB

## 模型与依赖位置
- 代码仓库（项目外）: `E:\WorkSpace\index-tts`（git clone github）
- 模型权重: `models/indextts/`（5.1GB，从 ModelScope `IndexTeam/IndexTTS-2.5` 下载）
- 辅助模型（均在 `models/indextts/hf_cache/`）:
  - `w2v-bert-2.0/`（4.4GB，ModelScope `facebook/w2v-bert-2.0`）
  - `campplus_cn_common.bin`（28MB，ModelScope `iic/speech_campplus_sv_zh-cn_16k-common`）
  - `semantic_codec_model.safetensors`（177MB，ModelScope `amphion/MaskGCT`）
  - `bigvgan/config.json` + `bigvgan_generator.pt`（449MB，ModelScope `nv-community/bigvgan_v2_22khz_80band_256x`）
- 参考音频: `E:\WorkSpace\index-tts\examples\voice_01.wav`（edge-tts 生成的 2 秒中文语音）

## Python 环境（index-tts 仓库独立 venv）
- Python 3.11.13，torch 2.8.0+cu128，transformers 4.52.1
- 安装：`uv pip install`（核心依赖）+ matplotlib/pandas 等
- 注：`uv sync` 全量安装卡住，改用 uv pip 分步安装

## 性能实测
- 模型加载: ~4 分钟（含 QwenEmotion 实测 264s，懒加载一次，应用启动后首次播放时）
- 常驻显存: 6152 MiB / 8151 MiB（75%，可用 ~2GB 富余）
- 合成速度: 首句 ~20s（含预热），稳态 ~7s/句（2-3 秒音频）
- RTF: ~4.8（CLI 实测）

## 运行命令
```powershell
cd E:\WorkSpace\index-tts
$env:PYTHONPATH = "E:\WorkSpace\index-tts"
$env:HF_HUB_CACHE = "E:\WorkSpace\t2voice\.worktrees\indextts\models\indextts\hf_cache"
.\.venv\Scripts\python.exe indextts\infer_v2_5.py --cfg_path "E:\WorkSpace\t2voice\.worktrees\indextts\models\indextts\config.yaml" --model_dir "E:\WorkSpace\t2voice\.worktrees\indextts\models\indextts" --text "测试文本" --lang ZH --output gen.wav
```

## 关键坑
1. w2v-bert-2.0 是 gated 模型，huggingface_hub 库下载 401；**用 ModelScope `facebook/w2v-bert-2.0` curl 直下最快（16MB/s）**
2. ModelScope 下载后须校验 sha256（首次下载被污染过，重下即好）
3. 示例音频 `voice_01.wav` 官方源 404，用 edge-tts 生成替代
4. python -c 方式调用 infer 不稳定（挂起），**用脚本文件 + use_qwen_emo=True + text_normalization=True** 稳定

## 参考音频（spk_audio_prompt）解析

IndexTTS 的 `spk_audio_prompt` 不再硬编码，`IndexTTSBackend` 构造时按以下优先级解析
（见 `core/tts_backend.py` 的 `resolve_spk_audio_prompt`）：

1. 构造参数 `spk_audio_prompt=`（权威值，即使文件不存在也原样保留，合成时校验）
2. 环境变量 `INDEXTTS_REF_AUDIO`（指向 `examples/voice_01.wav` 的绝对路径）
3. 常见位置：CWD 下 `examples/voice_01.wav` → `E:\WorkSpace\index-tts\examples\voice_01.wav`

全部缺失时合成（synthesize）阶段报明确 `TTSBackendError`，提示设置 `INDEXTTS_REF_AUDIO`。

---

## 端到端验证（Task 7，2026-08-19，真实 GPU 模型）

通过应用自身代码路径（`core/tts_backend.py` 的 `IndexTTSBackend`）对真实 IndexTTS-2.5
模型做推理验证（非 CLI 直调，走后端统一接口）：

### 验证命令

```powershell
# 全量测试（mock 层，离线）：91 passed
cd E:/WorkSpace/t2voice/.worktrees/indextts
$env:QT_QPA_PLATFORM="offscreen"; E:/WorkSpace/t2voice/.venv/Scripts/python.exe -m pytest tests/ -v

# 真实推理（需 GPU，index-tts venv 含 torch/indextts）
cd E:/WorkSpace/t2voice/.worktrees/indextts
E:/WorkSpace/index-tts/.venv/Scripts/python.exe .superpowers/sdd/scratch_e2e_verify.py
```

注意：scratch 脚本用 `E:/WorkSpace/index-tts/.venv`（torch/indextts 所在），但 `sys.path`
指向 worktree 的 `core/`，即**跑应用自己的 `IndexTTSBackend` 代码路径**。该 venv 另装了
`edge-tts==7.2.8`（与主 venv 同版本，`core/tts_backend.py` 模块级 import 所需）。

### 结果

| 项 | 结果 |
|---|---|
| 模型加载 | 264s（含 QwenEmotion，懒加载一次） |
| 自动情感 `emo_mode="auto"`（use_emo_text） | 成功，142380B wav，首句 46.6s（含预热），稳态 RTF 0.74 |
| 手动向量 `emo_mode="悲伤"`（emo_vector） | 成功，137260B wav，稳态 2.4s/句 |
| 推理文本 | “快躲起来！是他要来了！”（lang=ZH） |
| 输出 | `.superpowers/sdd/e2e_out/e2e_auto.wav` / `e2e_sad.wav`，均 >10KB |
| 显存（应用进程） | 加载后 ~6.2GB，推理峰值 ~6.5GB 分配 / 6.9GB 系统看（8151 MiB 总） |
| 回退路径 | IndexTTS 不可用 → 自动切 edge-tts（既有测试覆盖） |

### 发现并修复的 Bug（本任务内）

**自动情感（use_emo_text）在真实模型上会崩溃**：`IndexTTSBackend.load()` 构造 `IndexTTS2`
时未传 `use_qwen_emo=True`，而 `use_emo_text=True` 依赖 QwenEmotion 文本→情感向量模型，
不加载则抛 `RuntimeError`。参考 CLI（`indextts/infer_v2_5.py` main）即传 `use_qwen_emo=True`。

- 修复：`core/tts_backend.py` 构造参数补 `use_qwen_emo=True`
- 回归测试：`tests/test_tts_backend.py::test_load_passes_use_qwen_emo_for_auto_emotion`

修复前真实推理：`emo_mode="auto"` 报 `TTSBackendError: use_emo_text=True requires QwenEmotion...`；
修复后 auto 与 悲伤 均成功（见上表）。

### 说明

- 模型加载 264s 与 Task 1 的 ~2min 一致（QwenEmotion 额外约 0.8GB 显存）
- 稳态单句合成 2.4s（2-3 秒音频），RTF < 1，优于 CLI 实测
- 参考音频解析链、缺失报错路径已在 Task 6 验证（测试覆盖）

### 待用户 GUI 验证（无法自动化）

以下需真实 GUI 交互（音频输出、任务管理器、人耳听感），自动化仅验证了代码路径不崩：

1. 打开《魔天记》→ 点播放 → 首次 IndexTTS 加载约 2-4 分钟（实测 264s，状态栏文案已同步为"首次约 2-4 分钟"）
2. 情感效果：同一句切换 平静/悲伤/激昂 → 人耳确认明显差异
3. 强度滑条：拉低减弱 / 拉高增强（代码路径有测试，听感需人工）
4. 自动情感：读“快躲起来！”应有紧张语气（合成成功已程序验证，语气需人耳）
5. 引擎切换：播放中切 edge-tts → 立即换引擎继续读（smoke 已跑不崩，听感需人工）
6. 显存：任务管理器确认 IndexTTS 运行时专用 GPU 内存 < 7.5GB（nvidia-smi 实测 ~6.9GB，建议复核）
7. 速度：单句合成 ~2.4s，预取使播放不中断（合成速度已测，播放连贯性需人工）
8. 回退：卸载模型/显存不足 → 自动回退 edge-tts 并提示（代码路径有测试，UI 提示需人工）
9. 回归：edge-tts 模式全部原功能正常（smoke 已跑，真实音频需人工）
