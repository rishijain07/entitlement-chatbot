# app/routes.py
# Defines the Flask routes/endpoints for the application.

import time
from flask import Blueprint, request, jsonify, current_app, render_template # Added render_template
from . import utils
from . import rag_pipeline

# Create a Blueprint
bp = Blueprint('main', __name__)

# --- Route to serve the frontend ---
@bp.route('/', methods=['GET'])
def index():
    """Serves the main chat interface."""
    print("Serving index.html")
    # Renders the index.html file from the 'templates' folder
    return render_template('index.html')

# --- API Endpoint for Chat ---
@bp.route('/chat', methods=['POST'])
def chat_handler():
    """Handles incoming chat queries and executes the RAG pipeline."""
    start_time = time.time()
    print(f"\nReceived request at /chat")

    # 1. Get user query
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    user_query = data.get('query')
    if not user_query: return jsonify({"error": "'query' field is required"}), 400
    print(f"User Query: '{user_query}'")

    response_text = "Could not process the request."
    conn = None
    coll = None

    try:
        # Get DB connections/clients using utils within request context
        conn = utils.get_db()
        coll = utils.get_chroma_collection()

        if conn is None:
             raise ConnectionError("Failed to connect to SQLite database.")
        # Note: Chroma connection failure is handled within retrieve_vector_data

        # --- RAG Pipeline Execution ---
        # 2. Parse Query
        parsed_entities = rag_pipeline.parse_query(user_query, conn)

        # 3. Retrieval Phase
        structured_context = rag_pipeline.retrieve_structured_data(parsed_entities, conn)
        vector_context = rag_pipeline.retrieve_vector_data(user_query, coll) # Pass collection

        # 4. Context Aggregation
        print("   Aggregating context...")
        context_parts = []
        if structured_context: context_parts.append("Structured Information Found:"); context_parts.extend(structured_context)
        if vector_context:
             if context_parts: context_parts.append("\n")
             context_parts.extend(vector_context)
        if not context_parts: aggregated_context = "No specific information found in the knowledge base for your query."; print("      No context retrieved.")
        else: aggregated_context = "\n".join(context_parts); print(f"      Aggregated context length: {len(aggregated_context)}")

        # 5. Generation Phase
        response_text = rag_pipeline.generate_llm_response(user_query, aggregated_context)

    except ConnectionError as e:
         print(f"! Connection Error: {e}")
         response_text = "Error connecting to backend data stores."
         return jsonify({"error": response_text}), 503 # Service Unavailable
    except Exception as e:
        print(f"!! Critical Error processing chat request: {e}")
        # Log traceback here in production
        response_text = "An unexpected error occurred while processing your request."
        return jsonify({"error": "An internal server error occurred."}), 500
    # Note: DB connection closing is handled by teardown context registered in __init__.py via utils.init_app

    # 6. Return Response
    end_time = time.time(); processing_time = end_time - start_time
    print(f"Sending Response (Processing Time: {processing_time:.2f}s): '{response_text[:100]}...'")
    return jsonify({"reply": response_text})

# Add a simple health check endpoint
@bp.route('/health', methods=['GET'])
def health_check():
    # Basic check: can we connect to DB?
    db_ok = False
    conn = None
    try:
        conn = utils.get_db()
        if conn:
            conn.cursor().execute("SELECT 1")
            db_ok = True
    except Exception as e:
        print(f"Health check DB error: {e}")

    # Basic check: can we connect to Chroma?
    chroma_ok = False
    coll = None
    try:
        coll = utils.get_chroma_collection()
        if coll:
            coll.count() # Simple operation
            chroma_ok = True
    except Exception as e:
        print(f"Health check Chroma error: {e}")

    status = {
        "status": "OK" if db_ok and chroma_ok else "ERROR",
        "sqlite_status": "OK" if db_ok else "ERROR",
        "chromadb_status": "OK" if chroma_ok else "ERROR",
        "timestamp": time.time()
    }
    status_code = 200 if status["status"] == "OK" else 503
    return jsonify(status), status_code
