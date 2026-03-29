from __future__ import annotations

import uvicorn

from .app import create_app, load_settings_from_env


def main() -> None:
    settings = load_settings_from_env()
    app = create_app(settings)
    uvicorn.run(app, host="127.0.0.1", port=9786)


if __name__ == "__main__":
    main()
