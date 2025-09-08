import json

import pytest

from erniebot_agent.agents import FunctionAgent
from erniebot_agent.agents.schema import EndStep
from erniebot_agent.chat_models import ERNIEBot
from erniebot_agent.memory import WholeMemory
from erniebot_agent.memory.messages import (
    AIMessage,
    AIMessageChunk,
    FunctionMessage,
    HumanMessage,
)
from erniebot_agent.tools.calculator_tool import CalculatorTool

ONE_HIT_PROMPT = "1+4等于几？"
NO_HIT_PROMPT = "深圳今天天气怎么样？"


@pytest.fixture(scope="module")
def llm():
    return ERNIEBot(model="ernie-3.5")


@pytest.fixture(scope="module")
def tool():
    return CalculatorTool()


@pytest.fixture(scope="function")
def memory():
    return WholeMemory()


@pytest.mark.asyncio
async def test_function_agent_run_one_hit(llm, tool, memory):
    agent = FunctionAgent(llm=llm, tools=[tool], memory=memory)
    prompt = ONE_HIT_PROMPT

    run_logs = []
    async for step, msgs in agent.run_stream(prompt):
        run_logs.append((step, msgs))

    assert len(agent.memory.get_messages()) == 2
    assert isinstance(agent.memory.get_messages()[0], HumanMessage)
    assert agent.memory.get_messages()[0].content == prompt
    assert isinstance(run_logs[0][1][0], AIMessageChunk)
    assert run_logs[0][1][0].function_call is not None
    assert run_logs[0][1][0].function_call["name"] == tool.tool_name
    assert isinstance(run_logs[0][1][1], FunctionMessage)
    assert run_logs[0][1][1].name == run_logs[0][1][0].function_call["name"]
    assert json.loads(run_logs[0][1][1].content) == {"formula_result": 5}
    assert isinstance(agent.memory.get_messages()[1], AIMessage)

    tool_steps = [step for step, msgs in run_logs if not isinstance(step, EndStep)]
    assert len(tool_steps) == 1
    assert tool_steps[0].info["tool_name"] == tool.tool_name


@pytest.mark.asyncio
async def test_function_agent_run_no_hit(llm, tool, memory):
    agent = FunctionAgent(llm=llm, tools=[tool], memory=memory)
    prompt = NO_HIT_PROMPT

    run_logs = []
    async for step, msgs in agent.run_stream(prompt):
        run_logs.append((step, msgs))

    assert len(agent.memory.get_messages()) == 2
    assert isinstance(agent.memory.get_messages()[0], HumanMessage)
    assert agent.memory.get_messages()[0].content == prompt
    assert isinstance(run_logs[0][1][0], AIMessage)
    end_step_msg = "".join([msg[0].content for step, msg in run_logs if isinstance(step, EndStep)])
    assert end_step_msg == agent.memory.get_messages()[1].content

    tool_steps = [step for step, msgs in run_logs if not isinstance(step, EndStep)]
    assert len(tool_steps) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", [ONE_HIT_PROMPT, NO_HIT_PROMPT])
async def test_function_agent_run_no_tool(llm, memory, prompt):
    agent = FunctionAgent(llm=llm, tools=[], memory=memory)

    run_logs = []
    async for step, msgs in agent.run_stream(prompt):
        run_logs.append((step, msgs))

    assert len(agent.memory.get_messages()) == 2
    assert isinstance(agent.memory.get_messages()[0], HumanMessage)
    assert agent.memory.get_messages()[0].content == prompt
    assert isinstance(run_logs[0][1][0], AIMessage)
    end_step_msg = "".join([msg[0].content for step, msg in run_logs if isinstance(step, EndStep)])
    assert end_step_msg == agent.memory.get_messages()[1].content

    tool_steps = [step for step, msgs in run_logs if not isinstance(step, EndStep)]
    assert len(tool_steps) == 0
