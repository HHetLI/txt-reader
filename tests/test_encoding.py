import pytest
from core.encoding import detect_encoding, read_text_file


def test_detect_utf8():
    data = "你好，世界".encode("utf-8")
    assert detect_encoding(data) == "utf_8" or detect_encoding(data).lower() == "utf-8"


def test_detect_gbk():
    # Sample multiplied x10: charset-normalizer cannot reliably distinguish
    # very short GBK sequences from cp949/big5 (verified 3.5.1 -> 2.1.1).
    data = ("你好，世界" * 10).encode("gbk")
    enc = detect_encoding(data).lower()
    assert "gb" in enc  # gb18030 / gbk / gb2312


def test_read_utf8_plain(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("第一章\n内容", encoding="utf-8")
    assert "第一章" in read_text_file(p)


def test_read_gbk_file(tmp_path):
    p = tmp_path / "b.txt"
    # Same sample multiplied x10: see test_detect_gbk for the short-sample issue.
    p.write_bytes(("第一章\n内容" * 10).encode("gbk"))
    text = read_text_file(p)
    assert "第一章" in text


def test_read_strips_bom(tmp_path):
    p = tmp_path / "c.txt"
    p.write_bytes("\ufeff第一章".encode("utf-8"))
    text = read_text_file(p)
    assert not text.startswith("\ufeff")
    assert text.startswith("第一章")
