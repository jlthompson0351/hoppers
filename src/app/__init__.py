"""Flask application package.

Run with:
  python -m src.app
"""

from __future__ import annotations

from flask import Flask

from src.app.routes import bp as routes_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-only-change-me"  # no auth in scaffold
    app.register_blueprint(routes_bp)

    @app.context_processor
    def _inject_globals() -> dict:
        # "Maintenance tech" gating is intentionally simple in this scaffold.
        # Enable by setting either:
        # - env: LCS_MAINTENANCE_UI=1
        # - config JSON: ui.maintenance_enabled=true (stored in SQLite)
        import os

        env_on = os.environ.get("LCS_MAINTENANCE_UI", "").strip().lower() in ("1", "true", "yes", "on")
        cfg_on = False
        try:
            repo = app.config.get("REPO")
            if repo is not None:
                cfg = repo.get_latest_config()
                cfg_on = bool((cfg.get("ui") or {}).get("maintenance_enabled", False))
        except Exception:
            cfg_on = False

        return {"maintenance_enabled": bool(env_on or cfg_on)}

    return app


