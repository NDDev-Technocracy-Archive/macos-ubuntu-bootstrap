#!/usr/bin/env python3
"""Prove CI analyses this repository with the tools its contract pins.

`config/rldyour-contract.json` states which version and digest of a tool a
device gets. Several of those tools -- the CI-parity scanners -- are also run by
this repository's own workflows, through reusable workflows that carry their own
defaults. Nothing compared the two, and they had diverged: the contract pinned
OSV-Scanner 2.5.0 while the caller passed no version at all and inherited the
provider's 2.4.0 default, whose scanning pipeline is not the same one. A
developer's machine and the repository's merge gate were answering the same
question with different programs.

The check that used to guard this searched the installers for variable names:

    for marker in ("RLDYOUR_CODEX_VERSION", "RLDYOUR_CODEX_SHA512", ...):
        if marker not in common_data: raise SystemExit(...)

A name is not an identity. Every one of those markers survives changing the
version it holds, the digest it holds and the URL it is fetched from, which is
the entire content of a dependency pin. This module compares the values.

Three properties, each of which fails on a real mutation:

1. every tool a workflow acquires by version and digest matches the contract;
2. every download inside a workflow is bound to a fixed version in its URL and
   verified against a digest before it is used;
3. no vendor installer is executed straight from the network, and the pins that
   make that safe hold their declared shape.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/rldyour-contract.json"
WORKFLOWS = ROOT / ".github/workflows"
COMMON = ROOT / "scripts/lib/common.sh"

# Which workflow inputs carry a contract-pinned tool identity.
#
# Declared rather than discovered: a reusable workflow's input names are its
# interface, and guessing them from a pattern would make this check pass by
# finding nothing the day one of them is renamed. A tool that gains a CI caller
# gets a row here; a row whose file or inputs disappear is an error, not a skip.
#
# `arch` names which of the contract's per-architecture digests the workflow
# actually downloads. Every one of these lanes runs on a Linux X64 runner --
# the providers say so explicitly -- so they all take `x64`.
CI_TOOL_INPUTS: tuple[tuple[str, str, str, str, str], ...] = ()

# Lanes that acquire a tool through the STD-0004 library's `tools` action. The
# library downloads each tool at an exact version and verifies its SHA-256
# before use, so the binding to check here is the full-SHA pin of the action;
# a tag or branch reference would let the tool change without a diff.
LIBRARY_TOOL_LANES: tuple[tuple[str, str], ...] = (
    ("osv-scanner", "osv-scan.yml"),
    ("actionlint", "ci.yml"),
)
LIBRARY_TOOLS = re.compile(
    r"uses:\s*NDDev-Technocracy-Standarts/std-0004-ci-cd-workflows/\.github/actions/tools@[0-9a-f]{40}\b"
)

# Workflows that read a tool's identity out of the contract at run time instead
# of restating it. That is the stronger form -- there is no second copy to
# drift, so there is nothing for `check_tool_parity` to compare -- but it is
# only available to a plain `run:` step. A `uses:` caller must pass literals,
# because a reusable workflow's inputs cannot read a file, which is why `ci.yml`
# appears in the table above and `release.yml` appears here.
CONTRACT_DERIVED: tuple[tuple[str, str], ...] = (
    ("release.yml", ".runtime_support.ubuntu_pinned_source_tools.actionlint.version"),
    ("release.yml", ".runtime_support.ubuntu_pinned_source_tools.actionlint.sha256.x64"),
    ("release.yml", ".runtime_support.ubuntu_uv"),
    ("release.yml", ".runtime_support.ubuntu_uv_sha256.x64"),
)

# A release asset URL must name an exact version. These are the ways a URL says
# "whatever is newest", which is the property being forbidden.
FLOATING_URL = re.compile(
    r"https://[^\s\"']*/(?:latest/download|releases/latest|/(?:main|master|HEAD)/)",
    re.I,
)

# `curl … | sh`, in the spellings that actually occur, on one logical line.
NETWORK_TO_SHELL = re.compile(
    r"\b(?:curl|wget)\b[^\n|]*\|[^\n|]*\b(?:ba|z|k|d)?sh\b",
)

# A digest verification, in either utility and either flag spelling. The
# repository uses `sha256sum --check --status`; matching only `-c` would have
# reported its own correct code as unverified.
VERIFIES_DIGEST = re.compile(r"\b(?:sha256sum|shasum)\b[^\n]*(?:-c\b|--check\b)")


class ParityError(RuntimeError):
    """CI and the contract do not describe the same tool."""


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def contract_tool(contract: dict, name: str) -> dict:
    tools = contract["runtime_support"]["ubuntu_pinned_source_tools"]
    if name not in tools:
        raise ParityError(
            f"the contract has no pinned source tool {name!r}; "
            "CI_TOOL_INPUTS names a tool the contract does not pin"
        )
    return tools[name]


def workflow_input(text: str, name: str) -> str | None:
    """The value a caller passes for `name`, or None if it passes none.

    Parsed line-wise for the same reason `tests/test_agent_context.py` is: the
    hash-locked test environment carries no YAML reader, and adding one so a
    lint can read a scalar would be a supply-chain change made for convenience.
    """
    match = re.search(rf"^\s*{re.escape(name)}:\s*(.+?)\s*$", text, re.M)
    if match is None:
        return None
    return match.group(1).strip().strip("'\"")


def check_tool_parity(contract: dict) -> list[str]:
    findings: list[str] = []
    for tool, filename in LIBRARY_TOOL_LANES:
        path = WORKFLOWS / filename
        if not path.is_file():
            findings.append(f"{filename}: named by LIBRARY_TOOL_LANES but absent")
        elif not LIBRARY_TOOLS.search(path.read_text(encoding="utf-8")):
            findings.append(
                f"{filename}: acquires {tool} without the full-SHA pinned STD-0004 tools action"
            )
    for tool, filename, version_input, digest_input, arch in CI_TOOL_INPUTS:
        path = WORKFLOWS / filename
        if not path.is_file():
            findings.append(f"{filename}: named by CI_TOOL_INPUTS but absent")
            continue
        text = path.read_text(encoding="utf-8")
        spec = contract_tool(contract, tool)
        expected_version = str(spec["version"])
        expected_digest = spec["sha256"][arch]

        actual_version = workflow_input(text, version_input)
        actual_digest = workflow_input(text, digest_input)

        if actual_version is None:
            findings.append(
                f"{filename}: passes no {version_input}, so it inherits the "
                f"provider's default instead of the contract's {tool} "
                f"{expected_version}"
            )
        elif actual_version != expected_version:
            findings.append(
                f"{filename}: {version_input} is {actual_version!r}, the contract "
                f"pins {tool} {expected_version!r}"
            )

        if actual_digest is None:
            findings.append(f"{filename}: passes no {digest_input}")
        elif actual_digest != expected_digest:
            findings.append(
                f"{filename}: {digest_input} is {actual_digest!r}, the contract "
                f"pins {expected_digest!r} for {tool} {arch}"
            )
    return findings


def _without_comments(text: str) -> str:
    """Drop whole-line comments.

    A comment is documentation, not behaviour, and every scanner in this file
    has to know the difference. The rule this replaces did not: a comment
    quoting the construct it forbade failed the build, which trains the next
    author to stop writing down why a rule exists. `#` at the start of a line
    is a comment in YAML and, inside a `run:` block, in the shell too.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def check_workflow_downloads() -> list[str]:
    """Every workflow download names a version and is checked against a digest."""
    findings: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = _without_comments(path.read_text(encoding="utf-8"))
        for match in FLOATING_URL.finditer(text):
            findings.append(
                f"{path.name}: resolves a floating release URL: {match.group(0)}"
            )
        # A download step must verify what it downloaded. Checked per step so a
        # `sha256sum -c` somewhere else in the file cannot vouch for it.
        for step in re.split(r"\n      - ", text):
            if not re.search(r"\b(?:curl|wget)\b.*https://", step):
                continue
            if VERIFIES_DIGEST.search(step):
                continue
            name = re.search(r"name:\s*(.+)", step)
            findings.append(
                f"{path.name}: step {name.group(1).strip() if name else '?'!r} "
                "downloads over the network without verifying a digest"
            )
    return findings


def check_contract_derived() -> list[str]:
    """The run-time readers still read the keys they claim to read.

    A `jq` path that stops matching does not fail loudly on its own -- `jq -er`
    does, but only when that lane runs, which for `release.yml` is the moment a
    release is being cut. Asserting the paths here moves that failure to every
    pull request.
    """
    findings: list[str] = []
    contract = load_contract()
    for filename, jq_path in CONTRACT_DERIVED:
        path = WORKFLOWS / filename
        if not path.is_file():
            findings.append(f"{filename}: named by CONTRACT_DERIVED but absent")
            continue
        if jq_path not in path.read_text(encoding="utf-8"):
            findings.append(
                f"{filename}: no longer reads {jq_path} from the contract; a tool "
                "identity that was derived is now stated somewhere else or hard-coded"
            )
        node = contract
        for key in jq_path.lstrip(".").split("."):
            if not isinstance(node, dict) or key not in node:
                findings.append(f"the contract has no {jq_path}, which {filename} reads")
                break
            node = node[key]
    return findings


def check_no_network_to_shell(root: Path = ROOT / "scripts") -> list[str]:
    """No script executes a network response.

    This replaces the sweep `validate.sh` used to run, which matched the raw
    text `curl … | sh` anywhere under `scripts/`. That enforced a spelling
    rather than a property, in both directions: prose *describing* the
    construct failed the build, while the same construct written with `wget`,
    or piped into `zsh` or `dash`, passed it untouched.

    The two file kinds are checked the way each can actually execute a
    pipeline, because that is the difference the old sweep could not see:

    * a shell script executes what it contains, so its lines are read directly,
      minus comments;
    * a Python file cannot execute a pipeline by containing the words -- it has
      to hand them to a shell. So it is parsed, and what is looked for is the
      handing over: `os.system`, or `subprocess` with `shell=True`. A string
      inside a docstring is documentation and is not a finding; the same string
      passed to `subprocess.run(..., shell=True)` is.
    """
    findings: list[str] = []
    if not root.is_dir():
        return [f"{root}: expected script directory is missing"]

    for path in sorted(root.rglob("*")):
        # Suffix first: `rglob` also returns compiled caches and any binary a
        # working tree happens to carry, and reading one as UTF-8 raises rather
        # than reporting a finding -- a scanner that crashes on an unrelated
        # file is a scanner that stops covering the files it was written for.
        if path.suffix not in {".sh", ".bash", ".zsh", ".py"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")

        if path.suffix in {".sh", ".bash", ".zsh"}:
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if NETWORK_TO_SHELL.search(line):
                    findings.append(
                        f"{path.relative_to(ROOT)}:{number}: pipes a network "
                        f"response into a shell: {line.strip()}"
                    )
        elif path.suffix == ".py":
            findings.extend(_python_shell_handoffs(path, text))

    return findings


def _python_shell_handoffs(path: Path, text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"{path.relative_to(ROOT)}: does not parse: {exc}"]

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = ast.unparse(node.func)
        hands_to_shell = target in {"os.system", "system"} or any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        if hands_to_shell:
            findings.append(
                f"{path.relative_to(ROOT)}:{node.lineno}: hands a command to a "
                f"shell ({target}); build the argument list instead so a "
                "network response can never become a command"
            )
    return findings


def check_vendor_pin_shape() -> list[str]:
    """The vendor CLI pins hold a digest, not merely a name.

    The previous gate asserted these identifiers existed. That passes against a
    pin whose digest has been replaced with anything at all, including the empty
    string, so it proved only that someone had once written the word.
    """
    findings: list[str] = []
    text = COMMON.read_text(encoding="utf-8")
    for name, width in (
        ("RLDYOUR_CLAUDE_INSTALLER_SHA256", 64),
        ("RLDYOUR_GROK_INSTALLER_SHA256", 64),
        ("RLDYOUR_CODEX_SHA512", 128),
    ):
        match = re.search(rf'^{name}="([^"]*)"', text, re.M)
        if match is None:
            findings.append(f"scripts/lib/common.sh: {name} is not declared")
            continue
        value = match.group(1)
        if not re.fullmatch(rf"[0-9a-f]{{{width}}}", value):
            findings.append(
                f"scripts/lib/common.sh: {name} is not a {width}-character "
                f"lowercase hex digest: {value!r}"
            )
    if not re.search(r"^RLDYOUR_CODEX_VERSION=\"\d+\.\d+\.\d+\"", text, re.M):
        findings.append(
            "scripts/lib/common.sh: RLDYOUR_CODEX_VERSION is not an exact "
            "three-part version"
        )
    for helper in ("rldyour::download_verified_file", "rldyour::install_vendor_ai_clis"):
        if f"{helper}()" not in text:
            findings.append(f"scripts/lib/common.sh: {helper} is not defined")
    return findings


def check(contract: dict | None = None) -> int:
    contract = contract if contract is not None else load_contract()
    findings = (
        check_tool_parity(contract)
        + check_contract_derived()
        + check_workflow_downloads()
        + check_no_network_to_shell()
        + check_vendor_pin_shape()
    )
    if findings:
        raise ParityError("\n".join(f"  {item}" for item in findings))

    sites = len(CI_TOOL_INPUTS) + len(LIBRARY_TOOL_LANES) + len({name for name, _ in CONTRACT_DERIVED})
    print(f"ci-tool-parity-ok: {sites} CI call sites bound to the contract")
    for tool, filename, _version, _digest, arch in CI_TOOL_INPUTS:
        spec = contract_tool(contract, tool)
        print(f"  {filename}: {tool} {spec['version']} ({arch}), stated and compared")
    for tool, filename in LIBRARY_TOOL_LANES:
        print(f"  {filename}: {tool} from the SHA-pinned STD-0004 tools action")
    for filename in sorted({name for name, _ in CONTRACT_DERIVED}):
        print(f"  {filename}: reads its tool identities from the contract at run time")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args(argv)
    return check(load_contract(args.contract))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ParityError as exc:
        print(f"ci-tool-parity-error:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
