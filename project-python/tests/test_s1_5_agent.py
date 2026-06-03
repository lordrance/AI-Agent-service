"""S1.5 验证：ReAct Agent 端到端调用内置工具（假 LLM 驱动，确定性）。"""

from __future__ import annotations

import pytest

from app.core.agent.react_agent import ReActAgent
from app.core.tools.builtin import CalculatorTool
from app.core.tools.registry import ToolRegistry


class _ScriptedLLM:
    """按调用次数返回脚本化的 ReAct 步骤。"""

    def __init__(self) -> None:
        self._calls = 0

    async def acomplete(self, messages, **kwargs):
        self._calls += 1
        if self._calls == 1:
            return 'Thought: 需要计算 2+3\nAction: calculator\nAction Input: {"expression": "2+3"}'
        return "Thought: 已得到结果\nFinal Answer: 计算结果是 5"


@pytest.mark.asyncio
async def test_react_agent_invokes_calculator():
    reg = ToolRegistry()
    reg.register(CalculatorTool())

    agent = ReActAgent(llm=_ScriptedLLM(), tools=reg, memory=None, max_steps=5)
    result = await agent.run("帮我算 2+3", {"tool_names": reg.list_tool_names()})

    assert result.success is True
    assert "5" in result.final_answer
    # 至少经历一次工具调用（observation 含计算结果 5.0）
    observations = [s.get("observation", "") for s in result.steps]
    assert any("5" in o for o in observations)


@pytest.mark.asyncio
async def test_react_agent_respects_max_steps():
    """模型始终不给 Final Answer 时，应在 max_steps 后失败返回（防失控循环）。"""

    class _LoopLLM:
        async def acomplete(self, messages, **kwargs):
            return 'Thought: 再算一次\nAction: calculator\nAction Input: {"expression": "1+1"}'

    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = ReActAgent(llm=_LoopLLM(), tools=reg, memory=None, max_steps=3)
    result = await agent.run("循环", {"tool_names": reg.list_tool_names()})

    assert result.success is False
    assert "最大步数" in (result.error or "")
    assert len(result.steps) == 3
