import pytest
from src.utils.message_splitter import (
    split_message, 
    _find_unclosed_tags, 
    _find_split_point,
    _close_tags,
    _open_tags
)

class TestMessageSplitter:
    
    def test_find_unclosed_tags_simple(self):
        text = "<b>Bold text"
        assert _find_unclosed_tags(text) == ['b']
        
    def test_find_unclosed_tags_nested(self):
        text = "<b>Bold <i>Italic"
        assert _find_unclosed_tags(text) == ['b', 'i']
        
    def test_find_unclosed_tags_closed(self):
        text = "<b>Bold</b> <i>Italic</i>"
        assert _find_unclosed_tags(text) == []
        
    def test_find_unclosed_tags_mixed(self):
        text = "<b>Bold <i>Italic</i> continued"
        assert _find_unclosed_tags(text) == ['b']

    def test_close_tags(self):
        tags = ['b', 'i']
        assert _close_tags(tags) == "</i></b>"

    def test_open_tags(self):
        tags = ['b', 'i']
        assert _open_tags(tags) == "<b><i>"

    def test_find_split_point_paragraphs(self):
        text = "Para 1\n\nPara 2\n\nPara 3"
        # max_len covers Para 1 + \n\n
        max_len = len("Para 1\n\n") + 1
        split_point = _find_split_point(text, max_len)
        assert text[:split_point] == "Para 1\n\n"

    def test_find_split_point_newlines(self):
        text = "Line 1\nLine 2\nLine 3"
        max_len = len("Line 1\n") + 1
        split_point = _find_split_point(text, max_len)
        assert text[:split_point] == "Line 1\n"

    def test_find_split_point_spaces(self):
        text = "Word1 Word2 Word3"
        max_len = len("Word1 Word2") + 1
        split_point = _find_split_point(text, max_len)
        assert text[:split_point] == "Word1 Word2 " # Includes space? Logic: last_space + 1
        
    def test_split_message_simple(self):
        text = "Short message"
        parts = split_message(text, max_len=100)
        assert len(parts) == 1
        assert parts[0] == text

    def test_split_message_long_no_tags(self):
        text = "Part 1 " * 10 + "\n\n" + "Part 2 " * 10
        # Force split at \n\n
        # "Part 1 " * 10 is 70 chars. \n\n is 2 chars.
        # Let's set max_len to 80.
        parts = split_message(text, max_len=80, add_numbering=False)
        assert len(parts) >= 2
        assert "Part 1" in parts[0]
        assert "Part 2" in parts[1]

    def test_split_message_with_tags(self):
        # <b>... split ...</b>
        text = "<b>" + "Word " * 20 + "</b>"
        # Length is 3 + 100 + 4 = 107
        # Split at 50
        parts = split_message(text, max_len=50, add_numbering=False)
        
        assert len(parts) > 1
        # Part 1 should start with <b> and end with </b> (added by splitter)
        assert parts[0].startswith("<b>")
        assert parts[0].endswith("</b>")
        
        # Part 2 should start with <b> (added by splitter) and end with </b>
        assert parts[1].startswith("<b>")
        assert parts[1].endswith("</b>")

    def test_split_message_numbering(self):
        text = "A" * 100
        parts = split_message(text, max_len=60, add_numbering=True)
        assert len(parts) == 2
        assert "(1/2)" in parts[0]
        assert "(2/2)" in parts[1]

    def test_split_message_nested_tags(self):
        text = "<b>Bold <i>Italic " + "text " * 10 + "</i></b>"
        # Split inside italic
        parts = split_message(text, max_len=50, add_numbering=False)
        
        # Part 1: <b>Bold <i>Italic ...</i></b>
        assert parts[0].startswith("<b>Bold <i>Italic")
        assert parts[0].endswith("</i></b>")
        
        # Part 2: <b><i>... text </i></b>
        assert parts[1].startswith("<b><i>")
        assert parts[1].endswith("</i></b>")
