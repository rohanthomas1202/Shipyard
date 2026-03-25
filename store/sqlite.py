"""SQLite implementation of the SessionStore Protocol."""
import json
import aiosqlite
from store.models import Project, Run, Event, EditRecord, Conversation, GitOperation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
    github_repo TEXT, github_pat TEXT, default_model TEXT DEFAULT 'gpt-4o',
    autonomy_mode TEXT DEFAULT 'supervised', test_command TEXT,
    build_command TEXT, lint_command TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id),
    instruction TEXT NOT NULL, status TEXT DEFAULT 'running',
    branch TEXT, context TEXT, plan TEXT, model_usage TEXT,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL, node TEXT, model TEXT, data TEXT,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_replay ON events(run_id, timestamp);

CREATE TABLE IF NOT EXISTS edits (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    file_path TEXT NOT NULL, step INTEGER DEFAULT 0,
    anchor TEXT, old_content TEXT, new_content TEXT,
    status TEXT DEFAULT 'proposed', approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id),
    title TEXT, messages TEXT, model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS git_operations (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL, branch TEXT, commit_sha TEXT,
    pr_url TEXT, pr_number INTEGER, status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class SQLiteSessionStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    # --- Projects ---

    async def create_project(self, project: Project) -> Project:
        await self._db.execute(
            """INSERT INTO projects
               (id, name, path, github_repo, github_pat, default_model,
                autonomy_mode, test_command, build_command, lint_command,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id, project.name, project.path,
                project.github_repo, project.github_pat, project.default_model,
                project.autonomy_mode, project.test_command, project.build_command,
                project.lint_command,
                project.created_at.isoformat(), project.updated_at.isoformat(),
            ),
        )
        await self._db.commit()
        return project

    async def get_project(self, project_id: str) -> Project | None:
        async with self._db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    async def list_projects(self) -> list[Project]:
        async with self._db.execute("SELECT * FROM projects") as cursor:
            rows = await cursor.fetchall()
        return [Project(**dict(row)) for row in rows]

    async def update_project(self, project: Project) -> Project:
        await self._db.execute(
            """UPDATE projects SET name=?, path=?, github_repo=?, github_pat=?,
               default_model=?, autonomy_mode=?, test_command=?, build_command=?,
               lint_command=?, updated_at=? WHERE id=?""",
            (
                project.name, project.path, project.github_repo, project.github_pat,
                project.default_model, project.autonomy_mode, project.test_command,
                project.build_command, project.lint_command,
                project.updated_at.isoformat(), project.id,
            ),
        )
        await self._db.commit()
        return project

    # --- Runs ---

    async def create_run(self, run: Run) -> Run:
        await self._db.execute(
            """INSERT INTO runs
               (id, project_id, instruction, status, branch, context, plan,
                model_usage, total_tokens, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id, run.project_id, run.instruction, run.status, run.branch,
                json.dumps(run.context), json.dumps(run.plan),
                json.dumps(run.model_usage), run.total_tokens,
                run.created_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
            ),
        )
        await self._db.commit()
        return run

    async def get_run(self, run_id: str) -> Run | None:
        async with self._db.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["context"] = json.loads(data["context"]) if data["context"] else {}
        data["plan"] = json.loads(data["plan"]) if data["plan"] else []
        data["model_usage"] = json.loads(data["model_usage"]) if data["model_usage"] else {}
        return Run(**data)

    async def update_run(self, run: Run) -> Run:
        await self._db.execute(
            """UPDATE runs SET status=?, branch=?, context=?, plan=?, model_usage=?,
               total_tokens=?, completed_at=? WHERE id=?""",
            (
                run.status, run.branch,
                json.dumps(run.context), json.dumps(run.plan),
                json.dumps(run.model_usage), run.total_tokens,
                run.completed_at.isoformat() if run.completed_at else None,
                run.id,
            ),
        )
        await self._db.commit()
        return run

    async def list_runs(self, project_id: str) -> list[Run]:
        async with self._db.execute(
            "SELECT * FROM runs WHERE project_id = ?", (project_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["context"] = json.loads(data["context"]) if data["context"] else {}
            data["plan"] = json.loads(data["plan"]) if data["plan"] else []
            data["model_usage"] = json.loads(data["model_usage"]) if data["model_usage"] else {}
            result.append(Run(**data))
        return result

    # --- Events ---

    async def append_event(self, event: Event) -> None:
        await self._db.execute(
            """INSERT INTO events (id, run_id, type, node, model, data, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.run_id, event.type, event.node, event.model,
                json.dumps(event.data), event.timestamp,
            ),
        )
        await self._db.commit()

    async def replay_events(self, run_id: str, after_id: str | None = None) -> list[Event]:
        if after_id is None:
            async with self._db.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY rowid ASC",
                (run_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self._db.execute(
                """SELECT * FROM events WHERE run_id = ?
                   AND rowid > (SELECT rowid FROM events WHERE id = ?)
                   ORDER BY rowid ASC""",
                (run_id, after_id),
            ) as cursor:
                rows = await cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["data"] = json.loads(data["data"]) if data["data"] else {}
            result.append(Event(**data))
        return result

    # --- Edits ---

    async def create_edit(self, edit: EditRecord) -> EditRecord:
        await self._db.execute(
            """INSERT INTO edits
               (id, run_id, file_path, step, anchor, old_content, new_content,
                status, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edit.id, edit.run_id, edit.file_path, edit.step,
                edit.anchor, edit.old_content, edit.new_content, edit.status,
                edit.approved_at.isoformat() if edit.approved_at else None,
            ),
        )
        await self._db.commit()
        return edit

    async def get_edits(self, run_id: str) -> list[EditRecord]:
        async with self._db.execute(
            "SELECT * FROM edits WHERE run_id = ?", (run_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [EditRecord(**dict(row)) for row in rows]

    async def update_edit_status(self, edit_id: str, status: str) -> None:
        await self._db.execute(
            "UPDATE edits SET status = ? WHERE id = ?", (status, edit_id)
        )
        await self._db.commit()

    # --- Conversations ---

    async def create_conversation(self, conv: Conversation) -> Conversation:
        await self._db.execute(
            """INSERT INTO conversations
               (id, project_id, title, messages, model, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conv.id, conv.project_id, conv.title,
                json.dumps(conv.messages), conv.model,
                conv.created_at.isoformat(), conv.updated_at.isoformat(),
            ),
        )
        await self._db.commit()
        return conv

    async def get_conversations(self, project_id: str) -> list[Conversation]:
        async with self._db.execute(
            "SELECT * FROM conversations WHERE project_id = ?", (project_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["messages"] = json.loads(data["messages"]) if data["messages"] else []
            result.append(Conversation(**data))
        return result

    # --- Git Operations ---

    async def log_git_op(self, op: GitOperation) -> None:
        await self._db.execute(
            """INSERT INTO git_operations
               (id, run_id, type, branch, commit_sha, pr_url, pr_number, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                op.id, op.run_id, op.type, op.branch, op.commit_sha,
                op.pr_url, op.pr_number, op.status, op.created_at.isoformat(),
            ),
        )
        await self._db.commit()
