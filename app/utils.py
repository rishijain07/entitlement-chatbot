# app/utils.py
# Utility functions, including database connections.
# ** No significant changes needed, but added explicit FileNotFoundError check **

import sqlite3
import chromadb
import os # Import os
from flask import current_app, g # Use Flask application context 'g'

def get_db():
    """
    Connects to the SQLite database for the current request context.
    If a connection doesn't exist, it creates one.
    """
    if 'db' not in g:
        db_path = current_app.config['SQLITE_DB_FILE']
        try:
            if not os.path.exists(db_path):
                 # Raise specific error if DB file is missing after app start
                 raise FileNotFoundError(f"SQLite DB file not found at {db_path}. Run initialization script.")
            g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row # Return dict-like rows
            # print(f"DB connection opened for request: {db_path}") # Less verbose
        except Exception as e:
            print(f"Error connecting to SQLite DB: {e}")
            g.db = None # Ensure g.db is None if connection failed
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()
        # print("DB connection closed for request.") # Less verbose

def get_chroma_collection():
    """
    Connects to ChromaDB and returns the specified collection for the current request context.
    """
    if 'chroma_collection' not in g:
        db_path = current_app.config['CHROMA_DB_PATH']
        collection_name = current_app.config['CHROMA_COLLECTION_NAME']
        try:
            if not os.path.exists(db_path):
                 raise FileNotFoundError(f"ChromaDB path not found at {db_path}. Run initialization script.")
            # Use a single client instance if possible, but PersistentClient handles path access
            # For simplicity in request context, we create client each time if not present
            # In high-load scenarios, manage client lifecycle better (e.g., app context factory)
            client = chromadb.PersistentClient(path=db_path)
            # Check if collection exists
            collections = client.list_collections()
            collection_names = [c.name for c in collections]
            if collection_name in collection_names:
                 g.chroma_collection = client.get_collection(name=collection_name)
                 # print(f"Chroma collection '{collection_name}' accessed for request.") # Less verbose
            else:
                 print(f"Error: Chroma collection '{collection_name}' not found.")
                 g.chroma_collection = None
        except Exception as e:
            print(f"Error connecting to ChromaDB: {e}")
            g.chroma_collection = None
    return g.chroma_collection

def init_app(app):
    """Register database functions with the Flask app."""
    app.teardown_appcontext(close_db)
    # Add any other app initialization for utils here

