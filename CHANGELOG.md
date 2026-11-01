# Changelog

All notable changes to this module are documented here. Older release history
remains available in immutable Git tags.

## [Unreleased]

### Added

- CI callers now use the public OpenNetwork workflow engine while all public
  Ubuntu, ARM, macOS, and Windows jobs remain on standard GitHub-hosted runners.
  Run-id-unique concurrency preserves every queued and running evidence job,
  and the protected Python context names the reusable workflow's actual `uv`
  check identity.
- An ADR that names a test as its enforcement must name one that exists. ADR 0008
  now cites `test_no_script_grants_docker_group_membership` in place of the
  contract key nothing read — an improvement only while the name resolves, since
  a renamed test would leave the ADR asserting enforcement by something gone.
  `docs/adr/README.md` already held that a citation resolving to nothing is a
  defect; this checks the direction the contract-side test does not.

### Added

- Two safety policies the contract stated and nothing enforced now have tests.
  **No script may grant `docker` group membership** — it is root-equivalent, ADR
  0008 records that it must stay a manual act, and that ADR cited a contract key
  as though the key were the mechanism. No installer does it today; nothing would
  have noticed if one started. And **every apt install that touches a device
  carries `--no-upgrade`**, so setting up tools cannot silently upgrade packages
  the operator chose to keep. The two CI-fixture installers that build disposable
  environments are exempt by name, and a test fails if an exemption stops
  installing anything.

### Changed

- Refreshed the twenty pins `source-drift` reported behind on 2026-11-01. Each
  new artifact was downloaded, inspected and hashed here, and every digest also
  matches the publisher's own record: Node.js 24.19.0 -> 26.13.0 (the current
  LTS; `SHASUMS256.txt`, signed by a Node.js release key), uv 0.12.5 -> 0.13.6
  (per-asset `.sha256`), Bun 1.3.14 -> 1.4.4 (`SHASUMS256.txt`, signed by
  Robobun), Go 1.26.6 -> 1.27.3 (go.dev/dl JSON), gopls v0.23.0 -> v0.24.0
  (module checksum database; it requires Go 1.27), Rust 1.97.1 -> 1.99.1
  (channel 2026-10-15, signed by the Rust release key), Dart SDK 3.13.0 ->
  3.13.7 (dart-archive `.sha256sum`), Homebrew.pkg 6.0.17 -> 7.0.11 (signed by
  the pinned Developer ID Installer team), Herdr 0.8.0 -> 0.9.5, Telegram
  7.0.9 -> 7.3.3, Codex 0.147.0 -> 0.166.0 (npm `integrity`), osv-scanner
  2.5.0 -> 2.7.0, delta 0.19.2 -> 0.20.1, yq 4.53.3 -> 4.54.1, just 1.58.0 ->
  1.59.0, age 1.3.1 -> 1.3.2, ast-grep 0.45.1 -> 0.51.0, lazygit 0.64.1 ->
  0.66.2, difftastic 0.70.0 -> 0.72.0 and jaq 3.1.1 -> 3.1.2 (each matched
  against its release checksum file where one exists, and against the digest
  GitHub records for the release asset).

  Three upstream changes needed more than a new value:

  - **Node.js 25 removed corepack from the distribution.** The runtime receipt
    required `bin/corepack` to exist, so a 26.x install would have failed its
    own receipt. The installer and the verifier now record `node`, `npm` and
    `npx` only; corepack was never published to the managed PATH.
  - **Telegram renamed its Linux asset** from `tsetup.<version>.tar.xz` to
    `td-setup-linux-x64-<version>.tar.xz`; the archive layout is unchanged. The
    four desktop assets move to the v7.3.3 source commit `5c674f1f`. They and
    `InstallLauncher()` are byte-identical to v7.0.9, so installed icons stay
    valid. Upstream's own desktop entry now also lists `x-scheme-handler/ton`;
    the managed entry does not claim that scheme, since a pin refresh is not
    the place to change which links Telegram owns.
  - **difftastic now versions its asset names**, so the URLs changed shape.

  Homebrew.pkg 7 declares macOS 15.0 as its minimum, so a Mac on macOS 14
  can no longer bootstrap Homebrew from the pinned package. The macOS
  evidence lane already runs on `macos-15`.

### Removed

- The `safety` contract block and `verified_on`, and with them the exemption
  mechanism that recorded them (#88). `safety` stated twelve policies that no
  script and no test read. Ten were enforced elsewhere under different names;
  **two were not enforced at all**, which is why the tests above came first — a
  duplicate can be deleted, but a sole statement cannot.

  Binding the block instead was considered and rejected. The only binding
  available to a unit test is a text pattern over the implementation, and this
  release spent its effort removing exactly that from `dependency-check.yml`,
  where marker-matching could not fail for any mutation it existed to catch.
  Adding a second such layer to fix the first would not have been an improvement.

  `verified_on` was a bare date nothing wrote, read or checked; it could only
  ever become wrong, invisibly.
- Source drift escalates a source that is unreachable twice running. The
  tolerance alone cannot see this: one `unknown` out of twenty-five stays inside
  it forever, so a source that fails every single week looks exactly like one
  that was rate-limited once. The scheduled run now compares against the previous
  run's retained snapshot and fails by name on any pin that was `unknown` then
  and is `unknown` now.

  Best-effort by design. An expired or unreadable previous snapshot skips the
  comparison and says so, because refusing to check for drift is a failure about
  artifact retention rather than about pins.

## [3.1.0] - 2026-08-15

### Removed

- The two `cross-platform smoke` required status checks, and the workflow behind
  them. Both jobs ran the same block — that `README.md`, `LICENSE`, `NOTICE` and
  `VERSION` exist and `VERSION` is readable — and neither executed a line of this
  adapter, so a platform-specific regression passed both. The cost was two
  required contexts and two runner starts on every push, every pull request and a
  weekly schedule, for one assertion. That assertion moved into
  `bootstrap-validate` in the previous change: it already runs on both supported
  operating systems, already executes the installers in plan mode, and already
  has to be green to merge.

- `validate.yml`, which installed shellcheck and ripgrep and ran `validate.sh` on
  ubuntu — which `ci.yml`'s `bootstrap-validate` already does on **both** ubuntu
  and macOS. It was not a required context and proved nothing the required lane
  did not prove more widely.

### Added

- Ubuntu privileged operations are composable and fail closed (`#55`). A GUI
  session authorizes a narrowly scoped PolicyKit action; a terminal, headless or
  SSH session takes the TTY sudo path. The installer is never run opaquely under
  `pkexec`, no password travels through argv, environment, stdin, a file, an
  artifact or telemetry, and user-owned files stay owned by the invoking user.
  `scripts/ubuntu/privileged-helper.sh` executes only allowlisted operations with
  allowlisted arguments.

  Recut from current `main` rather than merged from the `#55` lineage. The three
  open pull requests on that line were one branch, not three options, and the
  latest carried a CI framework — a validation-path indirection, a script
  inventory, a locked test audit — alongside the privilege work. That framework
  is left behind: it broke the command `AGENTS.md` documents (`validate.sh`
  exited 2 unless invoked through a wrapper) and duplicated discovery `lint.sh`
  already does better. What came with the privilege layer is the two tools it
  genuinely uses: `shell_contract.py`, which the Ubuntu verifier calls at
  runtime, and `shell_function_harness.py`, which is how a 520-line root helper
  gets unit-tested at all.

### Fixed

- The privileged descendant supervisor, verified in containers rather than
  reviewed (`#64`). `timeout --foreground` does not bound the children of the
  command it runs — GNU documents exactly that — so `apt-get`, `dpkg` and `curl`
  started by the root helper outlived a launcher reporting timeout. The helper
  now owns its process group and escalates TERM → KILL over it.

  Four defects in that supervisor were invisible to `shellcheck` and `bash -n`,
  and a container caught each: an enumeration that counted its own pipeline;
  `kill -- -$$` when `$$` is 1, which POSIX defines as *every process the caller
  may signal* and a root helper in a container **is** PID 1; a group signal
  reaching the caller, so the KILL round killed the supervisor mid-cleanup after
  its traps were cleared; and a bare `wait` blocking on a job in another process
  group. Re-verified before this recut: five scenarios pass, and the old spelling
  still exits 137 — the supervisor killing itself.

- Firefox removal was rejected by the helper's own allowlist, after partial
  mutation, and was semantically inverted. `apt_install --purge firefox` neither
  passed `apt_arguments_allowed` nor removed anything — it is an install command.
  Removal is now its own `apt_remove` operation using `apt-get purge`, and the
  install channel was not widened to accommodate it.

- Four of the seven container cases covering these paths **did not pass, and
  nothing said so**: the module is gated on `RLDYOUR_CONTAINER_TESTS=1` and no
  workflow set it. The container was missing `python3` and `locales`. Two more
  need systemd as PID 1, which `docker run` cannot provide; they are skipped with
  that reason stated rather than left failing in a lane nobody runs.

### Fixed

- `evidence-gate` could not report for two whole classes of pull request, while
  the ruleset mirror declared it required. A pull request outside the workflow's
  `paths:` filter never ran the workflow at all, so the context never arrived —
  and a required context that never arrives leaves a pull request pending with
  nothing to click. A fork's pull request skipped every producer job, and the
  gate turned `skipped` into `exit 1`: not absent but **red**, for a contributor
  who had done nothing wrong and could do nothing about it.

  The path filter moved out of the trigger and into a `scope` job that always
  runs. `evidence-gate` now reports for every pull request that can reach `main`
  and states which of three cases it is — verified, out of scope, or a fork whose
  head cannot run the native lanes — each explained in the job summary rather
  than implied by a check that silently never appeared.

- The release lane treated a green `evidence-gate` as proof that evidence
  existed. With the gate reporting three outcomes, two of them are green without
  a single lane having run, so that inference would publish a fork-authored
  device change with no evidence at all. `evidence-gate` now writes a verdict
  naming the exact SHA and every `(lane, release, architecture)` it opened, and
  `release.yml` reads that instead of asking GitHub what a check concluded. An
  absent verdict is a refusal, with the reason and the remedy in the message.
  The verdict is written only after verification succeeds — a rejected run
  leaves none behind, and a test asserts it.

### Changed

- Raised the evidence sandbox matrix from `max-parallel: 2` to `6`. Each matrix
  job takes its own hosted runner, so the cap throttled nothing but this
  workflow: fourteen lanes two at a time is seven waves, which is why a run took
  25m35s against Bootstrap CI's 2m28s. It arrived as a conservative default in
  the first version of the file with no reason recorded, and a gate that is a
  ten-fold long pole is one people learn to merge around.

- Folded the repository-metadata contract into `bootstrap-validate`, which
  already runs on both supported operating systems and already has to be green
  to merge. `cross-platform.yml` spent two required status checks and two runner
  starts per push, pull request and weekly schedule proving that four files
  exist — the same block on both platforms, neither running a line of this
  adapter. The invariant is real and is kept; the ceremony around it is not.
  Removing the two now-redundant required contexts is a separate, reversible
  act against the live ruleset.

### Fixed

- Source drift was rendered and never acted on. `discover_source_drift.py`
  exited non-zero only for a `violation`; an ordinary `behind` result printed a
  row, uploaded a report and exited zero, so the scheduled run went green and the
  finding existed only inside a job summary nobody opens. `#66` — the issue this
  script exists to keep from recurring — was seven pins behind their upstreams,
  and this mechanism would have reported them exactly that quietly. A non-held
  `behind` now fails, and the message names the pin, both versions, and the two
  ways to resolve it.

  Unreachability keeps its exemption, because "GitHub rate-limited us" is not
  evidence that a pin drifted — but only up to a tolerance. Past it the run has
  not read enough to be evidence of anything and says so instead of reporting
  health. The residual limit is stated in the script rather than hidden: a single
  source unreachable every week stays inside the tolerance, and catching that
  needs state across runs the script deliberately does not keep.

  The workflow also ran discovery **twice**, once for `--markdown` and once for
  `--json` — two network snapshots taken minutes apart, free to disagree, each
  spending the rate limit the other needed. It now probes once and renders that
  snapshot with `--from-json`, so the summary, the artifact and the exit status
  all describe the same moment. The report is published before the job fails: a
  failure whose evidence was never uploaded is one people re-run rather than read.

### Changed

- Refreshed uv `0.12.4` → `0.12.5`, with both architecture digests computed from
  the downloaded artifacts. Found by the drift check above on its first real run,
  against sources the previous version would have reported as green.

### Fixed

- The module's own declared verification lane could not run on a clean host.
  `.gds/repository.yaml` began `verification.commands.test` with
  `uv venv --python 3.14`, and declared no prerequisite that provides uv — or
  zsh, which `tests/test_terminal_portability.py` needs because it runs the
  managed rc files through the shell that actually reads them. A host without uv
  failed before a virtualenv existed; a host with uv but without zsh installed
  cleanly and then failed inside pytest at a fixture. Both were reported to the
  control plane as the module failing its tests, and neither was. GitHub CI
  passed either way, because the reusable Python lane installed exactly what the
  anchor omitted — so the declaration written to reproduce CI was the one place
  that did not.

  `scripts/ci/setup-test-env.sh` now owns the environment, and both
  `.github/workflows/pytest.yml` and the anchor call it. It is declared as
  `verification.commands.bootstrap`, a GDS prerequisite lane that runs first and
  is deliberately not in `required`: a module is not verified by having been
  prepared, and its failure states that the check could not be attempted rather
  than that the module failed it.

  Running the declared lane on a bare `ubuntu:24.04` container found four
  prerequisites no amount of reading would have: the suite drives `git`,
  `ssh-keygen`, `gpg` and `python3` through `subprocess`, and a GitHub runner
  ships all of them — which is precisely why their absence from the anchor could
  not fail anywhere. It also found that `curl` installed with
  `--no-install-recommends` cannot complete a TLS handshake without
  `ca-certificates`, surfacing as a certificate error on a pinned download.

  uv itself is acquired the way this repository acquires every pinned artifact:
  the exact version and SHA-256 the contract already states for a device, from a
  fixed versioned URL, verified before execution.

- The documented way to validate a change was the one the anchor exists to rule
  out. `README.md`, `AGENTS.md` and `docs/install.md` all instructed
  `python3 -m pytest`, which passes only where pytest already happened to be
  installed, long after CI had stopped using it. A reader following the guide ran
  something the repository had already established proves nothing.

### Added

- One statement of what protects `main`. The contexts the branch enforces were
  written down three times — the live ruleset, `.github/rulesets/branch-main.json`
  and `.gds/repository.yaml` — and nothing compared them.
  `scripts/ci/check_required_contexts.py` does, on every pull request, against
  the live rules API. The `.gds` list in particular was bound by nothing at all:
  it was accurate, and nothing would have reported it if it stopped being, which
  is how `#79` found it unset by reading it rather than by a check failing.

- A dependency gate that checks dependencies.
  `scripts/ci/check_ci_tool_parity.py` compares the tool versions and digests CI
  runs against the ones the contract pins for a device, proves every workflow
  download names a fixed version and verifies a digest, and proves nothing
  reaches a shell straight from the network. `validate.sh` and the required
  `Dependency pin checks` both run it, so one implementation answers for both.

### Fixed

- The ruleset mirror declared a check that could not report, and shipped a
  command to apply it. `branch-main.json` listed `evidence-gate` as a pending
  proposal, `.github/rulesets/README.md` explained the delta with *"`evidence-gate`
  runs on `pull_request` and on pushes to `main` … so making it required does not
  introduce a check that cannot report"*, and gave an administrator a
  ready-to-paste `gh api --method PUT` to do it. That justification stopped being
  true when `#77` closed `#75` by making `pull_request` the only trigger. A pull
  request touching none of the workflow's `paths:` never receives the context,
  and a fork's pull request skips every producer job, which `evidence-gate` turns
  into a hard failure rather than an absence — so running the documented command
  would have made both classes permanently unmergeable. The mirror is now a
  mirror: it may not declare a check the live ruleset does not enforce, and the
  test that used to pin `evidence-gate` into it now keeps it out until it can
  report for every pull request that can reach `main`.

- The required merge gate linted with whatever was newest.
  `raven-actions/actionlint` was pinned to a commit, but that action defaults its
  tool version to `latest` and verifies no checksum, so the action SHA bound the
  wrapper and nothing bound the bytes — in the one check that must be green to
  merge, and again in the release lane. The checksum-bound implementation already
  existed and was already what `actionlint.yml` called, but that workflow was not
  a required context: the repository ran the strong lane advisorily and the weak
  lane as its gate. `ci.yml` now calls the checksum-bound reusable with the
  contract's version and digest, `release.yml` reads both out of the contract at
  run time the way it already did for uv, and the duplicate workflow is deleted.

- CI and a developer's machine scanned with different programs. The contract
  pinned OSV-Scanner `2.5.0` while the caller passed no version and inherited the
  pinned provider's `2.4.0` default, whose scanning pipeline is not the same one.
  The caller now passes the contract's version and digest — the provider
  downloads `osv-scanner_linux_amd64`, which is the asset that digest covers.

- `Dependency pin checks` could not fail for anything it existed to catch. It
  searched the installers for variable and function *names*; every one of them
  survives replacing the version, the digest and the URL it holds. Its
  network-pipe guard was `"curl -fsSL https://" in data and "| sh" in data`, a
  test on the whole file, so two unrelated lines satisfied it while
  `wget … | sh` did not. The same weakness lived in `validate.sh` as an `rg`
  sweep that failed the build on a comment *describing* the construct. Both are
  replaced by one parser-based check that knows code from documentation, names
  every shell, and for Python looks for the actual handover — `os.system`, or
  `subprocess` with `shell=True` — rather than for the words.

- The runner-routing test skipped the callers most likely to be wrong. It only
  required an explicit hosted runner from a caller that already passed some
  input, so deleting a caller's entire `with:` block — the single edit that most
  obviously hands runner selection back to the pinned provider's default —
  removed it from the test's attention instead of failing it. This repository is
  public, so `pull_request` runs untrusted fork code, and several of those
  reusables default `runner` to the estate's self-hosted label.

### Added

- Weekly discovery of pin drift against official sources. `#66` found seven pins
  behind their upstreams, one a whole minor version, and nothing in the
  repository would have said so — Dependabot covers the GitHub Actions
  ecosystem, and every pin here is a direct upstream artifact it cannot see.
  `scripts/ci/discover_source_drift.py` reads first-party release metadata for
  all twenty-five and reports where each stands. It is discovery only: it holds
  no write permission, opens no pull request, downloads no install artifact, and
  a test asserts it cannot open a file for writing. A refresh stays a reviewed
  change with digests computed from the downloaded artifact. A source that
  contradicts the contract — a missing architecture, a mutable download URL,
  metadata in an unexpected shape — fails the run; a source that is merely
  unreachable is reported as `unknown` and does not, because a report that fails
  on a rate limit is a report people mute.

- Ubuntu 26.04 hosted evidence. Every sandbox lane now runs on both supported
  releases, and the evidence matrix expands per `(lane, release, architecture)`
  so a 24.04 result can never stand in for its 26.04 twin — the artifact count
  goes from 13 to 21 and the gate keys on the release. The container's release
  is a lane property rather than the runner's, so this needs no dependency on
  the `ubuntu-26.04` runner labels, which exist but are public preview and would
  queue indefinitely rather than fail if withdrawn. Each artifact records the
  release it proved and the runner's stability class.

### Fixed

- Stopped superseded evidence runs holding the queue. `evidence-gate` proves
  the artifacts belong to one exact SHA and the release gate resolves a
  candidate through the head whose gate is green, so a run for an older head
  answers a question nobody is asking. With the lane count doubled by 26.04
  coverage and `max-parallel: 2` serialising the sandbox matrix, letting each
  push queue a full run behind the one it invalidated turned two quick
  corrections into two hours of runner time.
- Key-only SSH hardening no longer refuses a valid `authorized_keys` on Ubuntu
  26.04. The preflight asked `test -r` through `sudo`, and coreutils 9.5
  answers `-r` via `access(2)` without granting root its usual override, so a
  correct mode-0600 key file owned by the target user read as unreadable. On
  24.04 the same probe returned true. Measured as root with full capabilities
  on one file: external `test -r` gave 0 on 24.04 and 1 on 26.04, while the
  shell builtin and `test -e` agreed on both. Readability is now answered by
  opening the file, which depends on no coreutils policy about what root may
  read and reads no key material. This was a refusal on a real server, not a
  test artifact, and only the release matrix surfaced it.

- Made the sandbox readiness check release-portable. It waited for systemd to
  report `running`, but on 26.04 `systemd-modules-load.service` fails inside a
  container — it cannot load kernel modules — so systemd settles `degraded` and
  never reaches `running`. A correct 26.04 lane would have timed out after 30
  attempts for a reason unrelated to the bootstrap. Readiness now accepts either
  settled state and records a degraded boot with its failed units in the
  evidence, rather than either rejecting it or tolerating it silently; the
  facility assertions the lane actually depends on still have to hold.

### Security

- Removed `workflow_dispatch` from `platform-evidence`, leaving `pull_request`
  as its only trigger. Those jobs check out a contributor's exact head SHA and
  execute it — they run the bootstrap with `sudo` — so any trigger able to write
  the default-branch Actions cache scope made this a cache-poisoning path:
  unreviewed code running where it can plant an entry a privileged workflow
  later restores. CodeQL reported four such alerts against this file, all of
  them predating the evidence-gate work. A `pull_request` run's cache scope is
  the pull request's own branch, which is the isolation the finding asks for.
  Nothing needed the trigger: re-running a lane still works through re-run-jobs
  on the original run, and the release gate proves a candidate's tree is
  identical to a head whose `evidence-gate` is green rather than asking for a
  fresh run. A test now binds the trigger set and rejects a job condition that
  re-admits one.

### Added

- Added a canonical machine-readable clean-system support/evidence matrix and
  made hosted evidence fail closed when a required capability is unproven or a
  runner/lane architecture is outside the declared proof boundary.

### Changed

- Refreshed every pinned upstream source against first-party release metadata
  and recomputed each digest from the downloaded artifact: Node.js
  24.18.0 -> 24.19.0, uv 0.11.30 -> 0.12.4, Homebrew.pkg 6.0.9 -> 6.0.17,
  Go 1.26.5 -> 1.26.6, Dart SDK 3.12.2 -> 3.13.0, osv-scanner 2.4.0 -> 2.5.0,
  and ast-grep 0.45.0 -> 0.45.1. Bun 1.3.14, gopls v0.23.0, Rust 1.97.1,
  Herdr 0.8.0, Telegram 7.0.9, RustDesk 1.4.9, Codex 0.147.0, the Chrome
  signing key, both vendor AI installer scripts, and the remaining eight
  pinned source tools were re-downloaded and confirmed unchanged. The macOS
  Dart floor stays at 3.12 on purpose: `dart-sdk` is a rolling Homebrew
  formula whose determinism class is decided in #63, and raising the floor
  before that decision would fail verification on a host whose already
  installed formula the installer deliberately preserves.

### Added

- ADR 0010 takes the macOS package determinism decision the repository had
  drifted into without recording: the Homebrew formula and cask sets are
  intentionally rolling, and anything whose exact bytes matter is installed from
  an immutable upstream artifact instead, as Herdr already was. Every macOS
  package now carries a determinism class in `macos_package_determinism`, bound
  to the installer's arrays by tests, so a package cannot be added without one.
  The record also fixes what provenance metadata may claim -- only facts a
  resolver can establish on the machine it runs on -- and names each field it may
  not claim together with the reason, so `executable_sha256` cannot be re-added
  for a rolling formula whose digest moves on every homebrew-core rebuild.

### Fixed

- Made `evidence-gate` prove something. It read four `needs.*.result` values and
  never opened an artifact, and the runtime check inside `finalize_evidence`
  re-tested an invariant the matrix validator already refused statically, so it
  could never fire. REQUIRED capabilities now declare the steps a lane must
  record; the lane script appends a step name only after the command that proves
  it returns, so a successful lane that skipped a step fails. The gate downloads
  all thirteen artifacts and requires the payload count, the (lane, architecture)
  set, each result, each capability list, each observation ledger, each
  `not_proven` list and each SHA to hold. `evidence-gate` is now in the
  checked-in required-check projection.
- Made release preparation verify both mandatory gates before publication, on
  every trigger including a tag push, which previously published without asking
  about hosted evidence at all. `evidence-gate` reports against a PR head rather
  than the merge commit that lands, so rather than give `platform-evidence` a
  default-branch trigger — it checks out a contributor's head SHA and runs it,
  and a default-branch trigger would hand that write access to the default-branch
  Actions cache scope — the release gate proves the candidate's tree is identical
  to the head whose `evidence-gate` is green. `main` already guarantees that
  through `strict_required_status_checks_policy`, and the gate verifies it rather
  than assuming it. `platform-evidence`'s `sha` dispatch input was removed for the
  same reason: it accepted any commit reachable from the repository, including a
  fork's PR head under `refs/pull/*`.

- Connected the device integrity receipt to the lifecycle it documents.
  `scripts/device_integrity.py` had no runtime caller, and its
  one-owner-per-harness check read a contract key that did not exist, so it
  could not report drift — while ADR 0007 and `AGENTS.md` described receipts as
  a working mechanism. Apply now writes the receipt after strict verification
  passes, `verify.sh --strict` reads it back and compares the device to it
  exactly, and `harnesses.detection` in the contract gives the ownership check
  something to check: `codex` is enforced to the prefix this repository installs
  it into, and a second copy from a package-manager global is reported by name.
  `claude-code` and `grok-build` are observe-only because their vendor installer
  owns the target. Exact-version assertions are now scoped to the platforms the
  contract actually pins, so a macOS device is no longer reported as drifting
  from `ubuntu_*` fields Homebrew cannot honour.

- Closed the macOS/Ubuntu interactive tool boundary. `templates/terminal/zshrc`
  guards every alias with `command -v`, so a tool only one platform installs
  degrades silently rather than erroring. Ubuntu now installs `eza`, `lazygit`,
  `difft` and `jaq` as pinned source tools, macOS gains `btop`, `duf` and
  `hexyl`, and six guards for `dust`, `dua`, `procs`, `doggo`, `gping` and
  `viddy` were removed because no profile has ever installed them on either
  platform. `duckdb`, `jnv`, `xh` and `yazi` stay macOS-only, each with its
  reason recorded. The contract now owns the boundary as `terminal_tools`, and
  tests bind the zshrc guard set to it and it to both installers, so a future
  addition cannot become a silent no-op. The test that previously asserted the
  guards existed carried a literal list including all six phantom tools; it now
  derives that list from the contract.

- Bound every version the Ubuntu verifier asserts to the contract. The
  verifier checks uv with an escaped-dot regex, so it was the one pin a
  literal refresh could not reach: the installer and the verifier could
  publish and demand different versions, and a strict verify would then fail
  on a correctly installed host. Two parity tests now prove the verifier
  asserts the contract's versions and asserts no others.
- Repaired Ubuntu GUI strict verification, which could not pass in any state:
  the Chrome signing-key check was written inside a double-quoted command
  substitution, so its escaped quotes reached `awk` verbatim and the verifier
  aborted under `set -o pipefail`. Vendor-key identity is now one library
  primitive shared by the Chrome and Docker installers and verifiers, and it
  rejects a keyring carrying a second primary key.
- Stopped a failed user tool stranding the layers behind it. Herdr is a user
  tool on every profile, so one divergent Herdr left a server without Docker,
  without the vendor AI CLIs and without verification. Optional-layer failures
  are now reported once, after every layer has been attempted.
- Made plan mode read-only. A plan created `~/.local/bin`, `~/.bun/install/global`
  and `~/.cache/uv` on every Ubuntu profile, and reported a Docker daemon health
  verdict it had never obtained because the probe was routed through the
  dry-run helper.
- Verified every tool the Ubuntu installer publishes. starship, atuin, carapace,
  semgrep, ty, biome, oxlint, markdownlint-cli2, prettier,
  ansible-language-server and gh-actions-language-server were installed on every
  profile and checked by nothing.
- Aligned the desktop layer with its contract: desktop entries follow the
  GUI-capable profile set, the GUI font is a declared package group rather than
  an inline literal, and every managed launcher guards its own program with
  `TryExec`.
- Made the required plan lane exercise the full plan path instead of argument
  parsing alone, and fail if a plan writes to the home directory it describes.
- Removed a Dependabot ecosystem pointing at a directory deleted with the
  browser layer, replaced the release lane's unpinned `pip` install with the
  contract-pinned, SHA-256-verified `uv` path used everywhere else, and repaired
  citations to the two decision records retired in 3.0.0.

## [3.0.1] - 2026-08-13

### Fixed

- Made Herdr permission verification deterministic across BSD/macOS and GNU/Linux
  test hosts, with explicit fail-closed shell control flow and repeat-apply coverage.
- Installed the exact receipt-bound Herdr 0.8.0 macOS release artifact instead
  of accepting the older mutable Homebrew formula.
- Published terminal plugins from verified pinned Git commit trees instead of
  exposing mutable checkout metadata to the executable Antidote source layer.
- Made Ubuntu server verification and device receipts prove the complete
  contract 3.0.1 source-tool set.
- Restricted Ubuntu GUI apply to amd64 because required vendor applications do
  not publish compatible Linux ARM64 builds; ARM64 no-GUI profiles remain
  supported.
- Synchronized release metadata and architecture policy across the contract,
  implementation, tests, ADRs, and operator documentation.

- Updated Herdr to `0.8.0`, with verified macOS and Linux x86_64/aarch64
  installation and verification.
- Updated Telegram Desktop to the official `7.0.9` release and pinned its Linux
  x86_64 archive and source assets to tag commit `a1e89e1f`.
- Declared Herdr on macOS and every Ubuntu profile and Telegram on supported GUI
  targets.

## [3.0.0] - 2026-08-13

### Changed

- Standardized the active AI CLI set on official Codex CLI, Claude Code, and
  Grok Build distributions, with verified installer inputs and `cx`, `cl`, and
  `gk` unrestricted-mode launchers.
- Made Google Chrome stable the sole installed browser.
- Added ChatGPT, Claude, RustDesk, Telegram, Ghostty, and cmux to the applicable
  macOS GUI composition; added Chrome, RustDesk, Telegram, GNOME integration,
  and Firefox removal to Ubuntu GUI.
- Extended Go, Rust, Dart, language servers, terminal tooling, and local static
  verification to the supported profile matrix while retaining explicit
  execution-policy boundaries.
