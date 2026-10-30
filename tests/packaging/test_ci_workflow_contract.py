from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-docs.yml").read_text(encoding="utf-8")


APPROVED_V7_PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1", 3),
    "actions/setup-python": ("6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "v7.1.0", 1),
    "actions/setup-node": ("949feb2413d6458794dcd2491c4babbbce0c15c1", "v7.1.0", 2),
}

DOCS_AUDIT_COMMAND = "npm audit --omit=dev --audit-level=high"


def _extract_job(workflow: str, job_name: str) -> str:
    job = re.search(
        rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    assert job is not None
    return job.group("body")


def _extract_step_blocks(job: str) -> list[str]:
    return re.findall(
        r"^      - .*?(?=^      - |\Z)",
        job,
        re.MULTILINE | re.DOTALL,
    )


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


@pytest.mark.parametrize("shell", ["bash", "pwsh"])
def test_release_cells_compare_both_builds_before_installation(shell: str) -> None:
    job = _extract_job(CI, "release-gates")
    steps = [
        step for step in _extract_step_blocks(job)
        if f"if: matrix.shell == '{shell}'" in step
        and "scripts/build_release_artifacts.py" in step
    ]
    assert len(steps) == 1
    step = steps[0]
    assert f"shell: {shell}\n" in step
    assert "continue-on-error:" not in job
    lines = step.split("        run: |\n", 1)[1].splitlines()
    commands = [line.strip() for line in lines if line.strip()]
    required = [
        "python scripts/build_release_artifacts.py --output .ci-dist-a --source-date-epoch 0",
        "python scripts/build_release_artifacts.py --output .ci-dist-b --source-date-epoch 0",
        "python scripts/packaging_policy.py compare .ci-dist-a/autopulse-0.1.0-py3-none-any.whl .ci-dist-b/autopulse-0.1.0-py3-none-any.whl",
        "python scripts/packaging_policy.py compare .ci-dist-a/autopulse-0.1.0.tar.gz .ci-dist-b/autopulse-0.1.0.tar.gz",
    ]
    start = commands.index(required[0])
    # Standalone consecutive commands reject comments, conditionals, success
    # overrides, self-comparisons, and an unused second build.
    assert commands[start:start + len(required)] == required
    assert commands[start + len(required)].startswith(
        "python scripts/verify_release_cell.py "
    )
    if shell == "pwsh":
        assert commands[:2] == [
            "$ErrorActionPreference = 'Stop'",
            "$PSNativeCommandUseErrorActionPreference = $true",
        ]
        assert all(not command.startswith("$") for command in commands[2:])
    else:
        assert all(command.startswith("python ") for command in commands)


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


def test_docs_dependency_audit_is_an_unconditional_fail_closed_gate() -> None:
    docs_job = _extract_job(CI, "docs")
    steps = _extract_step_blocks(docs_job)
    audit_steps = [step for step in steps if "npm audit" in step]

    assert len(audit_steps) == 1
    audit_step = audit_steps[0]
    assert audit_step.strip() == f"- run: {DOCS_AUDIT_COMMAND}"

    # Keep the gate unconditional and on the job's fail-closed default Bash
    # invocation. The exact standalone block also rejects multiline shell
    # success overrides and the Bash error-suppression commands set +e and
    # set +o errexit.
    assert not re.search(r"^\s+if:\s*", audit_step, re.MULTILINE)
    assert not re.search(r"^\s+shell:\s*", audit_step, re.MULTILINE)
    step_continue = re.search(
        r"^\s+continue-on-error:\s*(\S+)", audit_step, re.MULTILINE
    )
    assert step_continue is None or step_continue.group(1) == "false"
    assert not re.search(rf"{re.escape(DOCS_AUDIT_COMMAND)}\s*(?:\|\||;|&&)", audit_step)
    assert not re.search(
        r"(?:^|[;&|]\s*)set\s+(?:\+e|\+o\s+errexit)(?:\s|$)",
        audit_step,
        re.MULTILINE,
    )

    job_continue = re.search(
        r"^    continue-on-error:\s*(\S+)", docs_job, re.MULTILINE
    )
    assert job_continue is None or job_continue.group(1) == "false"
    assert re.search(r"^        shell: bash$", docs_job, re.MULTILINE)

    audit_index = steps.index(audit_step)
    npm_ci_index = next(
        index for index, step in enumerate(steps) if step.strip() == "- run: npm ci"
    )
    assert audit_index == npm_ci_index + 1
    for required_later_step in (
        "npx playwright install --with-deps chromium",
        "npm run build",
        "npm run test:smoke",
        "npm run test:e2e",
    ):
        assert audit_index < next(
            index for index, step in enumerate(steps) if required_later_step in step
        )
