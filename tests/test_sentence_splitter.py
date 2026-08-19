from core.sentence_splitter import split_sentences


def test_split_chinese_sentences():
    sentences = split_sentences("你好。世界！这是测试？")
    assert sentences == ["你好。", "世界！", "这是测试？"]


def test_keep_delimiter_with_sentence():
    sentences = split_sentences("第一句！第二句？第三句。")
    assert sentences[0] == "第一句！"
    assert sentences[1] == "第二句？"
    assert sentences[2] == "第三句。"


def test_semicolon_splits():
    sentences = split_sentences("甲；乙；丙。")
    assert sentences == ["甲；", "乙；", "丙。"]


def test_empty_input():
    assert split_sentences("") == []


def test_whitespace_only_input():
    assert split_sentences("   \n  ") == []


def test_split_sentences_with_max_len():
    sentences = split_sentences("第一句。第二句。第三句。", max_len=4)
    # 每段 ≤ 4 字
    assert all(len(s) <= 5 for s in sentences)  # 分隔符保留，允许 +1
    assert "".join(sentences) == "第一句。第二句。第三句。"


def test_split_sentences_without_max_len_unchanged():
    assert split_sentences("你好。世界！") == ["你好。", "世界！"]


def test_split_sentences_with_max_len_zero_or_negative():
    # max_len <= 0 不进入死循环：退化为 1 字切分，且不丢字
    text = "这是一个很长的句子。"
    for bad in (0, -1):
        sentences = split_sentences(text, max_len=bad)
        assert all(len(s) >= 1 for s in sentences)
        assert "".join(sentences) == text


def test_split_long_sentence_respects_max_len():
    # 超长段按 max_len 二次切分，不丢字
    sentences = split_sentences(
        "这是一个非常长的句子需要被切分成多个部分以确保长度合适。", max_len=10)
    assert all(len(s) <= 11 for s in sentences)  # 允许尾随分隔符 +1
    assert "".join(sentences) == "这是一个非常长的句子需要被切分成多个部分以确保长度合适。"
