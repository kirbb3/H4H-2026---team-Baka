import os
from flask import Flask
from src.backend.config import config_map, DevelopmentConfig
from src.backend.routes import api_bp


def create_app(config_name: str = None) -> Flask:
    """
    Application factory.
    config_name: 'development' | 'production' (defaults to FLASK_ENV env var, else development)
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend", "static"),
        template_folder=os.path.join(os.path.dirname(__file__), "..", "frontend", "templates"),
    )

    # Load config
    app.config.from_object(config_map.get(config_name, DevelopmentConfig))

    # Register blueprints
    app.register_blueprint(api_bp)

    # --- FUTURE: init DB here ---
    # e.g. db.init_app(app)  (SQLAlchemy / raw psycopg2 pool / etc.)
    # ----------------------------

    # Keep the root route for serving the frontend SPA/template
    from flask import render_template

    @app.route("/")
    def index():
        return render_template("index.html")

    return app