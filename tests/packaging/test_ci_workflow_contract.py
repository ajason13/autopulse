from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-docs.yml").read_text(encoding="utf-8")


def test_ci_release_gate_contract_is_fail_closed() -> None:
    assert "pull_request_target" not in CI and "workflow_run" not in CI
    assert "contents: read" in CI and "*-latest" not in CI
    assert len(re.findall(r"runner: (?:ubuntu-24.04|macos-15-intel|macos-15|windows-2025)", CI)) == 8
    assert "shell: pwsh" in CI and "shell: cmd" not in CI and "shell: bat" not in CI
    assert "verify_release_cell.py" in CI and "emit_ci_summary.py" in CI
    assert re.search(r"actions/checkout@[0-9a-f]{40} # v6", CI)
    assert "not Windows 11 desktop validation" in CI


def test_docs_workflows_pin_actions_and_verify_committed_base_path() -> None:
    assert "npm run build" in CI and "--base" not in CI and "pages: write" not in CI
    assert "configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d" in DEPLOY
    assert not re.search(r"uses: [^@]+@v\d", DEPLOY)
