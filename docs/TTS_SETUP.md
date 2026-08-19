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
- 模型加载: ~2 分钟（懒加载一次，应用启动后首次播放时）
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
