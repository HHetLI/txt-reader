# t2voice · 小说阅读听书

Windows 桌面小说阅读听书应用：打开 txt 小说自动分章阅读，支持 **edge-tts 快速朗读** 与 **IndexTTS2.5 情感朗读**（双引擎可切换）。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)

## 功能特性

- **单栏阅读界面**：正文占满主窗口，无侧栏干扰，深色护眼主题（适合夜间长时间阅读）
- **自动分章**：打开 txt 自动检测编码（UTF-8/GBK 等），识别「第 X 章 / 序章 / 楔子 / 番外」等标题分章
- **章节导航（菜单栏）**：「章节」菜单提供搜索跳转（`Ctrl+G`）、上一章/下一章；支持上千章的长篇
- **正文搜索（Ctrl+F）**：输入即高亮全部匹配，`Enter`/`Shift+Enter` 或按钮循环跳转，显示匹配计数
- **播放句子跟读**：朗读时正文中的当前句子以暗金色高亮，逐句推进
- **双 TTS 引擎**：
  - `edge-tts`：微软在线语音，5 种中文声线、语速 -10%~+50%，即开即用
  - `IndexTTS2.5`：本地情感合成，支持平静/悲伤/激昂/温柔/恐惧/高兴 6 种预设 + 自动情感 + 强度调节
- **播放控制**：播放/暂停/上一章/下一章/停止，自动连播下一章，记住每本书的阅读进度（章节 + 滚动位置）
- **阅读设置**：字号/行距可调

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Space` | 播放 / 暂停（输入控件聚焦时不生效） |
| `Ctrl+S` | 停止 |
| `Ctrl+O` | 打开文件 |
| `Ctrl+PageUp` / `Ctrl+PageDown` | 上一章 / 下一章 |
| `Ctrl+G` | 跳转到章节… |
| `Ctrl+F` / `F3` | 打开正文搜索 / 下一个匹配 |
| `Esc` | 关闭搜索 |
| `Ctrl+=` / `Ctrl+-` | 字号放大 / 缩小 |
| `Ctrl+0` | 复位字号（16pt） |
| `Ctrl+Shift+=` / `Ctrl+Shift+-` | 行距增大 / 减小 |
| `F11` | 全屏 / 退出全屏 |

## 安装与运行

```bash
# 克隆后
uv venv
uv pip install -e ".[dev]"
uv run python main.py
```

> 听书（edge-tts 模式）需要联网；断网时启动朗读会提示错误。

## IndexTTS2.5 情感引擎（可选）

默认引擎即 IndexTTS2.5；若未安装模型，应用会自动回退到 edge-tts 并提示。

1. 克隆推理仓库：[index-tts/index-tts](https://github.com/index-tts/index-tts)（放置到本仓库根目录或项目外任意位置）
2. 下载模型权重到 `models/indextts/`：ModelScope [`IndexTeam/IndexTTS-2.5`](https://modelscope.cn/models/IndexTeam/IndexTTS-2.5)（约 5.1GB）
3. 安装 torch 等推理依赖到 index-tts 的 Python 环境（应用通过 `sys.path` 导入其 `indextts` 包，见 `core/tts_backend.py`）
4. 参考音频：放置 `examples/voice_01.wav`，或设置环境变量 `INDEXTTS_REF_AUDIO` 指向 wav 文件

首次播放时模型加载约 2-4 分钟（后续会话复用）。模型权重约 10GB，**不入库**（见 `.gitignore`）。

## 测试

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v
```

## 第三方依赖与许可声明（Third-Party Notices）

本项目自身以 MIT 许可证发布（见 [LICENSE](./LICENSE)）。运行时使用了以下第三方项目，感谢他们的工作：

| 组件 | 上游项目 | 许可证 | 用途 |
|---|---|---|---|
| PySide6 | [Qt for Python](https://pypi.org/project/PySide6/) | LGPL-3.0 / GPL-3.0 | GUI 框架 |
| edge-tts | [rany2/edge-tts](https://github.com/rany2/edge-tts) | MIT | 微软 Edge 在线语音合成 |
| charset-normalizer | [Ousret/charset_normalizer](https://github.com/Ousret/charset_normalizer) | MIT | 文本编码检测 |
| IndexTTS2.5 | [index-tts/index-tts](https://github.com/index-tts/index-tts) | [bilibili Model Use License Agreement](https://github.com/index-tts/index-tts/blob/main/LICENSE) | 本地情感 TTS（可选，不随本仓库分发） |

**IndexTTS 说明**：本仓库**不包含** IndexTTS 模型权重与代码，仅通过 `core/tts_backend.py` 在运行时集成外部安装的 index-tts 仓库。使用 IndexTTS 前请阅读并遵守其 [bilibili Model Use License Agreement](https://github.com/index-tts/index-tts/blob/main/LICENSE)（含使用限制、非商业豁免门槛、高风险场景禁用等条款）。

**IndexTTS 辅助模型**（由 index-tts 仓库在本地自动下载，各有独立版权）：

- [facebook/w2v-bert-2.0](https://modelscope.cn/models/facebook/w2v-bert-2.0) — 语音编码
- [iic/speech_campplus_sv_zh-cn_16k-common](https://modelscope.cn/models/iic/speech_campplus_sv_zh-cn_16k-common) — 说话人验证
- [amphion/MaskGCT](https://modelscope.cn/models/amphion/MaskGCT) — 语义编解码
- [nv-community/bigvgan_v2_22khz_80band_256x](https://modelscope.cn/models/nv-community/bigvgan_v2_22khz_80band_256x) — 声码器

## 许可证

[MIT](./LICENSE) © 2026 liyuchen

---

*本项目仅为个人学习与使用目的开发；使用本软件或其中任何模型产生的任何后果由使用者自行承担。*
