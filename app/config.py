# app/config.py
# Configuration settings for the Flask application

import os
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(basedir, '..')) # Go up one level from app/
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("Warning: .env file not found.")


class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # --- Database configuration ---
    # Point to the DB with Employee Holdings
    SQLITE_DB_FILE = os.environ.get('SQLITE_DB_FILE') or os.path.join(project_root, 'entitlements_employee_db.db')
    # Point to the corresponding Chroma DB
    CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH') or os.path.join(project_root, 'chroma_db_employee')
    CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME') or 'entitlement_docs_employee'

    # --- RAG Model configuration ---
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL') or 'models/embedding-001'
    GENERATION_MODEL = os.environ.get('GENERATION_MODEL') or 'gemini-1.5-pro-latest'
    CHROMA_N_RESULTS = int(os.environ.get('CHROMA_N_RESULTS') or 3)

    # --- API Keys ---
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

    # --- Flask App Config ---
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

