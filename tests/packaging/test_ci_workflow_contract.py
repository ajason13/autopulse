from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-docs.yml").read_text(encoding="utf-8")


APPROVED_V7_PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1", 3),
    "actions/setup-python": ("5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0", 1),
    "actions/setup-node": ("820762786026740c76f36085b0efc47a31fe5020", "v7.0.0", 2),
}


def _assert_approved_v7_pins() -> None:
    workflows = CI + "\n" + DEPLOY
    for action, (sha, version, expected_count) in APPROVED_V7_PINS.items():
        all_occurrences = re.findall(rf"uses:\s*{re.escape(action)}@[^\s#]+", workflows)
        approved_occurrences = re.findall(
            rf"uses:\s*{re.escape(action)}@{sha} # {re.escape(version)}", workflows
        )
        assert len(all_occurrences) == expected_count
        assert len(approved_occurrences) == expected_count


def test_ci_release_gate_contract_is_fail_closed() -> None:
    assert "pull_request_target" not in CI and "workflow_run" not in CI
    assert "contents: read" in CI and "*-latest" not in CI
    assert len(re.findall(r"runner: (?:ubuntu-24.04|macos-15-intel|macos-15|windows-2025)", CI)) == 8
    assert "shell: bash" in CI and "shell: pwsh" in CI
    assert "$ErrorActionPreference = 'Stop'" in CI
    assert "$PSNativeCommandUseErrorActionPreference = $true" in CI
    assert "shell: cmd" not in CI and "shell: bat" not in CI
    assert "verify_release_cell.py" in CI and "emit_ci_summary.py" in CI
    _assert_approved_v7_pins()
    setup_python_step = re.search(
        r"- uses: actions/setup-python@[^\n]+\n(?P<body>.*?)(?=\n\s*-\s|\Z)",
        CI,
        re.DOTALL,
    )
    assert setup_python_step is not None
    assert "pip-install:" not in setup_python_step.group("body")
    assert "not Windows 11 desktop validation" in CI


def test_docs_workflows_pin_actions_and_verify_committed_base_path() -> None:
    assert "npm run build" in CI and "--base" not in CI and "pages: write" not in CI
    assert "configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d" in DEPLOY
    assert "pages: write" in DEPLOY and "id-token: write" in DEPLOY
    assert '${{ steps.pages.outputs.origin }}' in DEPLOY
    assert '${{ steps.pages.outputs.base_path }}' in DEPLOY
    assert all(
        re.fullmatch(r"[0-9a-f]{40}", sha)
        for sha in re.findall(r"uses:\s*[^@\s]+@([^\s#]+)", DEPLOY)
    )
