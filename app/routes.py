# app/routes.py
# Defines the Flask routes/endpoints for the RAG application (frontend & chat API).
# Renamed Blueprint to 'rag_bp'.

import time
from flask import Blueprint, request, jsonify, current_app, render_template
from . import utils
from . import rag_pipeline

# Create Blueprint for RAG functionality
rag_bp = Blueprint('rag', __name__) # Renamed from 'main'

# --- Route to serve the frontend ---
@rag_bp.route('/', methods=['GET'])
def index():
    """Serves the main chat interface."""
    print("Serving index.html")
    return render_template('index.html')

# --- API Endpoint for Chat ---
@rag_bp.route('/chat', methods=['POST'])
def chat_handler():
    """Handles incoming chat queries and executes the RAG pipeline."""
    # (Same chat_handler logic as before, using rag_pipeline functions)
    # ... (omitted for brevity, assume function is pasted here) ...
    start_time = time.time()
    print(f"\nReceived request at /chat")
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json(); user_query = data.get('query')
    if not user_query: return jsonify({"error": "'query' field is required"}), 400
    print(f"User Query: '{user_query}'")
    response_text = "Could not process the request."
    conn = None; coll = None
    try:
        conn = utils.get_db(); coll = utils.get_chroma_collection()
        if conn is None: raise ConnectionError("Failed to connect to SQLite database.")
        parsed_entities = rag_pipeline.parse_query(user_query, conn)
        structured_context = rag_pipeline.retrieve_structured_data(parsed_entities, conn)
        vector_context = rag_pipeline.retrieve_vector_data(user_query, coll)
        print("   Aggregating context...")
        context_parts = []
        if structured_context: context_parts.append("Information from Database:"); context_parts.extend(structured_context)
        if vector_context:
             if context_parts: context_parts.append("\n")
             context_parts.extend(vector_context)
        if not context_parts: aggregated_context = "No specific information found in the knowledge base for your query."; print("      No context retrieved.")
        else: aggregated_context = "\n".join(context_parts); print(f"      Aggregated context length: {len(aggregated_context)}")
        response_text = rag_pipeline.generate_llm_response(user_query, aggregated_context)
    except ConnectionError as e:
         print(f"! Connection Error: {e}"); response_text = "Error connecting to backend data stores."
         return jsonify({"error": response_text}), 503 # Service Unavailable
    except Exception as e:
        print(f"!! Critical Error processing chat request: {e}")
        response_text = "An unexpected error occurred while processing your request."
        return jsonify({"error": "An internal server error occurred."}), 500
    end_time = time.time(); processing_time = end_time - start_time
    print(f"Sending Response (Processing Time: {processing_time:.2f}s): '{response_text[:100]}...'")
    return jsonify({"reply": response_text})


# Add a simple health check endpoint
@rag_bp.route('/health', methods=['GET'])
def health_check():
    # (Same health_check logic as before)
    # ... (omitted for brevity, assume function is pasted here) ...
    db_ok = False; conn = None
    try:
        conn = utils.get_db()
        if conn: conn.cursor().execute("SELECT 1"); db_ok = True
    except Exception as e: print(f"Health check DB error: {e}")
    chroma_ok = False; coll = None
    try:
        coll = utils.get_chroma_collection()
        if coll: coll.count(); chroma_ok = True
    except Exception as e: print(f"Health check Chroma error: {e}")
    status = {"status": "OK" if db_ok and chroma_ok else "ERROR", "sqlite_status": "OK" if db_ok else "ERROR", "chromadb_status": "OK" if chroma_ok else "ERROR", "timestamp": time.time()}
    status_code = 200 if status["status"] == "OK" else 503
    return jsonify(status), status_code

