"""Phase 0 spike: validate_anchor feasibility test.

Tests whether ast-grep-py can detect if an anchor string aligns with AST
node boundaries. Run against sample anchors to measure structural match rate.

Usage: python spike/validate_anchor_spike.py
"""
import time
from ast_grep_py import SgRoot


def validate_anchor(content: str, anchor: str, language: str) -> dict:
    """Check if anchor aligns with AST node boundaries."""
    try:
        root = SgRoot(content, language)
    except Exception:
        return {"structural_match": False, "unsupported_language": True, "node_type": None}

    start = content.find(anchor)
    if start == -1:
        return {"structural_match": False, "unsupported_language": False, "node_type": None}
    end = start + len(anchor)

    tree_root = root.root()

    def find_covering_nodes(node):
        node_start = node.range().start.index
        node_end = node.range().end.index

        if node_start == start and node_end == end:
            return {"structural_match": True, "unsupported_language": False, "node_type": node.kind()}

        children = list(node.children())
        if not children:
            return None

        for i in range(len(children)):
            child_start = children[i].range().start.index
            if child_start > end:
                break
            if child_start > start:
                continue
            for j in range(i, len(children)):
                seq_end = children[j].range().end.index
                if seq_end == end and child_start == start:
                    return {"structural_match": True, "unsupported_language": False, "node_type": node.kind()}
                if seq_end > end:
                    break

        for child in children:
            child_start = child.range().start.index
            child_end = child.range().end.index
            if child_start <= start and child_end >= end:
                result = find_covering_nodes(child)
                if result:
                    return result
                return {"structural_match": False, "unsupported_language": False, "node_type": child.kind()}

        return {"structural_match": False, "unsupported_language": False, "node_type": tree_root.kind()}

    result = find_covering_nodes(tree_root)
    return result or {"structural_match": False, "unsupported_language": False, "node_type": None}


TYPESCRIPT_FILE = """
import { useState } from 'react';

interface Props {
    name: string;
    count: number;
}

function Counter({ name, count }: Props) {
    const [value, setValue] = useState(count);

    const increment = () => {
        setValue(v => v + 1);
    };

    return (
        <div>
            <h1>{name}</h1>
            <p>Count: {value}</p>
            <button onClick={increment}>+</button>
        </div>
    );
}

export default Counter;
""".strip()

PYTHON_FILE = """
import os
from pathlib import Path

class FileManager:
    def __init__(self, root: str):
        self.root = Path(root)

    def read(self, path: str) -> str:
        full = self.root / path
        return full.read_text()

    def write(self, path: str, content: str) -> None:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

def main():
    fm = FileManager("/tmp")
    fm.write("test.txt", "hello")
    print(fm.read("test.txt"))
""".strip()

STRUCTURAL_ANCHORS = [
    ("typescript", TYPESCRIPT_FILE, "const [value, setValue] = useState(count);"),
    ("typescript", TYPESCRIPT_FILE, """const increment = () => {
        setValue(v => v + 1);
    };"""),
    ("python", PYTHON_FILE, """def read(self, path: str) -> str:
        full = self.root / path
        return full.read_text()"""),
    ("python", PYTHON_FILE, """def __init__(self, root: str):
        self.root = Path(root)"""),
    ("python", PYTHON_FILE, "import os"),
]

NON_STRUCTURAL_ANCHORS = [
    ("typescript", TYPESCRIPT_FILE, """};

    return ("""),
    ("typescript", TYPESCRIPT_FILE, """import { useState } from 'react';

interface Props {"""),
    ("python", PYTHON_FILE, """return full.read_text()

    def write"""),
    ("python", PYTHON_FILE, """fm = FileManager("/tmp")
    fm.write("test.txt", "hello")
    print"""),
]


def generate_large_file(lines: int) -> str:
    parts = []
    for i in range(lines // 4):
        parts.append(f"function func_{i}(x: number): number {{\n    return x + {i};\n}}\n")
    return "\n".join(parts)


def run_spike():
    print("=" * 60)
    print("Phase 0 Spike: validate_anchor feasibility")
    print("=" * 60)

    structural_correct = 0
    structural_total = 0
    non_structural_correct = 0
    non_structural_total = 0
    total = 0
    matches = 0
    timings = []

    print("\n--- Structural anchors (should match) ---")
    for lang, content, anchor in STRUCTURAL_ANCHORS:
        t0 = time.perf_counter_ns()
        result = validate_anchor(content, anchor, lang)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        total += 1
        structural_total += 1
        if result["structural_match"]:
            matches += 1
            structural_correct += 1
        status = "MATCH" if result["structural_match"] else f"NO MATCH ({result['node_type']})"
        print(f"  [{lang}] {status} ({elapsed_ms:.1f}ms) — {anchor[:50]}...")

    print("\n--- Non-structural anchors (should NOT match) ---")
    for lang, content, anchor in NON_STRUCTURAL_ANCHORS:
        t0 = time.perf_counter_ns()
        result = validate_anchor(content, anchor, lang)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        total += 1
        non_structural_total += 1
        if result["structural_match"]:
            matches += 1
        else:
            non_structural_correct += 1
        status = "MATCH" if result["structural_match"] else f"NO MATCH ({result['node_type']})"
        print(f"  [{lang}] {status} ({elapsed_ms:.1f}ms) — {anchor[:50]}...")

    print("\n--- Large file performance ---")
    for size in [100, 1000, 5000]:
        large_content = generate_large_file(size)
        anchor = f"function func_0(x: number): number {{\n    return x + 0;\n}}"
        t0 = time.perf_counter_ns()
        validate_anchor(large_content, anchor, "typescript")
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        print(f"  {size} lines: {elapsed_ms:.1f}ms")

    tp_rate = structural_correct / structural_total * 100 if structural_total else 0
    tn_rate = non_structural_correct / non_structural_total * 100 if non_structural_total else 0
    match_rate = matches / total * 100 if total else 0
    avg_ms = sum(timings) / len(timings) if timings else 0
    max_ms = max(timings) if timings else 0

    print(f"\n--- Results ---")
    print(f"True positive rate (structural detected): {structural_correct}/{structural_total} ({tp_rate:.0f}%)")
    print(f"True negative rate (non-structural detected): {non_structural_correct}/{non_structural_total} ({tn_rate:.0f}%)")
    print(f"Overall match rate: {matches}/{total} ({match_rate:.0f}%)")
    print(f"Average time: {avg_ms:.1f}ms")
    print(f"Max time: {max_ms:.1f}ms")
    print(f"\nGo/no-go: {'GO' if tp_rate >= 40 and max_ms < 10 else 'NEEDS INVESTIGATION'}")
    print(f"  True positive rate >= 40%: {'YES' if tp_rate >= 40 else 'NO'}")
    print(f"  Max time < 10ms: {'YES' if max_ms < 10 else 'NO'}")


if __name__ == "__main__":
    run_spike()
