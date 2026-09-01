from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir

from .job_control import install_shutdown_hooks, shutdown_all
from .production_ui import MATRIX_CSS, build_app
from .storage_cleanup import prune_stale_jobs_only, run_automatic_housekeeping


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _gradio_allowed_paths() -> list[str]:
    """Expose only DubLocal's generated job files to the local Gradio UI."""

    jobs_dir = Path(user_cache_dir("DubLocal")) / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return [str(jobs_dir.resolve())]


def main() -> None:
    """Launch DubLocal from one explicit production composition root."""

    port = int(os.getenv("DUBLOCAL_PORT", "7861"))
    inbrowser = _env_bool("DUBLOCAL_INBROWSER", True)
    install_shutdown_hooks()

    # Housekeeping is an ordinary application service. It never rewrites runtime
    # functions/classes and protects models, sign-in sessions and finished outputs.
    run_automatic_housekeeping()

    demo = build_app()
    try:
        demo.queue(default_concurrency_limit=1).launch(
            inbrowser=inbrowser,
            server_name="127.0.0.1",
            server_port=port,
            show_error=False,
            css=MATRIX_CSS,
            allowed_paths=_gradio_allowed_paths(),
        )
    finally:
        shutdown_all()
        try:
            prune_stale_jobs_only()
        except Exception:
            pass


if __name__ == "__main__":
    main()
