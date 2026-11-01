import hashlib
import os
import platform
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts/macos/install.sh"
VERIFY = ROOT / "scripts/macos/verify.sh"
COMMON = ROOT / "scripts/lib/common.sh"


def test_herdr_control_flow_is_explicit_and_sc2015_is_not_suppressed() -> None:
    installer = INSTALL.read_text(encoding="utf-8")
    verifier = VERIFY.read_text(encoding="utf-8")
    common = COMMON.read_text(encoding="utf-8")
    block = installer.split("ensure_herdr() {", 1)[1].split("\ncask_app_path()", 1)[0]
    assert not re.search(r"\]\s*&&[^\n]*\|\|", block)
    assert "shellcheck disable=SC2015" not in installer
    assert "stat -f" not in installer
    assert "stat -c" not in installer
    assert "stat -f" not in verifier
    assert "stat -c" not in verifier
    assert common.count("rldyour::file_mode() {") == 1
    assert installer.count("rldyour::file_mode") == 3
    assert verifier.count("rldyour::file_mode") == 3
    for branch in (
        'if [ "$system" != Darwin ] || [ "$machine" != arm64 ]; then',
        'if [ ! -d "$root" ] || [ -L "$root" ]; then',
        'if [ ! -f "$target" ] || [ -L "$target" ] || [ ! -x "$target" ]; then',
        'if [ ! -f "$receipt" ] || [ -L "$receipt" ] || [ "$(cat "$receipt")" != "$expected_receipt" ]; then',
        'if [ "$root_mode" != 755 ] || [ "$target_mode" != 755 ] || [ "$receipt_mode" != 600 ]; then',
    ):
        assert branch in block


def _fixture_binary(path: Path, version: str = "0.9.5") -> str:
    path.write_text(f'#!/bin/sh\necho "herdr {version}"\n', encoding="utf-8")
    path.chmod(0o755)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_installer_function(
    home: Path,
    binary: Path,
    sha256: str,
    *,
    download_result: int = 0,
    machine: str = "arm64",
    mode_kernel: str = "",
    mode_output: str = "",
    mode_status: int = 0,
    uname_failure: str = "",
    calls_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    script = r'''
source "$1"
HERDR_VERSION=0.9.5
HERDR_MACOS_AARCH64_SHA256="$2"
HERDR_MACOS_AARCH64_URL=https://github.com/herdrdev/herdr/releases/download/v0.9.5/herdr-macos-aarch64
rldyour::download_verified_file() {
  printf 'download\n' >>"$RLDYOUR_TEST_CALLS"
  [ "$1" = "$HERDR_MACOS_AARCH64_URL" ] || return 91
  [ "$2" = "$HERDR_MACOS_AARCH64_SHA256" ] || return 92
  [ "$RLDYOUR_TEST_DOWNLOAD_RESULT" -eq 0 ] || return "$RLDYOUR_TEST_DOWNLOAD_RESULT"
  cp "$RLDYOUR_TEST_HERDR" "$3"
}
uname() {
  if [ "$1" = -s ]; then
    [ "$RLDYOUR_TEST_UNAME_FAILURE" != system ] || return 71
    printf '%s\n' Darwin
    return
  fi
  if [ "$1" = -m ]; then
    [ "$RLDYOUR_TEST_UNAME_FAILURE" != machine ] || return 72
    printf '%s\n' "$RLDYOUR_TEST_MACHINE"
    return
  fi
  command uname "$@"
}
if [ -n "$RLDYOUR_TEST_MODE_KERNEL" ]; then
  rldyour::_kernel_name() { printf '%s\n' "$RLDYOUR_TEST_MODE_KERNEL"; }
fi
stat() {
  printf 'stat' >>"$RLDYOUR_TEST_CALLS"
  printf ' <%s>' "$@" >>"$RLDYOUR_TEST_CALLS"
  printf '\n' >>"$RLDYOUR_TEST_CALLS"
  [ "$RLDYOUR_TEST_MODE_STATUS" -eq 0 ] || return "$RLDYOUR_TEST_MODE_STATUS"
  if [ -n "$RLDYOUR_TEST_MODE_OUTPUT" ]; then
    printf '%s\n' "$RLDYOUR_TEST_MODE_OUTPUT"
    return
  fi
  if [ "$RLDYOUR_TEST_MODE_KERNEL" = Darwin ]; then
    python3 -I - "$3" <<'PY'
import os, stat, sys
print(f"{stat.S_IMODE(os.lstat(sys.argv[1]).st_mode):03o}")
PY
    return
  fi
  command stat "$@"
}
RLDYOUR_DRY_RUN=0
ensure_herdr
'''
    if calls_file is None:
        calls_file = home.parent / "herdr-calls"
    return subprocess.run(
        ["bash", "-c", script, "macos-herdr-test", str(INSTALL), sha256],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{home / '.local/bin'}{os.pathsep}{os.environ['PATH']}",
            "RLDYOUR_TEST_HERDR": str(binary),
            "RLDYOUR_TEST_DOWNLOAD_RESULT": str(download_result),
            "RLDYOUR_TEST_MACHINE": machine,
            "RLDYOUR_TEST_MODE_KERNEL": mode_kernel,
            "RLDYOUR_TEST_MODE_OUTPUT": mode_output,
            "RLDYOUR_TEST_MODE_STATUS": str(mode_status),
            "RLDYOUR_TEST_UNAME_FAILURE": uname_failure,
            "RLDYOUR_TEST_CALLS": str(calls_file),
        },
    )


def test_macos_herdr_is_receipt_bound_and_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)

    first = _run_installer_function(home, binary, sha256)
    assert first.returncode == 0, first.stderr + first.stdout
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    receipt = target.parent / ".receipt"
    launcher = home / ".local/bin/herdr"
    assert target.read_bytes() == binary.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o755
    assert launcher.is_symlink()
    assert launcher.readlink() == target
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert receipt.read_text(encoding="utf-8") == (
        "# Managed by macos-ubuntu-bootstrap: macos-herdr-runtime-v1\n"
        "version=0.9.5\n"
        f"sha256={sha256}\n"
        "source=https://github.com/herdrdev/herdr/releases/download/v0.9.5/herdr-macos-aarch64\n"
    )

    inode = target.stat().st_ino
    second = _run_installer_function(home, binary, sha256)
    assert second.returncode == 0, second.stderr + second.stdout
    assert target.stat().st_ino == inode


def test_linux_second_apply_uses_only_gnu_stat_and_does_not_reinstall(tmp_path: Path) -> None:
    if platform.system() != "Linux":
        pytest.skip("real GNU stat lane runs on Linux")
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    calls = tmp_path / "calls"

    assert _run_installer_function(home, binary, sha256, calls_file=calls).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    before = (target.stat().st_ino, target.read_bytes(), target.stat().st_mode & 0o777)
    second = _run_installer_function(home, binary, sha256, calls_file=calls)

    assert second.returncode == 0, second.stderr + second.stdout
    assert (target.stat().st_ino, target.read_bytes(), target.stat().st_mode & 0o777) == before
    call_lines = calls.read_text(encoding="utf-8").splitlines()
    assert call_lines.count("download") == 1
    assert any(" <-c> <%a> <--" in line for line in call_lines)
    assert not any(" <-f> <%Lp>" in line for line in call_lines)


def test_macos_bsd_mode_branch_has_second_apply_parity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    calls = tmp_path / "calls"

    first = _run_installer_function(home, binary, sha256, mode_kernel="Darwin", calls_file=calls)
    assert first.returncode == 0, first.stderr + first.stdout
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    inode = target.stat().st_ino
    second = _run_installer_function(home, binary, sha256, mode_kernel="Darwin", calls_file=calls)

    assert second.returncode == 0, second.stderr + second.stdout
    assert target.stat().st_ino == inode
    call_lines = calls.read_text(encoding="utf-8").splitlines()
    assert call_lines.count("download") == 1
    assert any(" <-f> <%Lp>" in line for line in call_lines)
    assert not any(" <-c> <%a>" in line for line in call_lines)


def test_macos_herdr_preserves_divergent_managed_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    assert _run_installer_function(home, binary, sha256).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    target.write_bytes(b"tampered\n")

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert target.read_bytes() == b"tampered\n"
    assert "checksum diverged; preserved" in result.stderr + result.stdout


def test_macos_herdr_preserves_unmanaged_launcher(tmp_path: Path) -> None:
    home = tmp_path / "home"
    launcher = home / ".local/bin/herdr"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes(b"unmanaged\n")
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert launcher.read_bytes() == b"unmanaged\n"
    assert "unmanaged Herdr launcher exists; preserved" in result.stderr + result.stdout


def test_macos_herdr_wrong_hash_fails_before_publication(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    _fixture_binary(binary)
    wrong_hash = "0" * 64

    result = _run_installer_function(home, binary, wrong_hash)
    assert result.returncode != 0
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()
    assert "checksum diverged before publication" in result.stderr + result.stdout


def test_macos_herdr_wrong_reported_version_fails_before_publication(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary, version="0.7.5")

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()
    assert "reports 0.7.5, expected 0.9.5" in result.stderr + result.stdout


def test_macos_herdr_unavailable_asset_fails_without_partial_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)

    result = _run_installer_function(home, binary, sha256, download_result=22)
    assert result.returncode != 0
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()
    assert "asset is unavailable or failed checksum verification" in result.stderr + result.stdout


def test_macos_herdr_unsupported_architecture_fails_before_download(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)

    result = _run_installer_function(home, binary, sha256, machine="x86_64")
    assert result.returncode != 0
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()
    assert "no managed macOS artifact for Darwin/x86_64" in result.stderr + result.stdout


def test_macos_herdr_fails_closed_when_system_probe_errors(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    result = _run_installer_function(home, binary, sha256, uname_failure="system")
    assert result.returncode != 0
    assert "could not determine the operating system" in result.stderr + result.stdout
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()


def test_macos_herdr_fails_closed_when_architecture_probe_errors(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    result = _run_installer_function(home, binary, sha256, uname_failure="machine")
    assert result.returncode != 0
    assert "could not determine the architecture" in result.stderr + result.stdout
    assert not (home / ".local/share/rldyour/herdr/0.9.5").exists()


def test_macos_herdr_partial_receipt_fails_closed_without_repair(tmp_path: Path) -> None:
    home = tmp_path / "home"
    root = home / ".local/share/rldyour/herdr/0.9.5"
    root.mkdir(parents=True)
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    target = root / "herdr"
    target.write_bytes(binary.read_bytes())
    target.chmod(0o755)
    receipt = root / ".receipt"
    receipt.write_text(
        "# Managed by macos-ubuntu-bootstrap: macos-herdr-runtime-v1\nversion=0.9.5\n",
        encoding="utf-8",
    )
    receipt.chmod(0o600)
    before = receipt.read_bytes()

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert receipt.read_bytes() == before
    assert target.read_bytes() == binary.read_bytes()
    assert "receipt is missing or divergent; preserved" in result.stderr + result.stdout


def test_macos_herdr_divergent_permissions_fail_closed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    assert _run_installer_function(home, binary, sha256).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    target.chmod(0o775)

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert target.stat().st_mode & 0o777 == 0o775
    assert "permissions diverged; preserved" in result.stderr + result.stdout


def test_macos_herdr_mode_probe_error_fails_closed_without_reinstall(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    calls = tmp_path / "calls"
    assert _run_installer_function(home, binary, sha256, calls_file=calls).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    inode = target.stat().st_ino

    result = _run_installer_function(
        home, binary, sha256, mode_status=9, calls_file=calls
    )
    assert result.returncode != 0
    assert target.stat().st_ino == inode
    assert calls.read_text(encoding="utf-8").splitlines().count("download") == 1
    assert "stat failed to inspect permissions" in result.stderr + result.stdout


def test_macos_herdr_malformed_mode_fails_closed_without_reinstall(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    calls = tmp_path / "calls"
    assert _run_installer_function(home, binary, sha256, calls_file=calls).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    inode = target.stat().st_ino

    result = _run_installer_function(
        home, binary, sha256, mode_output="invalid", calls_file=calls
    )
    assert result.returncode != 0
    assert target.stat().st_ino == inode
    assert calls.read_text(encoding="utf-8").splitlines().count("download") == 1
    assert "malformed permission mode" in result.stderr + result.stdout


def test_macos_herdr_target_shape_branch_preserves_nonexecutable_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    assert _run_installer_function(home, binary, sha256).returncode == 0
    target = home / ".local/share/rldyour/herdr/0.9.5/herdr"
    target.chmod(0o644)

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert target.stat().st_mode & 0o777 == 0o644
    assert "target has an unsupported shape; preserved" in result.stderr + result.stdout


def test_macos_herdr_root_shape_branch_preserves_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    root = home / ".local/share/rldyour/herdr/0.9.5"
    root.parent.mkdir(parents=True)
    root.symlink_to(outside, target_is_directory=True)
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert root.is_symlink()
    assert "root has an unsupported shape; preserved" in result.stderr + result.stdout


def test_macos_herdr_additional_managed_root_path_fails_closed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "herdr-fixture"
    sha256 = _fixture_binary(binary)
    assert _run_installer_function(home, binary, sha256).returncode == 0
    root = home / ".local/share/rldyour/herdr/0.9.5"
    extra = root / "unexpected"
    extra.write_bytes(b"preserve me\n")

    result = _run_installer_function(home, binary, sha256)
    assert result.returncode != 0
    assert extra.read_bytes() == b"preserve me\n"
    assert "missing or additional paths; preserved" in result.stderr + result.stdout
