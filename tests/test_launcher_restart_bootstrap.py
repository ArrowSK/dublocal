from __future__ import annotations

from pathlib import Path


def test_in_app_restart_detaches_before_stopping_backend() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "scripts" / "macos" / "launch-dublocal.sh").read_text(encoding="utf-8")

    detach_guard = 'if [[ "$REQUESTED_ACTION" == "restart" && "$RESTART_STAGE" != "detached" ]]'
    normal_restart = 'if [[ "$REQUESTED_ACTION" == "restart" ]]; then'

    detach_position = launcher.index(detach_guard)
    normal_position = launcher.index(normal_restart, detach_position + len(detach_guard))
    detach_block = launcher[detach_position:normal_position]

    assert detach_position < normal_position
    assert "DUBLOCAL_RESTART_STAGE=detached" in detach_block
    assert "DUBLOCAL_LAUNCH_ACTION=restart" in detach_block
    assert "/bin/sleep 0.25" in detach_block
    assert "&!" in detach_block
    assert "exit 0" in detach_block
