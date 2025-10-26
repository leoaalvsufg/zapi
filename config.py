import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for Flask application."""
    
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_secret_key_default')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Database configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Z-API configuration
    ZAPI_INSTANCE_ID = os.getenv('ZAPI_INSTANCE_ID')
    ZAPI_INSTANCE_TOKEN = os.getenv('ZAPI_INSTANCE_TOKEN')
    ZAPI_SEND_TEXT_URL = os.getenv('ZAPI_SEND_TEXT_URL')
    ZAPI_CLIENT_TOKEN = os.getenv('ZAPI_CLIENT_TOKEN')  # Optional: some Z-API setups require this header
    
    # Build Z-API URL if not provided
    if not ZAPI_SEND_TEXT_URL and ZAPI_INSTANCE_ID and ZAPI_INSTANCE_TOKEN:
        ZAPI_SEND_TEXT_URL = (
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/"
            f"token/{ZAPI_INSTANCE_TOKEN}/send-text"
        )
    
    # Rate limiting configuration
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '30 per minute')
    RATE_LIMIT_SEND = os.getenv('RATE_LIMIT_SEND', '10 per minute')
    RATE_LIMIT_BULK = os.getenv('RATE_LIMIT_BULK', '2 per minute')
    
    # AI Integration (Optional)
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    # Agnus Framework
    AGNUS_ENABLED = os.getenv('AGNUS_ENABLED', 'false').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.ZAPI_INSTANCE_ID or not cls.ZAPI_INSTANCE_TOKEN:
            raise ValueError(
                "Z-API credentials not configured. "
                "Please set ZAPI_INSTANCE_ID and ZAPI_INSTANCE_TOKEN in .env file."
            )
        return True