"""Unit tests for ContractStore — file-based contract CRUD."""
import pytest
from agent.orchestrator.contracts import ContractStore


class TestContractStore:
    """Tests for the ContractStore file-based contract reader/writer."""

    def test_write_and_read_sql(self, tmp_path):
        store = ContractStore(str(tmp_path))
        content = "CREATE TABLE users (id INTEGER PRIMARY KEY);"
        store.write_contract("db/schema.sql", content)
        assert store.read_contract("db/schema.sql") == content

    def test_write_and_read_yaml(self, tmp_path):
        store = ContractStore(str(tmp_path))
        content = "openapi: '3.0'\ninfo:\n  title: Test API"
        store.write_contract("api/openapi.yaml", content)
        assert store.read_contract("api/openapi.yaml") == content

    def test_write_and_read_ts(self, tmp_path):
        store = ContractStore(str(tmp_path))
        content = "export interface User { id: number; name: string; }"
        store.write_contract("types/shared.ts", content)
        assert store.read_contract("types/shared.ts") == content

    def test_write_and_read_json(self, tmp_path):
        store = ContractStore(str(tmp_path))
        content = '{"color": "red"}'
        store.write_contract("design/tokens.json", content)
        assert store.read_contract("design/tokens.json") == content

    def test_read_missing(self, tmp_path):
        store = ContractStore(str(tmp_path))
        assert store.read_contract("nonexistent.sql") is None

    def test_list_empty(self, tmp_path):
        store = ContractStore(str(tmp_path))
        assert store.list_contracts() == []

    def test_list_multiple(self, tmp_path):
        store = ContractStore(str(tmp_path))
        store.write_contract("a.sql", "sql")
        store.write_contract("b.yaml", "yaml")
        store.write_contract("c.ts", "ts")
        result = sorted(store.list_contracts())
        assert result == ["a.sql", "b.yaml", "c.ts"]

    def test_write_creates_subdirs(self, tmp_path):
        store = ContractStore(str(tmp_path))
        store.write_contract("deep/nested/file.sql", "CREATE TABLE t;")
        assert store.read_contract("deep/nested/file.sql") == "CREATE TABLE t;"

    def test_contract_types(self):
        assert ".sql" in ContractStore.CONTRACT_TYPES
        assert ".yaml" in ContractStore.CONTRACT_TYPES
        assert ".ts" in ContractStore.CONTRACT_TYPES
        assert ".json" in ContractStore.CONTRACT_TYPES

    def test_contract_exists(self, tmp_path):
        store = ContractStore(str(tmp_path))
        assert store.contract_exists("missing.sql") is False
        store.write_contract("found.sql", "content")
        assert store.contract_exists("found.sql") is True


# --- Phase 14: Backward compatibility tests ---

def test_check_compatibility_new_contract(tmp_path):
    store = ContractStore(str(tmp_path))
    report = store.check_compatibility("schema.sql", "CREATE TABLE users (id INTEGER);")
    assert report["compatible"] is True
    assert report["breaking"] == []


def test_check_compatibility_additive_sql(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("schema.sql", "CREATE TABLE users (id INTEGER);")
    report = store.check_compatibility("schema.sql", "CREATE TABLE users (id INTEGER);\nALTER TABLE users ADD COLUMN name TEXT;")
    assert report["compatible"] is True


def test_check_compatibility_breaking_sql_removal(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("schema.sql", "CREATE TABLE users (\n  id INTEGER,\n  name TEXT\n);")
    report = store.check_compatibility("schema.sql", "CREATE TABLE users (\n  id INTEGER\n);")
    assert report["compatible"] is False
    assert any("name TEXT" in b for b in report["breaking"])


def test_check_compatibility_breaking_yaml_removal(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("api.yaml", "paths:\n  /users:\n    get:\n  /health:\n    get:")
    report = store.check_compatibility("api.yaml", "paths:\n  /users:\n    get:")
    assert report["compatible"] is False
    assert any("YAML" in b for b in report["breaking"])


def test_check_compatibility_breaking_ts_removal(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("types.ts", "export interface User { id: string }\nexport interface Project { id: string }")
    report = store.check_compatibility("types.ts", "export interface User { id: string }")
    assert report["compatible"] is False
    assert any("TypeScript" in b for b in report["breaking"])


def test_check_compatibility_breaking_json_removal(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("config.json", '{\n  "key1": "val1",\n  "key2": "val2"\n}')
    report = store.check_compatibility("config.json", '{\n  "key1": "val1"\n}')
    assert report["compatible"] is False
    assert any("JSON" in b for b in report["breaking"])


def test_check_compatibility_whitespace_only(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("schema.sql", "SELECT 1;")
    report = store.check_compatibility("schema.sql", "SELECT 1;\n")
    assert report["compatible"] is True


def test_generate_migration_doc():
    from agent.orchestrator.migration import generate_migration_doc
    doc = generate_migration_doc("schema.sql", "/path/schema.sql", ["Removed column: name TEXT"])
    assert "## What Broke" in doc
    assert "## Why" in doc
    assert "## Migration Steps" in doc
    assert "## Verification" in doc
    assert "Removed column: name TEXT" in doc


def test_write_contract_safe_compatible(tmp_path):
    store = ContractStore(str(tmp_path))
    path, report = store.write_contract_safe("schema.sql", "CREATE TABLE t (id INTEGER);")
    assert report["compatible"] is True
    assert not store.contract_exists("schema.migration.md")


def test_write_contract_safe_breaking(tmp_path):
    store = ContractStore(str(tmp_path))
    store.write_contract("schema.sql", "CREATE TABLE t (\n  id INTEGER,\n  name TEXT\n);")
    path, report = store.write_contract_safe("schema.sql", "CREATE TABLE t (\n  id INTEGER\n);")
    assert report["compatible"] is False
    assert store.contract_exists("schema.migration.md")
    migration = store.read_contract("schema.migration.md")
    assert "## What Broke" in migration
