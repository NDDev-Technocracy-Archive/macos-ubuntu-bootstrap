"""The agent-facing context has one canonical source, and its rules are gates.

Four hand-maintained layers used to describe this repository: `AGENTS.md`,
`.claude/CLAUDE.md`, 23 Serena memories and a compiled GDS projection. They
drifted -- the Claude file did not know the `desktop-builds` profile and used a
retired name for the server policy, and the memory index claimed three tracked
memories when there were 23.

These tests hold the collapsed shape in place: one guide, one import, and rules
that are checked rather than asserted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / ".claude/CLAUDE.md"
MEMORIES = ROOT / ".serena/memories"
CONTRACT = json.loads((ROOT / "config/rldyour-contract.json").read_text(encoding="utf-8"))
WORKFLOWS = ROOT / ".github/workflows"
ANCHOR = ROOT / ".gds/repository.yaml"
SETUP_SCRIPT = "scripts/ci/setup-test-env.sh"


def _behaviour(text: str) -> str:
    """The lines that do something, without the lines that explain them.

    Every scanner in this repository has had to learn this distinction the
    hard way: a check that reads a comment as code punishes writing down why a
    rule exists, which is the documentation most worth keeping.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


# ----------------------------- context topology -----------------------------


def test_claude_imports_the_canonical_guide_instead_of_restating_it() -> None:
    text = CLAUDE.read_text(encoding="utf-8")
    assert "@AGENTS.md" in text, "CLAUDE.md must import the canonical guide"
    # A second copy of the project contract is what drifted last time.
    assert len(text.splitlines()) <= 60, (
        "CLAUDE.md is a delta, not a second specification"
    )


def test_pins_are_not_duplicated_into_the_agent_context() -> None:
    """Exact versions belong to the contract; prose copies of them go stale."""
    claude = CLAUDE.read_text(encoding="utf-8")
    support = CONTRACT["runtime_support"]
    for field in ("ubuntu_node_lts", "ubuntu_uv", "ubuntu_bun", "ubuntu_go", "ubuntu_dart"):
        assert support[field] not in claude, (
            f"CLAUDE.md pins {field}={support[field]}; the contract owns that"
        )


def test_no_agent_surface_names_a_retired_profile_or_policy() -> None:
    known_profiles = set(CONTRACT["targets"]["ubuntu"]["profiles"])
    policies = {
        spec["execution_policy"] for spec in CONTRACT["targets"]["ubuntu"]["profiles"].values()
    }
    for path in (AGENTS, CLAUDE):
        text = path.read_text(encoding="utf-8")
        assert "server-build-runtime" not in text, (
            f"{path.name} uses a policy name the contract retired"
        )
        if "--profile" in text:
            missing = sorted(p for p in known_profiles if p not in text)
            assert missing == [], f"{path.name} omits supported profile(s): {missing}"
    assert "container-execution-only" in policies


def test_the_memory_corpus_stays_small_and_self_describing() -> None:
    memories = sorted(MEMORIES.glob("*.md"))
    assert len(memories) <= 3, (
        f"{len(memories)} tracked memories; the corpus is derived context, not a "
        "second specification"
    )
    for memory in memories:
        text = memory.read_text(encoding="utf-8")
        # A memory that repeats a pin is a copy that will go stale.
        assert CONTRACT["adapter"]["version"] not in text, (
            f"{memory.name} pins the adapter version"
        )


# ----------------------------- rules as gates -----------------------------


EXEMPTION = "exposes no `runner` input"


# GitHub-hosted labels. Anything else routes onto the estate fleet, whose own
# threat model forbids public/fork code on a trusted runner group
# (modules/github-actions, docs/threat-model.md) -- and this repository is
# public.
#
# An allowlist, never a denylist of fleet labels. The fleet's scale-set classes
# (nddev-linux-fast/standard/integration/release as of 2026-08-12, the former
# `amsterdam` retired) change over time, and a job requesting a label no runner
# advertises does not fail -- it queues indefinitely. Enumerating the safe
# values is the only form of this check that survives a renamed class and
# turns a hang into a failed test.
HOSTED_RUNNERS = {
    "ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "ubuntu-24.04-arm",
    "macos-latest", "macos-15", "macos-14",
    "windows-latest", "windows-2022",
}


def _reusable_callers() -> list[tuple[Path, bool, bool, bool, str]]:
    """(workflow, has `with:`, names `runner`, exempt, the runner value).

    Parsed line-wise on purpose: the locked test environment carries no YAML
    reader, and pulling one in for a lint would be a supply-chain change for a
    convenience. These files have one `uses:` per job at a fixed indent.
    """
    callers: list[tuple[Path, bool, bool, bool, str]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "uses: NDDev-OpenNetwork/ci-workflows/" not in line:
                continue
            indent = len(line) - len(line.lstrip())
            has_with = names_runner = exempt = False
            runner_value = ""
            for follower in lines[index + 1 :]:
                if follower.strip() and (len(follower) - len(follower.lstrip())) < indent:
                    break  # left the job
                stripped = follower.strip()
                if EXEMPTION in stripped:
                    exempt = True
                elif stripped == "with:":
                    has_with = True
                elif has_with and stripped.startswith("runner:"):
                    names_runner = True
                    runner_value = stripped.split(":", 1)[1].strip().strip("'\"")
            callers.append((path, has_with, names_runner, exempt, runner_value))
    return callers


def test_every_reusable_caller_that_can_name_a_runner_does() -> None:
    """This was prose in two files and enforced by nothing.

    The repository is public, so `pull_request` runs untrusted fork code. The
    reusable's `runner` default belongs to the pinned commit, not to this
    repository, and several of those reusables default it to the estate's
    self-hosted label -- so a routine Dependabot pin bump could move fork PRs
    onto trusted infrastructure with no diff here to review.
    """
    callers = _reusable_callers()
    assert callers, "no ci-workflows callers found"
    # `has_with` is deliberately not part of this condition. It used to be:
    # the rule only applied to a caller that already passed some input, so
    # deleting the entire `with:` block -- the single edit that most obviously
    # hands runner selection back to the provider's default -- removed the
    # caller from the test's attention instead of failing it. The property is
    # about every caller, not about callers that happen to configure something.
    missing = [
        path.name
        for path, _has_with, names_runner, exempt, _value in callers
        if not names_runner and not exempt
    ]
    assert missing == [], (
        f"these callers never name a runner: {missing}. Pass "
        "`runner: ubuntu-latest`; if the reusable exposes no `runner` input at "
        "the pinned commit, say so in a comment next to the call."
    )
    # An exemption is a claim about the pinned commit and must be re-checked
    # when the pin moves, so it is recorded next to the call rather than
    # remembered.
    self_hosted = [
        (path.name, value)
        for path, _w, names_runner, _e, value in callers
        if names_runner and value not in HOSTED_RUNNERS
    ]
    assert self_hosted == [], (
        f"these callers name a non-hosted runner: {self_hosted}. The estate "
        "runner platform forbids public/fork code on a trusted runner group, "
        "and this repository is public."
    )
    exempted = [path.name for path, _w, _r, exempt, _v in callers if exempt]
    assert exempted == ["pr-hygiene.yml"], (
        f"the exemption list changed: {exempted}. Verify against the reusable's "
        "inputs at the pinned commit before accepting it."
    )


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_reusable_workflows_are_pinned_to_an_exact_commit(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"uses:\s*(NDDev-it-com/ci-workflows/[^@]+)@(\S+)", line)
        if match:
            assert re.fullmatch(r"[0-9a-f]{40}", match.group(2)), (
                f"{path.name} uses a mutable ref: {match.group(2)}"
            )


def _matrix_values(text: str, key: str) -> list[str]:
    """Every value of a `matrix.<key>` list, in block or inline form."""
    values: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f"{key}:":
            indent = len(line) - len(line.lstrip())
            for follower in lines[index + 1 :]:
                if not follower.strip():
                    continue
                if (len(follower) - len(follower.lstrip())) <= indent:
                    break
                if follower.strip().startswith("- "):
                    values.append(follower.strip()[2:].strip().strip("'\""))
        elif stripped.startswith(f"{key}: ["):
            inline = stripped.split("[", 1)[1].rsplit("]", 1)[0]
            values.extend(v.strip().strip("'\"") for v in inline.split(",") if v.strip())
    return values


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_job_runs_on_a_hosted_runner(path: Path) -> None:
    """`runs-on` is the other way onto a runner, and the reusable-caller gate
    does not see it. A job here selecting `runs-on: nddev-linux-standard`
    would put fork code on the estate fleet exactly as a reusable input
    would."""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("runs-on:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip("'\"")
        if value.startswith("${{"):
            # Resolve a matrix reference to the values it can take.
            key = value.strip("${} ").split(".")[-1].strip()
            candidates = _matrix_values(text, key)
            assert candidates, f"{path.name}: cannot resolve {value}; check it by hand"
        else:
            candidates = [value]
        for candidate in candidates:
            assert candidate in HOSTED_RUNNERS, (
                f"{path.name} runs a job on {candidate!r}. This repository is "
                "public and the estate runner platform forbids public/fork code "
                "on a trusted runner group."
            )


# ----------------------------- secret scanning -----------------------------


def test_gitleaks_allowlist_stays_narrow() -> None:
    """A path allowlist or a disabled rule would hide a real credential in the
    same files. Only the exact public value is exempt."""
    config = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    assert "useDefault = true" in config, "the default rule set must stay in force"
    contract = json.loads((ROOT / "config/rldyour-contract.json").read_text(encoding="utf-8"))
    chrome = next(item for item in contract["ubuntu_apt_packages"]["desktop_apps"] if item["name"] == "google-chrome-stable")
    assert chrome["apt_source"]["key_fingerprint"] in config
    for broad in ("paths =", "files =", "commits =", "stopwords ="):
        assert broad not in config, (
            f"{broad.strip(' =')} allowlisting is too broad; exempt the value"
        )


def test_secret_scan_uses_the_repository_config() -> None:
    caller = (WORKFLOWS / "secret-scan.yml").read_text(encoding="utf-8")
    assert "gitleaks_config_path: .gitleaks.toml" in caller, (
        "the allowlist has no effect unless the caller passes it"
    )


def test_no_tracked_document_points_at_a_deleted_memory() -> None:
    """Collapsing the corpus left README naming three memories that no longer
    exist. Any path a document advertises must resolve."""
    present = {p.name for p in MEMORIES.glob("*.md")}
    for doc in ROOT.rglob("*.md"):
        if any(part in {".venv", ".git"} for part in doc.parts) or doc.name == "CHANGELOG.md":
            continue
        for match in re.finditer(r"\.serena/memories/([A-Za-z0-9_-]+\.md)", doc.read_text(encoding="utf-8")):
            assert match.group(1) in present, (
                f"{doc.relative_to(ROOT)} names {match.group(1)}, which does not exist"
            )


# --------------------- the declared verification lane ----------------------


def test_the_anchor_declares_a_prerequisite_lane_rather_than_inlining_it() -> None:
    """The control plane must be able to tell "not attempted" from "failed".

    `verification.commands.test` used to start with `uv venv --python 3.14`, so
    a host without uv failed before a virtualenv existed and a host with uv but
    without zsh failed inside pytest at a fixture. Both were reported as the
    module failing its tests. GDS has a `bootstrap` lane for exactly this: it
    runs first, and its failure states that the check could not be attempted.
    """
    commands = _behaviour(ANCHOR.read_text(encoding="utf-8")).split("verification:", 1)[1]

    assert re.search(rf"^\s*bootstrap:\n\s*- \"bash {re.escape(SETUP_SCRIPT)}\"", commands, re.M), (
        f"the anchor must declare `bootstrap: [bash {SETUP_SCRIPT}]`"
    )

    test_lane = commands.split("\n    test:\n", 1)[1].split("\n  required:", 1)[0]
    for setup in ("uv venv", "uv pip install", "apt-get"):
        assert setup not in test_lane, (
            f"the test lane restates {setup!r}; environment setup belongs to the "
            "bootstrap lane, so its failure is not reported as a test failure"
        )

    # `bootstrap` is a prerequisite, not proof. The GDS schema forbids it in
    # `required`, and asserting it here keeps the two readings of the anchor --
    # this repository's and the control plane's -- from diverging.
    required = commands.split("\n  required:", 1)[1]
    assert "bootstrap" not in required.split("\n  ", 1)[0], (
        "a module is not verified by having been prepared"
    )


def test_ci_and_the_anchor_use_one_test_environment() -> None:
    """Two descriptions of one environment is how they came to differ.

    `pytest.yml` installed zsh and built the locked virtualenv; the anchor did
    something similar but not the same, and only the workflow's version ever
    ran. Both now name the same script, so there is no second description to
    drift.
    """
    pytest_workflow = _behaviour(
        (WORKFLOWS / "pytest.yml").read_text(encoding="utf-8")
    )
    assert f"install_command: bash {SETUP_SCRIPT}" in pytest_workflow, (
        f"pytest.yml must delegate environment setup to {SETUP_SCRIPT}"
    )
    assert f'uv_version: "{CONTRACT["runtime_support"]["ubuntu_uv"]}"' in pytest_workflow, (
        "the reusable Python lane must provision the exact uv version that "
        "setup-test-env verifies"
    )
    for setup in ("apt-get install", "uv venv", "uv pip install"):
        assert setup not in pytest_workflow, (
            f"pytest.yml restates {setup!r} instead of calling {SETUP_SCRIPT}"
        )
    assert (ROOT / SETUP_SCRIPT).is_file()


def test_the_documented_validation_sequence_is_the_one_that_works() -> None:
    """`python3 -m pytest` is what the anchor exists to rule out.

    It passes only where pytest already happened to be installed. Three
    documents instructed it as *the* validation step long after CI stopped
    using it, so a reader following the guide ran something the repository had
    already established does not prove anything.
    """
    for name in ("README.md", "AGENTS.md", "docs/install.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert SETUP_SCRIPT in text, f"{name} does not mention {SETUP_SCRIPT}"
        assert ".venv/bin/python -m pytest" in text, (
            f"{name} must name the interpreter the locked environment provides"
        )
        # A fenced block is an instruction; prose explaining why the bare
        # command is insufficient is not.
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            assert "python3 -m pytest" not in block, (
                f"{name} still instructs `python3 -m pytest` in a command block"
            )
