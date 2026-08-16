from pathlib import Path

from scripts.emit_ci_summary import main


def test_summary_accepts_the_real_release_cell_shape(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    output = tmp_path / "summary.md"
    source.write_text(
        "# PR-002 Native Packaging Cell Evidence\n\n"
        "- Cell: `cp313-macos-x86_64`\n"
        "- CPython: `3.13.14`\n"
        "- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)\n"
        "- Registry access during install probes: DISABLED (`--no-index` and `PIP_NO_INDEX=1`)\n"
        "- Tampered-hash install rejection: PASS\n"
        "- Incomplete-wheelhouse install rejection: PASS\n"
        "- Built wheel archive policy (`validate_archive()`): PASS\n"
        "- Built sdist archive policy (`validate_archive()`): PASS\n"
        "- Installed validator/schema resource smoke: PASS\n"
        "- Installed offline CLI smoke: PASS\n"
        "- `autopulse.live` absence (metadata and import): PASS\n"
        "- AutoPulse wheel: `autopulse-0.1.0-py3-none-any.whl` (`sha256:" + "a" * 64 + "`)\n"
        "- AutoPulse sdist: `autopulse-0.1.0.tar.gz` (`sha256:" + "b" * 64 + "`)\n"
        "- Wheelhouse manifest SHA-256: `" + "c" * 64 + "`\n\n"
        "## Selected wheels\n\n"
        "- `jsonschema-4.0.0-py3-none-any.whl` (`sha256:" + "d" * 64 + "`)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["emit", "--source", str(source), "--commit", "e" * 40, "--output", str(output)])
    assert main() == 0
    assert "AutoPulse wheel" in output.read_text(encoding="utf-8")
