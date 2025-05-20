# app/__init__.py
# Main application package initialization
# ** Updated for Langchain and session management (basic). **

import os
from flask import Flask, session # Added session
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

    # --- IMPORTANT: Set a secret key for Flask session management ---
    # This is crucial if you implement session-based conversational memory.
    # Load from config, which should load from .env or have a default.
    app.secret_key = app.config.get('SECRET_KEY', 'dev_default_secret_key_change_me')
    if app.secret_key == 'dev_default_secret_key_change_me' and not app.debug:
        print("WARNING: Using default SECRET_KEY in non-debug mode. Please set a strong secret key in your .env file.")


    print("Flask app created.")
    print(f"SQLite DB Path: {app.config.get('SQLITE_DB_PATH')}")
    print(f"ChromaDB Path: {app.config.get('CHROMA_DB_PATH')}")
    print(f"Generation Model: {app.config.get('GENERATION_MODEL_NAME')}")


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

    # Initialize database utilities (registers teardown context)
    from . import utils
    utils.init_app(app)
    print("Database utilities initialized.")

    # Register Blueprints
    from .routes import rag_bp # Contains RAG routes (/, /chat, /health)
    from .lookup_api import lookup_bp # Contains Lookup API routes (/api/entitlements)

    app.register_blueprint(rag_bp)
    app.register_blueprint(lookup_bp) # Ensure lookup_bp is also registered
    print("Blueprints registered (RAG and Lookup API).")

    # Initialize global LLM and other components if needed on app creation
    # This ensures they are ready when the first request comes.
    with app.app_context():
        from .rag_pipeline import get_llm
        if get_llm() is None:
            print("CRITICAL: LLM failed to initialize on app startup.")
        # Initialize Langchain SQLDatabase instance via utils to cache it in 'g' for first request
        utils.get_langchain_sql_db()
        utils.get_chroma_collection()


    return app