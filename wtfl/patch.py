"""Parse unified diffs into gold localization labels (files and old-side line ranges)."""
import re

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch: str) -> list[dict]:
    """Return one dict per touched file: path, is_new, is_deleted, touched old-side lines.

    Touched lines = old-side line numbers of removed lines plus, for pure insertions,
    the old-side line the insertion follows (so an added method maps to its enclosing class).
    """
    files, cur = [], None
    old_ln = 0
    for line in patch.splitlines():
        if line.startswith("--- "):
            src = line[4:].split("\t")[0]
            cur = {"path": None, "src": src, "is_new": src == "/dev/null", "is_deleted": False,
                   "lines": set(), "added": 0, "removed": 0}
            files.append(cur)
            continue
        if line.startswith("+++ ") and cur is not None and cur["path"] is None:
            dst = line[4:].split("\t")[0]
            cur["is_deleted"] = dst == "/dev/null"
            p = cur["src"] if cur["is_deleted"] else dst
            cur["path"] = p[2:] if p.startswith(("a/", "b/")) else p
            continue
        m = HUNK.match(line)
        if m and cur is not None:
            old_ln = int(m.group(1))
            if m.group(2) == "0" and int(m.group(1)) == 0:
                cur["is_new"] = True
            continue
        if cur is None or not line or line.startswith("\\"):
            continue
        if line[0] == "-":
            cur["lines"].add(old_ln)
            cur["removed"] += 1
            old_ln += 1
        elif line[0] == "+":
            cur["lines"].add(max(old_ln - 1, 1))
            cur["added"] += 1
        elif line[0] == " ":
            old_ln += 1
    for f in files:
        f["lines"] = sorted(f["lines"])
        f.pop("src")
    return files


if __name__ == "__main__":
    demo = """--- a/x.py
+++ b/x.py
@@ -3,3 +3,4 @@
 a
-b
+c
+d
 e
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+x
+y
"""
    out = parse_patch(demo)
    assert out[0]["path"] == "x.py" and out[0]["lines"] == [4] and not out[0]["is_new"], out
    assert out[1]["path"] == "new.py" and out[1]["is_new"], out
    print("ok", out)
