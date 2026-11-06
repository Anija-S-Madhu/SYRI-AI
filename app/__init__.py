"""
SYRI AI - Your Money. Your Intelligence.
AI-powered personal financial intelligence platform.
"""

from flask import Flask
from .config import Config


def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance directory exists before database connection
    import os
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    from .extensions import db, login_manager
    db.init_app(app)
    login_manager.init_app(app)

    # User loader for Flask-Login
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    from .routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Import all models so db.create_all() registers every table
    from .models import User, Category, Transaction, Budget  # noqa: F401

    # Create database tables
    with app.app_context():
        db.create_all()

    return app
