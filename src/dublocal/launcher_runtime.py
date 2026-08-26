from __future__ import annotations

import os

from .app import MATRIX_CSS, build_app


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def main() -> None:
    port = int(os.getenv("DUBLOCAL_PORT", "7861"))
    inbrowser = _env_bool("DUBLOCAL_INBROWSER", False)

    demo = build_app()
    demo.queue(default_concurrency_limit=1).launch(
        inbrowser=inbrowser,
        server_name="127.0.0.1",
        server_port=port,
        show_error=False,
        css=MATRIX_CSS,
    )


if __name__ == "__main__":
    main()
