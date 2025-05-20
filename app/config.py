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
    print(f"Warning: .env file not found at {project_root}. Using defaults or expecting environment variables.")


class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-so-change-me'

    # --- Database configuration ---
    SQLITE_DB_FILE_NAME = 'entitlements_employee_db.db' 
    SQLITE_DB_PATH = os.environ.get('SQLITE_DB_FILE') or os.path.join(project_root, SQLITE_DB_FILE_NAME)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{SQLITE_DB_PATH}"

    CHROMA_DB_DIR_NAME = 'chroma_db_employee' 
    CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH') or os.path.join(project_root, CHROMA_DB_DIR_NAME)
    CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME') or 'entitlement_docs_employee'

    # --- RAG Model configuration ---
    EMBEDDING_MODEL_NAME = os.environ.get('EMBEDDING_MODEL_NAME') or 'models/embedding-001'
    GENERATION_MODEL_NAME = os.environ.get('GENERATION_MODEL_NAME') or 'gemini-1.5-pro-latest'
    CHROMA_N_RESULTS = int(os.environ.get('CHROMA_N_RESULTS') or 3) # For vector store retrieval during init/other uses
    CHROMA_QUERY_N_RESULTS = int(os.environ.get('CHROMA_QUERY_N_RESULTS') or 10) # For RAG pipeline semantic search

    # --- API Keys ---
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

    # --- Flask App Config ---
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # Langchain Agent Config
    LANGCHAIN_VERBOSE = os.environ.get('LANGCHAIN_VERBOSE', 'True').lower() == 'true'
    LANGCHAIN_SQL_TABLES = [ 
        "Employees", "Roles", "Projects", "Applications", "Entitlements",
        "EmployeeProjectAssignments", "EmployeeEntitlementHoldings", "AppEntitlementMappings"
    ]
    LANGCHAIN_SQL_TOP_K = int(os.environ.get('LANGCHAIN_SQL_TOP_K') or 5) # Added for SQL query chain