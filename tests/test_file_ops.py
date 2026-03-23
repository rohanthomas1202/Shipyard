import os
from agent.tools.file_ops import read_file, edit_file, create_file, delete_file, list_files

def test_read_file_returns_content_with_line_numbers(tmp_codebase):
    result = read_file(os.path.join(tmp_codebase, "sample.ts"))
    assert "1: export interface Issue {" in result
    assert "2:   id: string;" in result

def test_read_file_nonexistent_returns_error(tmp_codebase):
    result = read_file(os.path.join(tmp_codebase, "nope.ts"))
    assert "Error" in result or "not found" in result.lower()

def test_edit_file_replaces_anchor(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    anchor = '  description: string;\n  status: "open" | "closed";'
    replacement = '  description: string;\n  due_date: string;\n  status: "open" | "closed";'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    content = open(path).read()
    assert "due_date: string;" in content
    assert result["snapshot"] is not None

def test_edit_file_anchor_not_found(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = edit_file(path, "this anchor does not exist", "replacement")
    assert result["success"] is False
    assert "not found" in result["error"].lower()

def test_edit_file_anchor_not_unique(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = edit_file(path, "string;", "number;")
    assert result["success"] is False
    assert "not unique" in result["error"].lower() or "multiple" in result["error"].lower()

def test_create_file(tmp_codebase):
    path = os.path.join(tmp_codebase, "new_file.ts")
    result = create_file(path, "export const x = 1;\n")
    assert result["success"] is True
    assert os.path.exists(path)
    assert open(path).read() == "export const x = 1;\n"

def test_create_file_already_exists(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = create_file(path, "overwrite")
    assert result["success"] is False
    assert "exists" in result["error"].lower()

def test_delete_file(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = delete_file(path)
    assert result["success"] is True
    assert not os.path.exists(path)

def test_list_files(tmp_codebase):
    result = list_files(tmp_codebase, "*.ts")
    assert "sample.ts" in result
    assert "user.ts" in result

def test_list_files_with_pattern(tmp_codebase):
    result = list_files(tmp_codebase, "*.json")
    assert "config.json" in result
    assert "sample.ts" not in result
