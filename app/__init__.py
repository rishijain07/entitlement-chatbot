# app/__init__.py
# Main application package initialization
# ** Updated to register both RAG and Lookup blueprints **

import os
from flask import Flask
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
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
        print("Warning: GOOGLE_API_KEY not set. RAG/Embedding features will fail.")

    # Initialize database utilities
    from . import utils
    utils.init_app(app) # Register teardown context etc.
    print("Database utilities initialized.")

    # Register Blueprints
    from . import routes # Contains rag_bp
    from . import lookup_api # Contains lookup_bp

    app.register_blueprint(routes.rag_bp) # Register RAG routes (/, /chat, /health)
    app.register_blueprint(lookup_api.lookup_bp) # Register Lookup API routes (/api/entitlements)
    print("Blueprints registered (RAG and Lookup API).")

    return app

