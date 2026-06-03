"""S2.1：ReAct 步骤解析（Thought / Action / Final Answer）。"""

from __future__ import annotations

from app.core.agent.react_agent import _parse_react_step


def test_parse_final_answer():
    text = "Thought: 够了\nFinal Answer: 答案是 42"
    parsed = _parse_react_step(text)
    assert parsed.get("done") is True
    assert parsed.get("final_answer") == "答案是 42"


def test_parse_action_and_json_input():
    text = 'Thought: 需要计算\nAction: calculator\nAction Input: {"expression": "1+2"}'
    parsed = _parse_react_step(text)
    assert parsed.get("action") == "calculator"
    assert parsed.get("action_input") == {"expression": "1+2"}


def test_parse_invalid_json_sets_error():
    text = "Thought: x\nAction: search\nAction Input: {not json}"
    parsed = _parse_react_step(text)
    assert parsed.get("action") == "search"
    assert parsed.get("parse_error") or parsed.get("action_input") == {}
