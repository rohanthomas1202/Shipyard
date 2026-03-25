"""Deterministic context assembly pipeline.

Fills the model's context window using a ranked priority system:
1. Task context (always included)
2. Working set (highest priority files — current edit target, errors)
3. Reference set (plan files, imports, dependencies)
4. Execution evidence (test failures, lint output)
5. Conversation memory (evicted first)
"""

CHARS_PER_TOKEN = 4


class ContextAssembler:
    def __init__(self, max_tokens: int = 128_000):
        self.max_chars = max_tokens * CHARS_PER_TOKEN
        self._task: str = ""
        self._files: dict[str, tuple[str, str]] = {}  # path -> (content, priority)
        self._errors: list[str] = []

    def add_task(self, instruction: str, step: int = 0, total_steps: int = 0):
        if total_steps > 0:
            self._task = f"[Step {step}/{total_steps}] {instruction}"
        else:
            self._task = instruction

    def add_file(self, path: str, content: str, priority: str = "working"):
        if path not in self._files:
            self._files[path] = (content, priority)

    def add_error(self, error: str):
        self._errors.append(error)

    def build(self) -> str:
        sections: list[str] = []
        budget = self.max_chars

        if self._task:
            task_section = f"## Task\n{self._task}"
            sections.append(task_section)
            budget -= len(task_section)

        if self._errors:
            error_section = "## Errors\n" + "\n---\n".join(self._errors)
            if len(error_section) <= budget:
                sections.append(error_section)
                budget -= len(error_section)

        working_files = {p: c for p, (c, pri) in self._files.items() if pri == "working"}
        for path, content in working_files.items():
            file_section = f"## File: {path}\n```\n{content}\n```"
            if len(file_section) <= budget:
                sections.append(file_section)
                budget -= len(file_section)
            else:
                avail = budget - len(f"## File: {path}\n```\n\n```\n[truncated]")
                if avail > 100:
                    sections.append(f"## File: {path}\n```\n{content[:avail]}\n```\n[truncated]")
                    budget = 0

        ref_files = {p: c for p, (c, pri) in self._files.items() if pri == "reference"}
        for path, content in ref_files.items():
            file_section = f"## File: {path}\n```\n{content}\n```"
            if len(file_section) <= budget:
                sections.append(file_section)
                budget -= len(file_section)

        return "\n\n".join(sections) if sections else ""
