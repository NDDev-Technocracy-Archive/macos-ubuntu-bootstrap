"""Telegram runtime policy and desktop launcher regressions."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts/ubuntu/install.sh"
MARKER = "# Managed by macos-ubuntu-bootstrap: telegram-external-updater-v1"


def _run_policy(home: Path, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["RLDYOUR_DRY_RUN"] = "1" if dry_run else "0"
    env["RLDYOUR_GUI_ENABLED"] = "1"
    env.pop("XDG_DATA_HOME", None)
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"\nrldyour::ubuntu::install_telegram_update_policy',
            "_",
            str(INSTALL),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_desktop_entries(home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["RLDYOUR_DRY_RUN"] = "0"
    env["RLDYOUR_GUI_ENABLED"] = "1"
    env.pop("XDG_DATA_HOME", None)
    return subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"\n'
                'install_desktop_entries\n'
                'rldyour::ubuntu::retire_telegram_legacy_managed_entry'
            ),
            "_",
            str(INSTALL),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_desktop_assets(
    home: Path, *, dry_run: bool = False
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["RLDYOUR_DRY_RUN"] = "1" if dry_run else "0"
    env["RLDYOUR_GUI_ENABLED"] = "1"
    env.pop("XDG_DATA_HOME", None)
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"\nrldyour::ubuntu::install_telegram_desktop_assets',
            "_",
            str(INSTALL),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_retire_integrations(
    home: Path, *, dry_run: bool = False
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["RLDYOUR_DRY_RUN"] = "1" if dry_run else "0"
    env.pop("XDG_DATA_HOME", None)
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"\nrldyour::ubuntu::retire_telegram_generated_integrations',
            "_",
            str(INSTALL),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _managed_telegram(home: Path) -> tuple[Path, Path]:
    real = home / ".local/share/rldyour/telegram/7.3.3/Telegram/Telegram"
    real.parent.mkdir(parents=True)
    real.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    real.chmod(0o755)
    launcher = home / ".local/bin/telegram-desktop"
    launcher.parent.mkdir(parents=True)
    launcher.symlink_to(real)
    return launcher, real


def test_telegram_policy_lists_launcher_and_receipt_bound_binary(tmp_path: Path) -> None:
    launcher, real = _managed_telegram(tmp_path)
    result = _run_policy(tmp_path)
    assert result.returncode == 0, result.stderr

    policy = (
        tmp_path
        / ".local/share/TelegramDesktop/externalupdater.d/macos-ubuntu-bootstrap"
    )
    assert policy.read_text(encoding="utf-8").splitlines() == [
        MARKER,
        str(launcher),
        str(real),
    ]
    assert policy.stat().st_mode & 0o777 == 0o644

    again = _run_policy(tmp_path)
    assert again.returncode == 0, again.stderr
    assert "already current" in again.stdout


def test_telegram_policy_preserves_unmanaged_file(tmp_path: Path) -> None:
    _managed_telegram(tmp_path)
    policy = (
        tmp_path
        / ".local/share/TelegramDesktop/externalupdater.d/macos-ubuntu-bootstrap"
    )
    policy.parent.mkdir(parents=True)
    policy.write_text("user-owned\n", encoding="utf-8")

    result = _run_policy(tmp_path)
    assert result.returncode != 0
    assert "unmanaged Telegram updater policy differs" in result.stdout
    assert policy.read_text(encoding="utf-8") == "user-owned\n"


def test_telegram_policy_dry_run_needs_no_installed_binary(tmp_path: Path) -> None:
    result = _run_policy(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert "Telegram external-updater policy" in result.stdout
    assert not (tmp_path / ".local/share/TelegramDesktop").exists()


def test_user_tool_install_attempts_telegram_after_an_earlier_failure(
    tmp_path: Path,
) -> None:
    calls = tmp_path / "calls"
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["RLDYOUR_DRY_RUN"] = "0"
    env["CALLS_FILE"] = str(calls)
    env["RLDYOUR_GUI_ENABLED"] = "1"
    result = subprocess.run(
        [
            "bash",
            "-c",
            """source "$1"
ensure_pinned_source_tool() {
  printf '%s\n' "${1%%;*}" >>"$CALLS_FILE"
  [ "${1%%;*}" != herdr ]
}
install_user_tools
""",
            "_",
            str(INSTALL),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert calls.read_text(encoding="utf-8").splitlines() == ["herdr", "telegram"]



def test_telegram_favorite_migrates_before_legacy_launchers_are_retired() -> None:
    source = INSTALL.read_text(encoding="utf-8")
    main = source.split("main() {", 1)[1]
    configure = main.index(
        "rldyour::ubuntu::configure_telegram_desktop_integration"
    )
    retire_legacy = main.index(
        "rldyour::ubuntu::retire_telegram_legacy_managed_entry"
    )
    retire_generated = main.index(
        "rldyour::ubuntu::retire_telegram_generated_integrations"
    )
    assert configure < retire_legacy
    assert configure < retire_generated


def test_telegram_desktop_assets_are_pinned_to_the_v733_source_commit() -> None:
    contract = json.loads(
        (ROOT / "config/rldyour-contract.json").read_text(encoding="utf-8")
    )
    desktop = contract["desktop_entries"]["telegram"]
    installer = INSTALL.read_text(encoding="utf-8")

    assert desktop["upstream_source_commit"] == (
        "5c674f1f6a0f6ace55b67f8bc295138680fe588b"
    )
    assert len(desktop["icon_assets"]) == 4
    for asset in desktop["icon_assets"]:
        assert asset["source_url"] in installer
        assert asset["sha256"] in installer
        assert asset["target"].split("${HOME}/.local/share/", 1)[1] in installer


def test_telegram_desktop_asset_dry_run_does_not_download(tmp_path: Path) -> None:
    result = _run_desktop_assets(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("[DRY-RUN] install pinned Telegram desktop asset") == 4
    assert not (tmp_path / ".local/share/icons").exists()


def test_divergent_telegram_desktop_asset_is_preserved(tmp_path: Path) -> None:
    icon = (
        tmp_path
        / ".local/share/icons/hicolor/256x256/apps/org.telegram.desktop.png"
    )
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"user-owned-icon")

    result = _run_desktop_assets(tmp_path)
    assert result.returncode != 0
    assert "Telegram desktop asset diverged; preserved" in result.stdout
    assert icon.read_bytes() == b"user-owned-icon"


def test_managed_telegram_v1_desktop_entry_is_backed_up_and_migrated(
    tmp_path: Path,
) -> None:
    applications = tmp_path / ".local/share/applications"
    applications.mkdir(parents=True)
    legacy_target = applications / "telegram.desktop"
    target = applications / "org.telegram.desktop.desktop"
    legacy = """[Desktop Entry]
Type=Application
Name=Telegram Desktop
Comment=New era of messaging
# Managed by macos-ubuntu-bootstrap: desktop-entry-telegram-v1
Exec=telegram-desktop -- %U
Icon=telegram
Terminal=false
StartupWMClass=TelegramDesktop
Categories=Chat;Network;InstantMessaging;
MimeType=x-scheme-handler/tg;
Keywords=tg;chat;im;messaging;messenger;
"""
    legacy_target.write_text(legacy, encoding="utf-8")

    result = _run_desktop_entries(tmp_path)
    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == (
        ROOT / "templates/desktop/org.telegram.desktop.desktop"
    ).read_text(encoding="utf-8")
    assert not legacy_target.exists()

    backups = list(
        (tmp_path / ".local/share/rldyour/backups/desktop-entries").glob(
            "retired-telegram.*/telegram.desktop"
        )
    )
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == legacy


def test_generated_telegram_integrations_are_retired_recoverably(
    tmp_path: Path,
) -> None:
    launcher, _real = _managed_telegram(tmp_path)
    identity = "org.telegram.desktop._0123456789abcdef0123456789abcdef"
    desktop = tmp_path / f".local/share/applications/{identity}.desktop"
    service = tmp_path / f".local/share/dbus-1/services/{identity}.service"
    desktop.parent.mkdir(parents=True)
    service.parent.mkdir(parents=True)
    desktop.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                f"TryExec={launcher}",
                f"Exec={launcher} -- %U",
                "DBusActivatable=true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    service.write_text(
        "\n".join(
            [
                "[D-BUS Service]",
                f"Name={identity}",
                f"Exec={launcher}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_retire_integrations(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not desktop.exists()
    assert not service.exists()
    backup_dirs = list(
        (tmp_path / ".local/share/rldyour/backups/telegram-integrations").glob(
            "generated.*"
        )
    )
    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / desktop.name).is_file()
    assert (backup_dirs[0] / service.name).is_file()


def test_fresh_dry_run_needs_no_installed_telegram_launcher(tmp_path: Path) -> None:
    result = _run_retire_integrations(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert "managed Telegram launcher is unavailable" not in result.stdout


def test_divergent_generated_telegram_integration_is_preserved(
    tmp_path: Path,
) -> None:
    _managed_telegram(tmp_path)
    identity = "org.telegram.desktop._0123456789abcdef0123456789abcdef"
    desktop = tmp_path / f".local/share/applications/{identity}.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.write_text("user-owned\n", encoding="utf-8")

    result = _run_retire_integrations(tmp_path)
    assert result.returncode != 0
    assert "diverged; preserved" in result.stdout
    assert desktop.read_text(encoding="utf-8") == "user-owned\n"


# --------------------- GIO userapp launchers (v3 migration) ---------------------
#
# GIO writes userapp-<Name>-<6 chars>.desktop when something picks a custom
# application for a scheme. On the estate's own desktop two of these survived
# the v3 migration: they sit in [Added Associations], so they do NOT shadow the
# default handler, but they invoke `telegram-desktop -- %u` without the
# `env QT_QPA_PLATFORM=xcb` wrapper the managed entry exists for.


def _managed_launcher(home: Path) -> None:
    binary = home / ".local/share/rldyour/telegram/7.3.3/Telegram/Telegram"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    launcher = home / ".local/bin/telegram-desktop"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.symlink_to(binary)


def _userapp(home: Path, suffix: str, *, exec_line: str, comment: str) -> Path:
    applications = home / ".local/share/applications"
    applications.mkdir(parents=True, exist_ok=True)
    entry = applications / f"userapp-Telegram Desktop-{suffix}.desktop"
    entry.write_text(
        "[Desktop Entry]\nEncoding=UTF-8\nVersion=1.0\nType=Application\n"
        f"NoDisplay=true\n{exec_line}\nName=Telegram Desktop\n{comment}\n",
        encoding="utf-8",
    )
    return entry


def _run_userapp_retirement(home: Path, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["RLDYOUR_DRY_RUN"] = "1" if dry_run else "0"
    env.pop("XDG_DATA_HOME", None)
    env.pop("XDG_CONFIG_HOME", None)
    return subprocess.run(
        ["bash", "-c", 'source "$1"\nrldyour::ubuntu::retire_telegram_userapp_entries', "_", str(INSTALL)],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )


def test_generated_telegram_userapp_entries_are_retired_recoverably(tmp_path: Path) -> None:
    _managed_launcher(tmp_path)
    ours = _userapp(
        tmp_path, "T5RGT3",
        exec_line="Exec=telegram-desktop -- %u",
        comment="Comment=Custom definition for Telegram Desktop",
    )
    foreign = tmp_path / ".local/share/applications/userapp-GIMP-AB12CD.desktop"
    foreign.write_text(
        "[Desktop Entry]\nType=Application\nNoDisplay=true\nExec=gimp %U\n"
        "Name=GIMP\nComment=Custom definition for GIMP\n",
        encoding="utf-8",
    )
    mimeapps = tmp_path / ".config/mimeapps.list"
    mimeapps.parent.mkdir(parents=True, exist_ok=True)
    mimeapps.write_text(
        "[Default Applications]\n"
        "x-scheme-handler/tg=org.telegram.desktop.desktop\n"
        "text/html=google-chrome.desktop\n"
        "\n"
        "[Added Associations]\n"
        "x-scheme-handler/tg=userapp-Telegram Desktop-T5RGT3.desktop;\n"
        "image/png=userapp-GIMP-AB12CD.desktop;\n",
        encoding="utf-8",
    )

    result = _run_userapp_retirement(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not ours.exists()
    assert foreign.exists(), "a userapp entry for another application must survive"

    remaining = mimeapps.read_text(encoding="utf-8")
    assert "userapp-Telegram Desktop-T5RGT3.desktop" not in remaining
    assert "image/png=userapp-GIMP-AB12CD.desktop;" in remaining
    assert "x-scheme-handler/tg=org.telegram.desktop.desktop" in remaining
    assert "text/html=google-chrome.desktop" in remaining

    backups = list((tmp_path / ".local/share/rldyour/backups/telegram-integrations").glob("userapp.*"))
    assert len(backups) == 1
    names = {p.name for p in backups[0].iterdir()}
    assert "userapp-Telegram Desktop-T5RGT3.desktop" in names
    assert "mimeapps.list" in names, "the original mimeapps.list must be recoverable"


def test_divergent_telegram_userapp_entry_is_preserved(tmp_path: Path) -> None:
    """A hand-written entry that merely resembles the generated shape stays."""
    _managed_launcher(tmp_path)
    handmade = _userapp(
        tmp_path, "T5RGT3",
        exec_line="Exec=telegram-desktop -- %u",
        comment="Comment=my own launcher",
    )
    result = _run_userapp_retirement(tmp_path)
    assert result.returncode != 0
    assert "diverged from the generated shape; preserved" in result.stdout
    assert handmade.exists()


def test_userapp_retirement_dry_run_changes_nothing(tmp_path: Path) -> None:
    _managed_launcher(tmp_path)
    ours = _userapp(
        tmp_path, "T5RGT3",
        exec_line="Exec=telegram-desktop -- %u",
        comment="Comment=Custom definition for Telegram Desktop",
    )
    result = _run_userapp_retirement(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stderr
    assert "[DRY-RUN] retire 1 generated Telegram userapp launcher" in result.stdout
    assert ours.exists()


def test_userapp_retirement_runs_after_the_generated_sweep() -> None:
    source = INSTALL.read_text(encoding="utf-8")
    main = source.split("main() {", 1)[1]
    assert main.index("rldyour::ubuntu::retire_telegram_generated_integrations") < main.index(
        "rldyour::ubuntu::retire_telegram_userapp_entries"
    )


def test_verifier_rejects_a_surviving_telegram_userapp_entry() -> None:
    verify = (ROOT / "scripts/ubuntu/verify.sh").read_text(encoding="utf-8")
    assert "userapp-*.desktop" in verify


# ---------------- one source of truth for the pinned assets ----------------


VERIFY = ROOT / "scripts/ubuntu/verify.sh"


def _contract() -> dict:
    return json.loads((ROOT / "config/rldyour-contract.json").read_text(encoding="utf-8"))


def test_verifier_gates_on_the_same_icon_digests_as_the_contract() -> None:
    """The four digests live in the contract, the installer, the verifier and a
    test. The parity check covered only contract<->installer, so a version bump
    could leave the verifier gating on the previous release's icons."""
    desktop = _contract()["desktop_entries"]["telegram"]
    verify = VERIFY.read_text(encoding="utf-8")
    for asset in desktop["icon_assets"]:
        assert asset["sha256"] in verify, (
            f"verify.sh does not gate on {asset['target']}"
        )
        relative = asset["target"].split("${HOME}/", 1)[1]
        assert relative in verify, f"verify.sh does not check {relative}"


def test_telegram_paths_do_not_diverge_between_install_and_verify() -> None:
    """install.sh consulted XDG_DATA_HOME for three Telegram paths while the
    contract, verify.sh and device_integrity all declare ${HOME}/.local/share.
    With XDG_DATA_HOME set the feature split in half: policy and icons landed
    in one place, the launcher and every check looked in another."""
    installer = INSTALL.read_text(encoding="utf-8")
    assert "XDG_DATA_HOME" not in installer, (
        "install.sh must use the location the contract declares"
    )
    contract_target = _contract()["user_tools"]["telegram"][
        "external_updater_policy_target"
    ]
    assert contract_target.startswith("${HOME}/.local/share/")
    # The installer composes the path from a directory and a filename, so check
    # the two halves rather than the joined literal.
    directory, _, filename = contract_target.split("${HOME}/", 1)[1].rpartition("/")
    assert directory in installer, f"install.sh does not write into {directory}"
    assert filename in installer
    verify = VERIFY.read_text(encoding="utf-8")
    assert directory in verify and filename in verify


def test_telegram_declares_no_arm64_artifact() -> None:
    """The row used to repeat the x86_64 URL and digest in the arm64 fields, so
    an arm64 desktop verified the SHA-256 of a binary it cannot execute."""
    installer = INSTALL.read_text(encoding="utf-8")
    row = next(
        line for line in installer.splitlines() if line.strip().startswith('"telegram;')
    )
    fields = row.strip().strip('"').split(";")
    name, version, kind = fields[0], fields[1], fields[2]
    sha_x64, sha_arm64, url_x64, url_arm64 = fields[6], fields[7], fields[8], fields[9]
    assert name == "telegram" and kind == "tarx"
    assert sha_x64 and url_x64
    assert sha_arm64 == "" and url_arm64 == "", "arm64 must be declared absent, not faked"
    assert version in url_x64


def test_only_telegram_declares_a_missing_architecture() -> None:
    """An empty pair is a deliberate 'upstream publishes nothing here'. Any
    other row with one is a typo that would silently skip a required tool."""
    import re

    installer = INSTALL.read_text(encoding="utf-8")
    for table in ("PINNED_SOURCE_TOOLS", "USER_TOOLS"):
        block = re.search(rf"^{table}=\((.*?)^\)", installer, re.M | re.S)
        assert block, f"{table} missing"
        for line in block.group(1).splitlines():
            line = line.strip()
            if not line.startswith('"'):
                continue
            fields = line.strip('"').split(";")
            incomplete = not fields[7] or not fields[9]
            if incomplete:
                assert fields[0] == "telegram", (
                    f"{fields[0]} declares no arm64 artifact; only telegram may"
                )


def test_arm64_verification_does_not_require_telegram() -> None:
    verify = VERIFY.read_text(encoding="utf-8")
    assert "upstream publishes no $(uname -m) build" in verify
    telegram_gate = verify.split("rldyour::require_cmd herdr required", 1)[1]
    assert "x86_64|amd64)" in telegram_gate.split("esac", 1)[0]


def test_a_shared_association_line_keeps_its_surviving_handler(tmp_path: Path) -> None:
    """Dropping the whole line would unregister a handler we never touched, and
    keeping it whole would leave a reference to a file that no longer exists."""
    _managed_launcher(tmp_path)
    _userapp(
        tmp_path, "T5RGT3",
        exec_line="Exec=telegram-desktop -- %u",
        comment="Comment=Custom definition for Telegram Desktop",
    )
    mimeapps = tmp_path / ".config/mimeapps.list"
    mimeapps.parent.mkdir(parents=True, exist_ok=True)
    mimeapps.write_text(
        "[Default Applications]\n"
        "x-scheme-handler/tg=org.telegram.desktop.desktop\n"
        "\n"
        "[Added Associations]\n"
        "x-scheme-handler/tg=userapp-Telegram Desktop-T5RGT3.desktop;org.telegram.desktop.desktop;\n"
        "x-scheme-handler/tonsite=userapp-Telegram Desktop-T5RGT3.desktop;\n"
        "image/png=gimp.desktop;\n",
        encoding="utf-8",
    )

    assert _run_userapp_retirement(tmp_path).returncode == 0
    remaining = mimeapps.read_text(encoding="utf-8")

    assert "userapp-Telegram Desktop-T5RGT3.desktop" not in remaining
    # Shared line: the survivor stays registered.
    assert "x-scheme-handler/tg=org.telegram.desktop.desktop;\n" in remaining
    # Sole handler retired: the line goes.
    assert "x-scheme-handler/tonsite=" not in remaining.split("[Added Associations]", 1)[1]
    # Untouched neighbours, and the default section, survive verbatim.
    assert "image/png=gimp.desktop;" in remaining
    assert "[Default Applications]\nx-scheme-handler/tg=org.telegram.desktop.desktop\n" in remaining


def test_the_pruner_never_treats_its_own_backup_as_a_handler() -> None:
    """The mimeapps.list backup lands in the same directory as the retired
    launchers, and the retired set is read from that directory."""
    installer = INSTALL.read_text(encoding="utf-8")
    # Bounded by the function that uses it: the embedded program contains
    # blank lines, so splitting on one truncates it.
    pruner = installer.split("RLDYOUR_PRUNE_ADDED_ASSOCIATIONS=", 1)[1].split(
        "rldyour::ubuntu::retire_telegram_userapp_entries()", 1
    )[0]
    # Single quotes inside the embedded program are shell-escaped as '\'', so
    # match on the quote-free part of the filter.
    assert "if path.name.endswith(" in pruner, (
        "the retired set must be filtered to launchers, not everything in the "
        "backup directory"
    )
    assert ".desktop" in pruner
