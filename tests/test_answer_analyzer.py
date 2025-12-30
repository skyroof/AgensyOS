import pytest
import json
from src.ai.answer_analyzer import robust_json_parse

def test_robust_json_parse_clean():
    json_str = '{"key": "value"}'
    result = robust_json_parse(json_str)
    assert result == {"key": "value"}

def test_robust_json_parse_markdown():
    json_str = '```json\n{"key": "value"}\n```'
    result = robust_json_parse(json_str)
    assert result == {"key": "value"}

def test_robust_json_parse_with_text():
    json_str = 'Here is the JSON: {"key": "value"} thanks'
    result = robust_json_parse(json_str)
    assert result == {"key": "value"}

def test_robust_json_parse_nested():
    json_str = '{"key": {"nested": "value"}}'
    result = robust_json_parse(json_str)
    assert result == {"key": {"nested": "value"}}

def test_robust_json_parse_broken_quotes():
    # This might fail depending on implementation, but let's test if it handles single quotes if implemented
    json_str = "{'key': 'value'}"
    # robust_json_parse has logic to replace single quotes if json.loads fails
    result = robust_json_parse(json_str)
    assert result == {"key": "value"}

def test_robust_json_parse_invalid():
    with pytest.raises(ValueError):
        robust_json_parse("Not a JSON")
