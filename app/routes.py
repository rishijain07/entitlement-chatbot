# app/routes.py
# Defines the Flask routes/endpoints for the RAG application (frontend & chat API).

import time
import traceback # Added for better error logging
from flask import Blueprint, request, jsonify, current_app, render_template
from . import utils
from . import rag_pipeline

# Create Blueprint for RAG functionality
rag_bp = Blueprint('rag', __name__)

# --- Route to serve the frontend ---
@rag_bp.route('/', methods=['GET'])
def index():
    """Serves the main chat interface."""
    print("Serving index.html")
    return render_template('index.html')

# --- API Endpoint for Chat ---
@rag_bp.route('/chat', methods=['POST'])
def chat_handler():
    """Handles incoming chat queries and executes the updated RAG pipeline."""
    start_time = time.time()
    print(f"\nReceived request at /chat")

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_query = data.get('query')

    if not user_query:
        return jsonify({"error": "'query' field is required"}), 400

    print(f"User Query: '{user_query}'")
    response_text = "Could not process the request."

    try:
        # Get necessary components for the RAG pipeline
        # The rag_pipeline.get_conversational_rag_answer function expects:
        # 1. user_query
        # 2. db_connection_for_sql_tool (which is the Langchain SQLDatabase object)
        # 3. chroma_collection_for_vector
        
        langchain_sql_db = utils.get_langchain_sql_db()
        chroma_collection = utils.get_chroma_collection()

        if langchain_sql_db is None:
            print("! Connection Error: Langchain SQLDatabase utility could not be initialized.")
            raise ConnectionError("Failed to initialize Langchain SQL Database utility.")
        
        if chroma_collection is None:
            print("! Connection Error: ChromaDB collection could not be retrieved.")
            raise ConnectionError("Failed to retrieve ChromaDB collection.")

        print("   Successfully retrieved Langchain SQL DB utility and ChromaDB collection.")
        
        # Execute the conversational RAG pipeline
        response_text = rag_pipeline.get_conversational_rag_answer(
            user_query=user_query,
            db_connection_for_sql_tool=langchain_sql_db, # This is the Langchain SQLDatabase object
            chroma_collection_for_vector=chroma_collection
        )

    except ConnectionError as e:
        print(f"! Connection Error during chat processing: {e}")
        # traceback.print_exc() # Optionally log the full traceback for connection errors too
        response_text = "Error connecting to backend data stores. Please ensure services are running and configured."
        return jsonify({"error": response_text}), 503  # Service Unavailable
    except Exception as e:
        print(f"!! Critical Error processing chat request: {e}")
        traceback.print_exc() # Log the full traceback for unexpected errors
        response_text = "An unexpected error occurred while processing your request. Please check server logs."
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        # Note: Database connections (g.db_conn) are typically closed by app.teardown_appcontext
        # Langchain SQLDatabase and Chroma PersistentClient might not need explicit closing here
        # if managed by 'g' or application context lifecycles.
        pass

    end_time = time.time()
    processing_time = end_time - start_time
    print(f"Sending Response (Processing Time: {processing_time:.2f}s): '{response_text[:100]}...'")
    return jsonify({"reply": response_text})


# Add a simple health check endpoint
@rag_bp.route('/health', methods=['GET'])
def health_check():
    """Checks the health of database connections and other essential services."""
    print("\nPerforming health check...")
    direct_sqlite_ok = False
    langchain_sqlite_util_ok = False
    chroma_ok = False
    
    # Check 1: Direct SQLite Connection
    sqlite_conn = None
    try:
        sqlite_conn = utils.get_db_connection() # Corrected function name
        if sqlite_conn:
            sqlite_conn.cursor().execute("SELECT 1")
            direct_sqlite_ok = True
            print("  Direct SQLite connection: OK")
        else:
            print("  Direct SQLite connection: Failed to get connection object.")
    except Exception as e:
        print(f"  Health check - Direct SQLite DB error: {e}")

    # Check 2: Langchain SQLDatabase Utility
    try:
        langchain_sql_db = utils.get_langchain_sql_db()
        if langchain_sql_db:
            # You could add a simple test like getting table names if needed
            # print(f"  Langchain SQL DB tables: {langchain_sql_db.get_usable_table_names()}")
            langchain_sqlite_util_ok = True
            print("  Langchain SQLDatabase utility: OK")
        else:
            print("  Langchain SQLDatabase utility: Failed to initialize.")
    except Exception as e:
        print(f"  Health check - Langchain SQLDatabase utility error: {e}")

    # Check 3: ChromaDB Connection
    chroma_collection = None
    try:
        chroma_collection = utils.get_chroma_collection()
        if chroma_collection:
            chroma_collection.count() # A simple operation to check connectivity
            chroma_ok = True
            print("  ChromaDB connection: OK")
        else:
            print("  ChromaDB connection: Failed to get collection object.")
    except Exception as e:
        print(f"  Health check - ChromaDB error: {e}")

    overall_status = "OK" if direct_sqlite_ok and langchain_sqlite_util_ok and chroma_ok else "ERROR"
    
    status_details = {
        "status": overall_status,
        "direct_sqlite_status": "OK" if direct_sqlite_ok else "ERROR",
        "langchain_sqlite_utility_status": "OK" if langchain_sqlite_util_ok else "ERROR",
        "chromadb_status": "OK" if chroma_ok else "ERROR",
        "timestamp": time.time()
    }
    
    status_code = 200 if overall_status == "OK" else 503 # Service Unavailable
    print(f"Health check result: {overall_status}, Details: {status_details}")
    return jsonify(status_details), status_code