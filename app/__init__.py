# app/__init__.py
# Main application package initialization

import os
from flask import Flask
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file (especially for API keys)
# Make sure this runs before accessing environment variables in config
load_dotenv()

# Import configuration after loading .env
from .config import Config

def create_app(config_class=Config):
    """Creates and configures the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    print("Flask app created.")
    print(f"SQLite DB Path: {app.config.get('SQLITE_DB_FILE')}")
    print(f"ChromaDB Path: {app.config.get('CHROMA_DB_PATH')}")

    # Configure Google Generative AI Client
    api_key = app.config.get('GOOGLE_API_KEY')
    if api_key:
        try:
            genai.configure(api_key=api_key)
            print("Google Generative AI client configured.")
        except Exception as e:
            print(f"Error configuring Google Generative AI: {e}")
    else:
        print("Warning: GOOGLE_API_KEY not set. RAG features requiring API calls will fail.")

    # Initialize database connections/clients (or setup app context)
    # For simplicity, utils functions will handle connections for now
    from . import utils
    # You might add teardown contexts here if using app context for DBs
    # app.teardown_appcontext(utils.close_db) # Example

    # Register routes/blueprints
    from . import routes
    app.register_blueprint(routes.bp)
    print("Routes registered.")

    return app

