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
