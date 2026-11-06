from pathlib import Path
import ast
import itertools
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-docs.yml").read_text(encoding="utf-8")
PROBE = (ROOT / ".github/workflows/verify-pages-gate.yml").read_text(encoding="utf-8")


APPROVED_V7_PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1", 3),
    "actions/setup-python": ("6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "v7.1.0", 1),
    "actions/setup-node": ("949feb2413d6458794dcd2491c4babbbce0c15c1", "v7.1.0", 2),
}

VALIDATOR = (ROOT / "grubby-galaxy/scripts/validate-docs.mjs").read_text(encoding="utf-8")


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
    assert "--base" not in CI and "pages: write" not in CI
    assert "configure-pages@" not in DEPLOY
    config = (ROOT / "grubby-galaxy/scripts/docs-provenance.mjs").read_text(encoding="utf-8")
    assert "site: 'https://ajason13.github.io', base: '/autopulse/'" in config
    assert all(
        re.fullmatch(r"[0-9a-f]{40}", sha)
        for sha in re.findall(r"uses:\s*[^@\s]+@([^\s#]+)", DEPLOY)
    )


def test_docs_dependency_audit_is_an_unconditional_fail_closed_gate() -> None:
    for workflow, job_name in [(CI, "docs"), (DEPLOY, "build")]:
        job = _extract_job(workflow, job_name)
        steps = _extract_step_blocks(job)
        commands = [step.strip() for step in steps if "- run:" in step]
        assert commands[:2] == ["- run: npm ci", "- run: npm run validate:docs"]
        assert "continue-on-error:" not in job
        assert "always()" not in job
        assert "shell: bash" in job
    # Runtime negative tests exercise each rejected gate; this ensures the
    # shared entry point still includes the required production audit.
    assert "await run(['audit', '--omit=dev', '--audit-level=high']);" in VALIDATOR


def test_pages_gate_is_main_only_and_privileged_job_executes_no_repo_code() -> None:
    assert "pull_request" not in DEPLOY and "workflow_run" not in DEPLOY
    assert "branches: [main]" in DEPLOY and "workflow_dispatch:" in DEPLOY
    global_permissions = DEPLOY.split("permissions:\n", 1)[1].split("\n\n", 1)[0]
    assert global_permissions.strip() == "contents: read"
    build = _extract_job(DEPLOY, "build")
    deploy = _extract_job(DEPLOY, "deploy")
    eligibility = "github.ref == 'refs/heads/main'"
    for job in [build, deploy]:
        assert eligibility in job
        assert "github.event_name == 'push'" in job
        assert "github.event_name == 'workflow_dispatch'" in job
        assert "continue-on-error:" not in job and "always()" not in job
    assert "pages: write" not in build and "id-token: write" not in build
    assert "persist-credentials: false" in build
    assert "needs: build" in deploy and "needs.build.result == 'success'" in deploy
    assert "needs.build.outputs.artifact-id != ''" in deploy
    assert "pages: write" in deploy and "id-token: write" in deploy
    assert "name: github-pages" in deploy
    assert "run:" not in deploy and "checkout@" not in deploy
    assert len(_extract_step_blocks(deploy)) == 1


def test_pages_uploads_only_validated_bytes_and_selects_same_run_artifact() -> None:
    build = _extract_job(DEPLOY, "build")
    steps = _extract_step_blocks(build)
    validation = next(i for i, s in enumerate(steps) if s.strip() == "- run: npm run validate:docs")
    upload = next(i for i, s in enumerate(steps) if "actions/upload-pages-artifact@" in s)
    assert upload == validation + 2
    assert 'github-pages-${GITHUB_SHA}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}' in steps[validation + 1]
    assert "steps.identity.outputs.artifact-name" in steps[upload]
    assert "path: grubby-galaxy/dist" in steps[upload]
    assert "include-hidden-files: true" in steps[upload]
    assert upload == len(steps) - 1
    deploy = _extract_job(DEPLOY, "deploy")
    assert "artifact_name: ${{ needs.build.outputs.artifact-name }}" in deploy
    assert "artifact-id: ${{ steps.upload.outputs.artifact_id }}" in build
    assert "artifact-name: ${{ steps.identity.outputs.artifact-name }}" in build
    assert "cancel-in-progress: false" in DEPLOY


def test_hosted_gate_probe_cannot_publish_or_deploy() -> None:
    assert "push:" in PROBE and "workflow_dispatch:" in PROBE
    assert "contents: read" in PROBE and "write" not in PROBE
    assert "pull_request_target" not in PROBE and "workflow_run" not in PROBE
    assert "upload" not in PROBE and "deploy-pages@" not in PROBE
    assert "test_ci_workflow_contract.py" in PROBE
    assert "node --test grubby-galaxy/tests/docs-provenance.test.mjs" in PROBE
    for action, sha in re.findall(r"uses:\s*([^@\s]+)@([^\s#]+)", PROBE):
        assert action in APPROVED_V7_PINS
        assert sha == APPROVED_V7_PINS[action][0]


def _condition(job: str, **context: str) -> bool:
    expression = re.search(r"^    if: (.+)$", job, re.MULTILINE).group(1)
    for key, value in context.items():
        expression = expression.replace(key, repr(value))
    tree = ast.parse(expression.replace("&&", " and ").replace("||", " or "), mode="eval")
    assert all(isinstance(node, (
        ast.Expression, ast.BoolOp, ast.Compare, ast.Constant,
        ast.And, ast.Or, ast.Eq, ast.NotEq,
    )) for node in ast.walk(tree))
    return eval(compile(tree, "<workflow-condition>", "eval"), {"__builtins__": {}})


@pytest.mark.parametrize("ref,event,result,artifact", list(itertools.product(
    ["refs/heads/main", "refs/heads/feature", "refs/tags/main"],
    ["push", "workflow_dispatch", "pull_request"],
    ["success", "failure", "cancelled", "skipped"], ["42", ""],
)))
def test_push_and_manual_gate_scenarios(ref, event, result, artifact) -> None:
    context = {
        "github.ref": ref, "github.event_name": event,
        "needs.build.result": result, "needs.build.outputs.artifact-id": artifact,
    }
    eligible = ref == "refs/heads/main" and event in {"push", "workflow_dispatch"}
    assert _condition(_extract_job(DEPLOY, "build"), **context) == eligible
    assert _condition(_extract_job(DEPLOY, "deploy"), **context) == (
        eligible and result == "success" and bool(artifact)
    )
