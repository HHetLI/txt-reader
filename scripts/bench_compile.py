"""基准测试：IndexTTS2.5 torch.compile 加速效果对比。

用法（应用 venv）：
    uv run python scripts/bench_compile.py [--compile] [--text "测试文本"]

首次跑 compile 会做 torch.compile 编译（数分钟），之后 inductor 有磁盘缓存。
"""

import argparse
import sys
import time
from pathlib import Path

REPO = Path(r"E:\WorkSpace\index-tts")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODEL_DIR = Path(r"E:\WorkSpace\t2voice\models\indextts")
REF_AUDIO = REPO / "examples" / "voice_01.wav"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true", help="开启 torch.compile")
    parser.add_argument("--text", default="快躲起来！是他要来了！我们得赶紧离开这里。")
    args = parser.parse_args()

    from indextts.infer_v2_5 import IndexTTS2

    print(f"[bench] compile={args.compile} text={args.text}")
    t0 = time.time()
    tts = IndexTTS2(
        cfg_path=str(MODEL_DIR / "config.yaml"),
        model_dir=str(MODEL_DIR),
        use_bf16=True,
        use_cuda_kernel=False,
        use_torch_compile=args.compile,
        use_qwen_emo=True,
    )
    print(f"[bench] 模型加载: {time.time() - t0:.1f}s")

    for round_no in range(3):
        out = Path(f"bench_compile_{'trt' if args.compile else 'pt'}_{round_no}.wav")
        t0 = time.time()
        tts.infer(spk_audio_prompt=str(REF_AUDIO), text=args.text, lang="ZH",
                  output_path=str(out), use_emo_text=True, emo_alpha=0.6)
        dt = time.time() - t0
        # 估算音频时长（wav 字节 / 采样率 / 声道 / 字节宽）
        size = out.stat().st_size - 44
        dur = size / (22050 * 2 * 2)
        print(f"[bench] 第{round_no + 1}句: {dt:.1f}s (音频 {dur:.2f}s, RTF {dt / dur:.2f})")
        out.unlink(missing_ok=True)

    print("[bench] done")


if __name__ == "__main__":
    main()
