from agent.tools.search import search_content

def test_search_finds_matching_lines(tmp_codebase):
    result = search_content("interface", tmp_codebase)
    assert "sample.ts" in result
    assert "user.ts" in result

def test_search_returns_line_numbers(tmp_codebase):
    result = search_content("email", tmp_codebase)
    assert "user.ts" in result
    assert "email" in result

def test_search_no_matches(tmp_codebase):
    result = search_content("zzzznotfound", tmp_codebase)
    assert "no matches" in result.lower() or result.strip() == ""
