from pathlib import Path

from esp32_manager.utils.code_analyzer import analyze_project


def test_analyze_project_detects_issues(tmp_path: Path) -> None:
    good_file = tmp_path / "good.py"
    good_file.write_text("x = 1\n")

    bad_file = tmp_path / "bad.py"
    bad_file.write_text(
        "import subprocess\n" + f"y = '{'x' * 100}'\n"
    )

    warnings = analyze_project(tmp_path)
    assert any("Forbidden import 'subprocess'" in w for w in warnings)
    assert any("Line too long" in w for w in warnings)
    assert all("good.py" not in w for w in warnings)