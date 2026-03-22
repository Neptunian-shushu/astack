"""CLI smoke tests — verify each subcommand exits 0."""

import subprocess
import sys


def _run(args):
    result = subprocess.run(
        [sys.executable, "-m", "astack.cli"] + args,
        capture_output=True, text=True, timeout=30,
    )
    return result


def test_cli_generate():
    r = _run(["generate", "--goal", "volume alpha", "--max-ideas", "2"])
    assert r.returncode == 0
    assert "alpha_idea_1" in r.stdout


def test_cli_formalize():
    r = _run(["formalize", "--goal", "volume alpha", "--max-ideas", "2"])
    assert r.returncode == 0


def test_cli_evaluate():
    r = _run(["evaluate", "--goal", "volume alpha", "--max-ideas", "2"])
    assert r.returncode == 0
    assert "quality=" in r.stdout


def test_cli_run(tmp_path):
    r = _run(["run", "--goal", "volume alpha", "--max-ideas", "2", "--output-dir", str(tmp_path)])
    assert r.returncode == 0
    assert "Completed" in r.stdout


def test_cli_generate_with_output(tmp_path):
    out = tmp_path / "ideas.json"
    r = _run(["generate", "--goal", "test", "--max-ideas", "2", "--output", str(out)])
    assert r.returncode == 0
    assert out.exists()


def test_cli_pipeline_artifacts(tmp_path):
    """Test full artifact pipeline: generate -> formalize -> evaluate -> rank."""
    ideas = tmp_path / "ideas.json"
    specs = tmp_path / "specs.json"
    reports = tmp_path / "reports.json"
    ranked = tmp_path / "ranked.json"

    r = _run(["generate", "--goal", "test", "--max-ideas", "2", "-o", str(ideas)])
    assert r.returncode == 0

    r = _run(["formalize", "-i", str(ideas), "-o", str(specs)])
    assert r.returncode == 0

    r = _run(["evaluate", "-i", str(specs), "-o", str(reports)])
    assert r.returncode == 0

    r = _run(["rank", "-i", str(reports), "-o", str(ranked)])
    assert r.returncode == 0
    assert ranked.exists()
