from agent.tools.shell import run_command

def test_run_command_success(tmp_codebase):
    result = run_command("echo hello", cwd=tmp_codebase)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]

def test_run_command_failure(tmp_codebase):
    result = run_command("false", cwd=tmp_codebase)
    assert result["exit_code"] != 0

def test_run_command_captures_stderr(tmp_codebase):
    result = run_command("echo error >&2", cwd=tmp_codebase)
    assert "error" in result["stderr"]

def test_run_command_timeout(tmp_codebase):
    result = run_command("sleep 10", cwd=tmp_codebase, timeout=1)
    assert result["exit_code"] != 0
    assert "timeout" in result["stderr"].lower() or "timed out" in result["stderr"].lower()
