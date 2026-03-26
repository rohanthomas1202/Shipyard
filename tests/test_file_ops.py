import os
from agent.tools.file_ops import read_file, edit_file, create_file, delete_file, list_files
from agent.tools.file_ops import content_hash, _normalize_whitespace, _find_fuzzy_match, _detect_indent, _adjust_replacement_indent

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

# ---------------------------------------------------------------------------
# New tests: fuzzy matching chain
# ---------------------------------------------------------------------------

def test_edit_exact_match(tmp_codebase):
    """edit_file with exact anchor returns match_type 'exact'."""
    path = os.path.join(tmp_codebase, "sample.ts")
    anchor = '  id: string;\n  title: string;'
    replacement = '  id: number;\n  title: string;'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    assert result["match_type"] == "exact"

def test_edit_whitespace_normalized(tmp_codebase):
    """edit_file with anchor that has extra spaces returns match_type 'whitespace_normalized'."""
    path = os.path.join(tmp_codebase, "sample.ts")
    # The file has '  id: string;' but we'll provide anchor with trailing spaces
    anchor = '  id: string;  \n  title: string;  '
    replacement = '  id: number;\n  title: string;'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    assert result["match_type"] == "whitespace_normalized"

def test_edit_fuzzy_match(tmp_codebase):
    """edit_file with anchor that has a few char differences returns match_type 'fuzzy'."""
    path = os.path.join(tmp_codebase, "sample.ts")
    # Slightly different anchor (changed "string" to "strng" in description line)
    anchor = '  description: strng;\n  status: "open" | "closed";'
    replacement = '  description: string;\n  priority: number;\n  status: "open" | "closed";'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    assert result["match_type"] == "fuzzy"
    assert result["fuzzy_score"] >= 0.85

def test_edit_fuzzy_below_threshold(tmp_codebase):
    """edit_file with very different anchor returns failure with diagnostics."""
    path = os.path.join(tmp_codebase, "sample.ts")
    anchor = 'completely different content that wont match anything useful at all xyz'
    result = edit_file(path, anchor, "replacement")
    assert result["success"] is False
    assert "best_score" in result
    assert isinstance(result["best_score"], float)
    assert "anchor_preview" in result
    assert "best_match_preview" in result

def test_edit_not_unique(tmp_codebase):
    """edit_file with anchor matching 2+ locations returns not-unique error."""
    path = os.path.join(tmp_codebase, "sample.ts")
    # "string;" appears multiple times in the file
    result = edit_file(path, "string;", "number;")
    assert result["success"] is False
    assert "not unique" in result["error"].lower()

# ---------------------------------------------------------------------------
# New tests: helper functions
# ---------------------------------------------------------------------------

def test_normalize_whitespace():
    """_normalize_whitespace collapses multiple whitespace to single space."""
    assert _normalize_whitespace("  foo   bar  ") == "foo bar"
    assert _normalize_whitespace("hello") == "hello"
    assert _normalize_whitespace("\t  a  \t  b  ") == "a b"

def test_find_fuzzy_match_above_threshold():
    """_find_fuzzy_match returns (matched_text, score) when above threshold."""
    content = "line 1\nfoo bar baz\nline 3\n"
    anchor = "foo bar bax"  # close to "foo bar baz"
    matched, score = _find_fuzzy_match(content, anchor)
    assert matched is not None
    assert score >= 0.85

def test_find_fuzzy_match_below_threshold():
    """_find_fuzzy_match returns (None, score) when below threshold."""
    content = "line 1\nfoo bar baz\nline 3\n"
    anchor = "completely different text with no similarity"
    matched, score = _find_fuzzy_match(content, anchor)
    assert matched is None
    assert score < 0.85

def test_detect_indent_spaces():
    """_detect_indent detects space-based indentation."""
    char, count = _detect_indent("    foo")
    assert char == " "
    assert count == 4

def test_detect_indent_tabs():
    """_detect_indent detects tab-based indentation."""
    char, count = _detect_indent("\t\tfoo")
    assert char == "\t"
    assert count == 2

def test_adjust_replacement_indent():
    """Replacement with 0 indent applied at 4-space context gets 4-space base indent."""
    content = "class Foo:\n    def bar(self):\n        pass\n"
    anchor_text = "    def bar(self):\n        pass"
    # Replacement has no leading indent
    replacement = "def baz(self):\n    return 1"
    result = _adjust_replacement_indent(anchor_text, replacement, content)
    lines = result.split("\n")
    assert lines[0] == "    def baz(self):"
    assert lines[1] == "        return 1"

def test_indentation_preserved_in_edit(tmp_codebase):
    """edit_file where replacement has wrong indentation still produces correctly indented output."""
    # Create a file with known indentation
    path = os.path.join(tmp_codebase, "indent_test.py")
    with open(path, "w") as f:
        f.write("class MyClass:\n    def old_method(self):\n        return 1\n")
    anchor = "    def old_method(self):\n        return 1"
    # Replacement deliberately has no leading indent
    replacement = "def new_method(self):\n    return 2"
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    content = open(path).read()
    assert "    def new_method(self):" in content
    assert "        return 2" in content

# ---------------------------------------------------------------------------
# New tests: content_hash
# ---------------------------------------------------------------------------

def test_content_hash_deterministic():
    """content_hash produces same result for same input, different for different input."""
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("world")

def test_content_hash_returns_16_hex():
    """content_hash returns a 16-character hex string."""
    result = content_hash("test")
    assert len(result) == 16
    assert all(c in "0123456789abcdef" for c in result)

# ---------------------------------------------------------------------------
# Existing test backward compatibility
# ---------------------------------------------------------------------------

def test_existing_exact_match_still_works(tmp_codebase):
    """Existing test_edit_file_replaces_anchor behavior is preserved."""
    path = os.path.join(tmp_codebase, "sample.ts")
    anchor = '  description: string;\n  status: "open" | "closed";'
    replacement = '  description: string;\n  due_date: string;\n  status: "open" | "closed";'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    content = open(path).read()
    assert "due_date: string;" in content
    assert result["snapshot"] is not None

def test_existing_anchor_not_found_still_works(tmp_codebase):
    """Existing not-found behavior is preserved, now with enhanced error info."""
    path = os.path.join(tmp_codebase, "sample.ts")
    result = edit_file(path, "this anchor does not exist at all in this file anywhere", "replacement")
    assert result["success"] is False
    assert "not found" in result["error"].lower()

def test_existing_anchor_not_unique_still_works(tmp_codebase):
    """Existing not-unique behavior is preserved."""
    path = os.path.join(tmp_codebase, "sample.ts")
    result = edit_file(path, "string;", "number;")
    assert result["success"] is False
    assert "not unique" in result["error"].lower() or "multiple" in result["error"].lower()
