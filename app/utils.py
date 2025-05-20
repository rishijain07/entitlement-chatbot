# app/utils.py
# Utility functions, including database connections and Langchain SQLDatabase setup.

import sqlite3
import chromadb
import os
from flask import current_app, g
from langchain_community.utilities import SQLDatabase # For Langchain

# --- SQLite Database ---
def get_db_connection():
    """
    Connects to the SQLite database for the current request context.
    If a connection doesn't exist, it creates one.
    """
    if 'db_conn' not in g: # Changed g variable name for clarity
        db_path = current_app.config['SQLITE_DB_PATH']
        try:
            if not os.path.exists(db_path):
                 raise FileNotFoundError(f"SQLite DB file not found at {db_path}. Run initialization script.")
            g.db_conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db_conn.row_factory = sqlite3.Row
        except Exception as e:
            print(f"Error connecting to SQLite DB: {e}")
            g.db_conn = None
    return g.db_conn

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_conn.close()

# --- Langchain SQLDatabase Utility ---
def get_langchain_sql_db():
    """
    Returns a Langchain SQLDatabase instance for the application's database.
    Includes only specified tables for the LLM to query.
    """
    if 'langchain_sql_db' not in g:
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        include_tables = current_app.config.get('LANGCHAIN_SQL_TABLES', []) # Get whitelisted tables
        if not include_tables:
            print("Warning: LANGCHAIN_SQL_TABLES not set in config. LLM will have access to all tables.")
        try:
            g.langchain_sql_db = SQLDatabase.from_uri(db_uri, include_tables=include_tables if include_tables else None)
            print(f"Langchain SQLDatabase initialized for URI: {db_uri}")
            if include_tables:
                print(f"  LLM can query tables: {g.langchain_sql_db.get_usable_table_names()}")
        except Exception as e:
            print(f"Error initializing Langchain SQLDatabase: {e}")
            g.langchain_sql_db = None
    return g.langchain_sql_db


# --- ChromaDB Vector Store ---
def get_chroma_collection():
    """
    Connects to ChromaDB and returns the specified collection.
    """
    if 'chroma_collection' not in g:
        db_path = current_app.config['CHROMA_DB_PATH']
        collection_name = current_app.config['CHROMA_COLLECTION_NAME']
        try:
            if not os.path.exists(db_path):
                 raise FileNotFoundError(f"ChromaDB path not found at {db_path}. Run initialization script.")
            client = chromadb.PersistentClient(path=db_path)
            collections = client.list_collections()
            collection_names = [c.name for c in collections]
            if collection_name in collection_names:
                 g.chroma_collection = client.get_collection(name=collection_name)
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
    # No need to explicitly close Langchain SQLDatabase or Chroma client here,
    # as they are typically managed differently or don't require explicit close for PersistentClient.