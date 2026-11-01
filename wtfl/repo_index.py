"""Map graph nodes (dotted symbol paths, no file info) to files and line spans at a commit."""
import ast
import json
import subprocess
from functools import lru_cache
from pathlib import Path


def git(repo_dir, *args) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True, text=True,
                          errors="replace", check=True).stdout


def read_blobs(repo_dir, commit: str, files: list[str]):
    """Yield (path, text) for files at commit through one `git cat-file --batch` process."""
    p = subprocess.Popen(["git", "-C", str(repo_dir), "cat-file", "--batch"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for f in files:
        p.stdin.write(f"{commit}:{f}\n".encode())
        p.stdin.flush()
        header = p.stdout.readline().split()
        if len(header) < 3 or header[1] != b"blob":
            continue
        data = p.stdout.read(int(header[2]))
        p.stdout.read(1)
        yield f, data.decode("utf-8", "replace")
    p.stdin.close()
    p.wait()


def defs_in_source(src: str) -> list[tuple[str, int, int]]:
    """(qualname, start, end) for every class/function, nested ones included."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return []
    out = []

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}.{ch.name}" if prefix else ch.name
                start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                out.append((q, start, ch.end_lineno))
                walk(ch, q)
            elif not isinstance(ch, (ast.Lambda,)):
                walk(ch, prefix)
    walk(tree, "")
    return out


def module_candidates(path: str) -> list[str]:
    """Dotted module names for a file, longest first (the graph strips some leading dirs)."""
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return [".".join(parts[i:]) for i in range(len(parts)) if parts[i:]]


@lru_cache(maxsize=8)
def load_graph(path: str) -> dict:
    return json.loads(Path(path).read_text())


def build_index(repo_dir, commit: str, node_names: set[str]) -> dict:
    """Return {'node2loc': {node: (file, start, end)}, 'file_defs': {file: [(node|None, q, s, e)]}}."""
    files = [f for f in git(repo_dir, "ls-tree", "-r", "--name-only", commit).splitlines() if f.endswith(".py")]
    node2loc, file_defs = {}, {}
    for f, src in read_blobs(repo_dir, commit, files):
        defs = defs_in_source(src)
        mods = module_candidates(f)
        # choose the module prefix under which most of this file's defs exist in the graph
        best, best_hits = None, 0
        for m in mods:
            hits = sum(f"{m}.{q}" in node_names for q, _, _ in defs)
            if hits > best_hits:
                best, best_hits = m, hits
        rows = []
        for q, s, e in defs:
            n = f"{best}.{q}" if best else None
            if n not in node_names:
                n = None
            elif n not in node2loc:
                node2loc[n] = (f, s, e)
            rows.append((n, q, s, e))
        file_defs[f] = rows
    return {"node2loc": node2loc, "file_defs": file_defs, "py_files": files}


def enclosing(rows, line: int):
    """Innermost def containing line, or None (module-level code)."""
    best = None
    for n, q, s, e in rows:
        if s <= line <= e and (best is None or e - s < best[3] - best[2]):
            best = (n, q, s, e)
    return best


if __name__ == "__main__":
    src = "class A:\n    @d\n    def f(self):\n        return 1\n\ndef g():\n    pass\n"
    d = defs_in_source(src)
    assert ("A.f", 2, 4) in d and ("g", 6, 7) in d, d
    assert enclosing([(None, q, s, e) for q, s, e in d], 4)[1] == "A.f"
    assert module_candidates("src/pkg/__init__.py") == ["src.pkg", "pkg"]
    print("ok")
