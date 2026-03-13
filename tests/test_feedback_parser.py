from run_coach.feedback_parser import parse_description


def test_parse_with_all_fields():
    """RPE + Pain + Commentが全てパースされること。"""
    text = "RPE:7\nPain:右ひざ軽い違和感\nComment:調子良かった"
    result = parse_description(text)
    assert result["rpe"] == 7
    assert result["pain"] == "右ひざ軽い違和感"
    assert result["comment"] == "調子良かった"


def test_parse_with_fullwidth_colon():
    """全角コロンでもパースできること。"""
    text = "RPE：8\nPain：なし\nComment：いい感じ"
    result = parse_description(text)
    assert result["rpe"] == 8
    assert result["pain"] == "なし"
    assert result["comment"] == "いい感じ"


def test_parse_case_insensitive():
    """大文字小文字を問わずパースできること。"""
    text = "rpe:6\npain:なし\ncomment:楽だった"
    result = parse_description(text)
    assert result["rpe"] == 6
    assert result["pain"] == "なし"
    assert result["comment"] == "楽だった"


def test_parse_comment_only():
    """RPE行なし、自由文のみの場合、全文をcommentとして扱うこと。"""
    text = "今日は気持ちよく走れた"
    result = parse_description(text)
    assert result["rpe"] is None
    assert result["pain"] is None
    assert result["comment"] == "今日は気持ちよく走れた"


def test_parse_empty():
    """空文字列で全てNoneを返すこと。"""
    result = parse_description("")
    assert result["rpe"] is None
    assert result["pain"] is None
    assert result["comment"] is None


def test_parse_none():
    """Noneで全てNoneを返すこと。"""
    result = parse_description(None)
    assert result["rpe"] is None
    assert result["pain"] is None
    assert result["comment"] is None


def test_parse_rpe_fullwidth_digits():
    """全角数字のRPEがパースされること。"""
    result = parse_description("RPE:７\nComment:テスト")
    assert result["rpe"] == 7
    assert result["comment"] == "テスト"


def test_parse_real_description():
    """実際のGarmin descriptionに近い形式がパースされること。"""
    text = (
        "RPE: 5\n"
        "Pain: なし\n"
        "Comment: 病み上がりから体力が回復しきっていなせいか、体が重かった。辛くはなかった。"
    )
    result = parse_description(text)
    assert result["rpe"] == 5
    assert result["pain"] == "なし"
    assert (
        result["comment"]
        == "病み上がりから体力が回復しきっていなせいか、体が重かった。辛くはなかった。"
    )


def test_parse_rpe_out_of_range():
    """RPEが1-10の範囲外の場合はNoneになること。"""
    result = parse_description("RPE:15\nComment:テスト")
    assert result["rpe"] is None
    assert result["comment"] == "テスト"


def test_parse_japanese_labels():
    """日本語ラベル「痛み」「コメント」でパースできること。"""
    text = "RPE: 7\n痛み: 右ひざ\nコメント: 調子良かった"
    result = parse_description(text)
    assert result["rpe"] == 7
    assert result["pain"] == "右ひざ"
    assert result["comment"] == "調子良かった"


def test_parse_japanese_labels_fullwidth_colon():
    """日本語ラベル＋全角コロンでパースできること。"""
    text = "RPE：8\n痛み：なし\nコメント：いい感じ"
    result = parse_description(text)
    assert result["rpe"] == 8
    assert result["pain"] == "なし"
    assert result["comment"] == "いい感じ"
