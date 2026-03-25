import pytest
from agent.tools.shell import run_command_async

@pytest.mark.asyncio
async def test_run_command_async_success():
    result = await run_command_async(["echo", "hello"])
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]

@pytest.mark.asyncio
async def test_run_command_async_failure():
    result = await run_command_async(["false"])
    assert result["exit_code"] != 0

@pytest.mark.asyncio
async def test_run_command_async_cwd(tmp_path):
    result = await run_command_async(["pwd"], cwd=str(tmp_path))
    assert str(tmp_path) in result["stdout"]

@pytest.mark.asyncio
async def test_run_command_async_timeout():
    result = await run_command_async(["sleep", "10"], timeout=1)
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()
