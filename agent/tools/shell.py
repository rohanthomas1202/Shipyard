import asyncio
import subprocess

async def run_command_async(argv: list[str], cwd: str = ".", timeout: int = 60) -> dict:
    """Non-blocking subprocess execution using argv list form (no shell=True)."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "exit_code": proc.returncode}
    except asyncio.TimeoutError:
        proc.kill()
        return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}


def run_command(command: str, cwd: str = ".", timeout: int = 60) -> dict:
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Command timed out after {timeout}s", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}
