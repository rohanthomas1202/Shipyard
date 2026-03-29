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
