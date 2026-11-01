import runpy
from pathlib import Path

from scripts.llm_localize import parse, score
from wtfl.rankers import is_test_node, rrf

ROOT = Path(__file__).resolve().parents[1]


def test_module_selfchecks():
    for m in ("patch", "repo_index", "anchors"):
        runpy.run_path(str(ROOT / "wtfl" / f"{m}.py"), run_name="__main__")


def test_score_accepts_enclosing_class_and_exact_function():
    gold = {("rich/console.py", "Console.print_json")}
    s = score(["rich/console.py::Console", "x.py::y"], gold, {"rich/console.py"})
    assert s["func_hit1"] and s["file_hit1"]
    s = score(["rich/console.py::print_json"], gold, {"rich/console.py"})
    assert not s["func_hit5"] and s["file_hit1"]


def test_parse_fenced_json():
    assert parse('```json\n["a.py::b"]\n```') == (["a.py::b"], True)


def test_rrf_and_test_filter():
    assert rrf([["a", "b"], ["b", "a"]], weights=[2, 1])[0] == "a"
    assert is_test_node("tests.test_x.test_y") and not is_test_node("fastapi.routing.APIRoute")
