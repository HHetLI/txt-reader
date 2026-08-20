# IndexTTS2.5 情感朗读集成 — 设计文档

日期：2026-08-19
状态：已批准（用户确认架构、情感控制、引擎切换策略）

## 1. 目标

在现有小说阅读听书应用（PySide6 + edge-tts）中集成 **IndexTTS2.5 本地情感朗读引擎**：
- 支持有感情的朗读（自动情感 + 手动微调）
- 双引擎可切换：edge-tts（快速/无显存）↔ IndexTTS2.5（情感朗读）
- 运行于用户机器：RTX 5060 Ti 8GB（可用 ~7.5GB）+ i5-14600K + 32GB 内存

## 2. 技术方案

### 2.1 架构（嵌入应用进程）

IndexTTS2.5 模型直接嵌入应用进程（用户选择，明确接受启动加载 30-60s、显存共享 5-7GB 的代价）：

```
TtsEngine (core/tts_engine.py)
 ├── 后端抽象: synthesize_sentence(...)
 │     ├── backend="edge"     → edge-tts（快速/无显存/默认兜底）
 │     └── backend="indextts" → IndexTTS2.5 直接推理（情感朗读）
 ├── 懒加载: IndexTTS2.5 模型首次播放才加载，后台线程加载（30-60s），
 │          加载期间 UI 状态栏显示"加载情感引擎…"，加载完自动开始
 ├── 播放管线不变: 句子队列 → 合成 → QMediaPlayer 播放
 └── 预取深度: IndexTTS 合成慢（~2s/句），预取队列从 3 加深到 8
```

### 2.2 模型配置

- 版本：**IndexTTS-2.5 + BF16**（官方推荐 `use_bf16=True`）
- 模型目录：`models/indextts/`（加入 .gitignore）
- 模型权重来源：HuggingFace `IndexTeam/IndexTTS-2.5`，经 hf-mirror 镜像下载（约 10GB）
- 环境：CUDA 12.8+；PyTorch ≥2.7（Blackwell 架构支持）；从 index-tts 仓库安装 indextts 包
- 显存不足处理：捕获 CUDA OOM → 弹提示"显存不足，请切换 edge-tts 引擎"，自动回退

## 3. 组件划分

| 模块 | 职责 |
|---|---|
| `core/tts_backend.py`（新增） | `IndexTTSBackend`：模型懒加载、`synthesize(text, emo_mode, emo_strength, out_path)`；`EdgeTTSBackend`：包装现有 edge-tts 逻辑；统一接口 `backend.synthesize(...)` |
| `core/tts_engine.py`（改造） | worker 按当前 backend 调用；`set_backend(name)` 即时切换；backend 切换时重启当前会话；IndexTTS 模式句子切分限长 |
| `core/sentence_splitter.py`（微调） | IndexTTS 模式每句 ≤50 字（合成更快、情感更准） |
| `ui/player_bar.py`（改造） | 新增：引擎切换下拉（edge/IndexTTS）、情感模式下拉（自动/平静/悲伤/激昂/温柔/恐惧）、情感强度滑条（0-100%） |
| `ui/main_window.py`（改造） | 引擎/情感参数透传到 TtsEngine；加载状态提示 |
| `pyproject.toml`（改造） | 依赖：indextts、torch 等作为可选依赖组 `[indextts]` |

## 4. 情感控制实现

### 4.1 控制方式（自动为主 + 手动微调）

- **自动情感**（默认）：`use_emo_text=True, emo_alpha=strength`（官方建议 0.6 自然）
- **手动情感**：预设 → 8 维 `emo_vector`（`[高兴,愤怒,悲伤,害怕,厌恶,忧郁,惊讶,平静]`）映射：

| 预设 | emo_vector |
|---|---|
| 平静 | [0,0,0,0,0,0,0,1] |
| 悲伤 | [0,0,0.8,0,0,0,0,0] |
| 激昂 | [0.7,0.2,0,0,0,0,0,0] |
| 温柔 | [0.3,0,0,0,0,0.2,0,0.5] |
| 恐惧 | [0,0,0,0.8,0,0,0,0] |

- **强度滑条**：自动模式映射为 `emo_alpha`（0-1）；手动模式缩放向量分量

### 4.2 音色

- 使用 IndexTTS 自带示例参考音频 `examples/voice_01.wav`（默认音色）
- 预留 `spk_audio_prompt` 参数，未来可支持用户自定义音色（本期不做）

## 5. 交互流程

1. 用户点播放 → `TtsEngine` 检查 backend
2. backend="indextts" 且模型未加载 → 后台线程加载（状态栏"加载情感引擎…"），加载完自动开始合成
3. 句子队列 → `IndexTTSBackend.synthesize(text, emo_mode, emo_strength, path)` → mp3 → QMediaPlayer 播放
4. 播放中切换引擎/情感/强度 → 重启当前会话（从当前句重新合成）
5. 模型加载失败或 CUDA OOM → 弹提示并自动回退 edge-tts

## 6. 错误处理

- **模型加载失败**（缺权重/CUDA 不兼容）：提示并回退 edge-tts
- **CUDA OOM**：提示"显存不足，请切换 edge-tts 引擎"，自动回退
- **合成失败**：沿用现有重试/跳过机制
- **首次加载等待**：状态栏进度提示，不冻结 UI

## 7. 测试策略

- 单元测试（pytest，mock 掉 IndexTTS 真实推理）：
  - backend 接口抽象（Edge/IndexTTS 统一 synthesize 签名）
  - 情感参数映射（emo_mode/strength → emo_vector/emo_alpha）
  - 引擎切换逻辑（set_backend 重启会话、句子长度限制切换）
  - 句子切分限长（IndexTTS 模式 ≤50 字）
- 手动验证（真实加载模型）：
  - 情感效果（同一句不同情感模式差异明显）
  - 显存占用（<7.5GB）
  - 合成速度（~2s/句）
  - 首次加载耗时与 UI 提示

## 8. 范围外（YAGNI）

- 用户自定义音色克隆（预留参数，本期不做）
- 多情感混合/逐句情感标注
- WebUI/服务化部署（用户选择嵌入方案）
