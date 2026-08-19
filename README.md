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
