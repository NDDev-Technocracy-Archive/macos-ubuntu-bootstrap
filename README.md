# rldyour macOS and Ubuntu bootstrap

Plan-first bootstrap for Apple Silicon macOS, Ubuntu 24.04/26.04 desktops, and
headless Ubuntu servers. The current contract is `3.1.0`.

## Profiles

| Target | GUI | Docker | Policy |
|---|---|---|---|
| macOS `desktop` | optional | none | source analysis and local checks |
| Ubuntu `desktop` | optional | none | source analysis and local checks |
| Ubuntu `desktop-builds` | optional | rootful | local builds and tests |
| Ubuntu `server` | none | rootful by default | production server/container host |

Every profile receives the zsh-first terminal environment, source-analysis
tools, language servers, Codex CLI, Claude Code, Grok Build, and the launchers
`cx`, `cl`, and `gk`. The interactive terminal tools the shell template binds
aliases to are the same set on both platforms — `config/rldyour-contract.json`
declares them under `terminal_tools.shared`, and a test fails if either
installer stops publishing one. Four macOS tools are deliberately outside that
set (`duckdb`, `jnv`, `xh`, `yazi`); the contract records why for each. These launchers select each vendor's explicit unrestricted
mode; use them only on machines and repositories you trust.

GUI workstations install Google Chrome stable. macOS GUI additionally installs
Ghostty, cmux, ChatGPT, Claude, RustDesk, and Telegram. Ubuntu GUI installs
Chrome, RustDesk, Telegram, desktop integration, and removes Firefox. Headless
profiles do not install GUI applications. Herdr is installed and verified on
macOS and every Ubuntu profile, including headless desktops and servers.
Ubuntu GUI is supported on amd64; ARM64 remains supported with `--no-gui`
because Google and Telegram publish no compatible Linux ARM64 applications.

Desktop source hosts include Node, Python, LLVM/clangd, Go/gopls, Rust with
rust-analyzer, Dart with its analysis server, TypeScript, YAML, Bash, Dockerfile,
HTML/CSS/JSON, TOML, Markdown, Terraform, CMake, GitHub Actions, and Ansible
analysis tooling. The `desktop` profile does not authorize project execution or
deployment. Use `desktop-builds` for local Docker builds/tests.

The Ubuntu server profile installs and verifies a server baseline, Docker,
unattended security updates, and time synchronization. UFW, key-only SSH, and
Fail2ban remain independent explicit opt-ins to prevent accidental lockout.

## Usage

```bash
# Plans (default)
bash scripts/bootstrap.sh --platform macos
bash scripts/bootstrap.sh --platform macos --no-gui
bash scripts/bootstrap.sh --platform ubuntu --profile desktop
bash scripts/bootstrap.sh --platform ubuntu --profile desktop-builds
bash scripts/bootstrap.sh --platform ubuntu --profile server

# Apply
bash scripts/bootstrap.sh --platform macos --apply
bash scripts/bootstrap.sh --platform ubuntu --profile desktop --apply
bash scripts/bootstrap.sh --platform ubuntu --profile desktop-builds --apply
bash scripts/bootstrap.sh --platform ubuntu --profile server --apply
```

Supported recovery skips are `--skip-system`, `--skip-ai`, `--skip-lsps`, and
`--skip-checks`. Authentication is always an owner handoff:

```bash
bash scripts/auth-handoff.sh show
bash scripts/auth-handoff.sh check
```

## Validation

`just check` runs build-free shell, source-contract and workflow checks.
`just verify` retains the original configured history/diff secret scan;
`just audit-dependencies` and `just links` preserve the independent source
security/link jobs. Their shared caller selection is in the workflows. Native
pytest, platform plans/container evidence and release checks remain separate
required obligations; source commands perform no host bootstrap or installation.
The dependency scan also compares its actual OSV identity with the existing
installer contract. A newer prepared scanner is a visible compatibility/update
input, not permission to silently change the contract or downgrade the SDK.

```bash
bash scripts/ci/setup-test-env.sh
bash scripts/ci/lint.sh
bash scripts/ci/validate.sh
.venv/bin/python -m pytest
```

`setup-test-env.sh` establishes what the suite needs — a real zsh, and the
hash-locked Python 3.14 environment — and is idempotent. `python3 -m pytest`
passes only where pytest already happened to be installed, and the
terminal-portability suite asserts against a real zsh rather than skipping
without one.

Real platform behavior must also be verified on the corresponding macOS or
Ubuntu host; container checks are not evidence for launchd, systemd, GNOME,
SSH, firewall, Docker daemon, or macOS application behavior.

The machine-readable support and proof boundary is
[`config/support-evidence-matrix.json`](config/support-evidence-matrix.json).
It distinguishes required core behavior from optional real-host capabilities
and prevents hosted or container evidence from being promoted to a stronger
tier. A successful evidence lane may contain typed `NOT_PROVEN` observations
only for optional capabilities; every required capability must be `PROVEN`.
See the [support/evidence reference](docs/reference/support-evidence.md) for the
typed tiers, current hosted coverage, and explicit real-host gaps.
