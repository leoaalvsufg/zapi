import os
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from loguru import logger
from config import Config
from models import db

# Configure logger
logger.add("logs/app.log", rotation="10 MB", retention="30 days", level="INFO")

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    Config.validate()
    
    # Initialize database
    db.init_app(app)
    
    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[Config.RATE_LIMIT_DEFAULT],
        storage_uri="memory://"
    )
    
    # Store limiter in app context for use in routes
    app.limiter = limiter
    
    # Register blueprints
    from routes import main_bp
    app.register_blueprint(main_bp)
    
    # Ensure database tables exist and initialize scheduler
    with app.app_context():
        db.create_all()
        logger.info("Database tables ready")
        # Initialize APScheduler and restore jobs
        from services.scheduler import init_scheduler
        init_scheduler(app)
    
    return app

def init_db_cli():
    """Initialize database from CLI."""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")

if __name__ == '__main__':
    app = create_app()
    logger.info("Starting Z-API WhatsApp Sender application")
    app.run(debug=True, host='127.0.0.1', port=5055)
