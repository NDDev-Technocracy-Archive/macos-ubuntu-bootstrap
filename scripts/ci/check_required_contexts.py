#!/usr/bin/env python3
"""Prove the three statements of `main`'s required checks are one list.

The contexts that protect `main` are written down three times:

* the live ruleset, which is the authority;
* ``.github/rulesets/branch-main.json``, the checked-in mirror a reviewer reads;
* ``.gds/repository.yaml`` → ``verification.required_contexts``, which the
  control plane reads.

Nothing compared them. The mirror was allowed to run ahead of the live ruleset
as a "proposal", and the ``.gds`` list was bound by no test at all -- it happened
to be correct, and nothing would have reported it if it stopped being. A reader,
human or agent, cannot tell an accurate list from a stale one by looking.

Two of the three are files, so they are compared on every test run. The live
ruleset needs the API and is compared when ``--live`` is passed; CI passes it.

Exit status is 0 only when every list compared is identical.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIRROR = ROOT / ".github/rulesets/branch-main.json"
ANCHOR = ROOT / ".gds/repository.yaml"
LIVE_ENDPOINT = "/repos/{repo}/rules/branches/main"
DEFAULT_REPO = "NDDev-it-com/macos-ubuntu-bootstrap"


class ContextError(RuntimeError):
    """The three declarations of the required checks do not agree."""


def mirror_contexts(path: Path = MIRROR) -> list[str]:
    ruleset = json.loads(path.read_text(encoding="utf-8"))
    contexts = [
        check["context"]
        for rule in ruleset.get("rules", [])
        if rule.get("type") == "required_status_checks"
        for check in rule.get("parameters", {}).get("required_status_checks", [])
    ]
    if not contexts:
        raise ContextError(f"{path}: declares no required status check")
    return sorted(contexts)


def anchor_contexts(path: Path = ANCHOR) -> list[str]:
    """Read ``verification.required_contexts`` without a YAML reader.

    The locked test environment carries none, and adding a dependency to a
    repository whose subject is supply-chain discipline, so that a lint can read
    six lines of a flat list, is the wrong trade. The block is a sequence of
    quoted scalars at a fixed indent under a known key; anything else is a
    parse error rather than a guess.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    contexts: list[str] = []
    inside = False
    for line in lines:
        if re.fullmatch(r"\s*required_contexts:\s*", line):
            inside = True
            continue
        if not inside:
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.fullmatch(r"\s*-\s*\"([^\"]+)\"\s*", line)
        if item is None:
            break  # the list ended; anything else belongs to another key
        contexts.append(item.group(1))
    if not inside:
        raise ContextError(f"{path}: has no verification.required_contexts block")
    if not contexts:
        raise ContextError(f"{path}: verification.required_contexts is empty")
    return sorted(contexts)


def live_contexts(repo: str = DEFAULT_REPO) -> list[str]:
    """Ask GitHub what the branch actually enforces.

    Uses the rules endpoint rather than the rulesets endpoint on purpose: rules
    are readable with ordinary read access, so this runs in CI under
    `contents: read` instead of needing an administrative token.
    """
    endpoint = LIVE_ENDPOINT.format(repo=repo)
    try:
        completed = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ContextError("--live needs the gh CLI, which is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ContextError(
            f"--live could not read {endpoint}: {exc.stderr.strip() or exc}"
        ) from exc

    rules = json.loads(completed.stdout)
    contexts = [
        check["context"]
        for rule in rules
        if rule.get("type") == "required_status_checks"
        for check in rule.get("parameters", {}).get("required_status_checks", [])
    ]
    if not contexts:
        contexts = _disabled_ruleset_contexts(repo)
    if not contexts:
        raise ContextError(
            f"{endpoint} reports no required status check; either the ruleset was "
            "emptied or this token cannot see it"
        )
    return sorted(contexts)


def _disabled_ruleset_contexts(repo: str) -> list[str]:
    """Contexts of a branch ruleset that exists but is not enforced.

    The rules endpoint lists only enforced rules. In the Archive the owner
    disabled the rulesets (2026-10-22), so the rules endpoint is empty while
    the ruleset still states what protects main; that definition is what the
    mirror must match. Rulesets are readable with read access.
    """
    contexts: list[str] = []
    try:
        listed = subprocess.run(
            ["gh", "api", f"/repos/{repo}/rulesets"],
            capture_output=True, text=True, check=True,
        )
        for summary in json.loads(listed.stdout):
            if summary.get("target") != "branch" or summary.get("enforcement") == "active":
                continue
            detail = subprocess.run(
                ["gh", "api", f"/repos/{repo}/rulesets/{summary['id']}"],
                capture_output=True, text=True, check=True,
            )
            ruleset = json.loads(detail.stdout)
            found = [
                check["context"]
                for rule in ruleset.get("rules", [])
                if rule.get("type") == "required_status_checks"
                for check in rule.get("parameters", {}).get("required_status_checks", [])
            ]
            if found:
                print(
                    f"required-contexts-notice: ruleset {ruleset.get('name')!r} is "
                    f"{ruleset.get('enforcement')}; comparing its definition"
                )
                contexts += found
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return []
    return contexts


def _report(name_a: str, a: list[str], name_b: str, b: list[str]) -> None:
    if a == b:
        return
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    raise ContextError(
        f"{name_a} and {name_b} disagree about what protects main:\n"
        f"  only in {name_a}: {only_a or '-'}\n"
        f"  only in {name_b}: {only_b or '-'}"
    )


def check(*, live: bool, repo: str = DEFAULT_REPO) -> int:
    mirror = mirror_contexts()
    anchor = anchor_contexts()
    _report("the ruleset mirror", mirror, "the .gds anchor", anchor)

    if live:
        actual = live_contexts(repo)
        _report("the live ruleset", actual, "the ruleset mirror", mirror)
        print(f"required-contexts-ok: {len(actual)} contexts, live == mirror == anchor")
    else:
        print(f"required-contexts-ok: {len(mirror)} contexts, mirror == anchor")

    for context in mirror:
        print(f"  {context}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="also compare against the live ruleset through the GitHub API",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO,
        help="owner/name to query when --live is passed",
    )
    args = parser.parse_args(argv)
    return check(live=args.live, repo=args.repo)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContextError as exc:
        print(f"required-contexts-error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
