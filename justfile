set shell := ["bash", "-euo", "pipefail", "-c"]
set positional-arguments

# List the maintained source commands.
default:
    @just --list

# Run readonly source checks without native tests or bootstrap execution.
check:
    just --fmt --check
    bash scripts/ci/lint.sh
    python3 -B scripts/ci/check_ci_tool_parity.py
    python3 -B scripts/ci/check_ci_tool_parity.py --installed actionlint
    actionlint
    zizmor --offline --no-progress .github/workflows/ci.yml .github/workflows/dependency-check.yml .github/workflows/docs-quality.yml .github/workflows/osv-scan.yml .github/workflows/platform-evidence.yml .github/workflows/pytest.yml .github/workflows/semgrep.yml .github/workflows/source-drift.yml .github/workflows/security.yml .github/workflows/security-daily.yml .github/dependabot.yml

# Retain exact PR-diff or complete-history secret scope with the original policy.
verify scope="--all": check
    betterleaks git --no-banner --redact --config .gitleaks.toml "--log-opts=$1" .

# Retain the full recursive source dependency scan.
audit-dependencies:
    python3 -B scripts/ci/check_ci_tool_parity.py --installed osv-scanner
    osv-scanner scan source --recursive .

# Retain the original live link check and its existing upstream exception.
links:
    lychee --no-progress --max-concurrency 8 --exclude 'openai\.com' "**/*.md"

# Format only the owned command source.
fix:
    just --fmt
