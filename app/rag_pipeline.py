# app/rag_pipeline.py
# Core RAG pipeline logic: parse, retrieve, generate.

import re
import sqlite3
import google.generativeai as genai
from flask import current_app # Access config and potentially genai client

# --- RAG Pipeline Helper Functions ---

def parse_query(query, conn):
    """Basic keyword parsing to identify entities."""
    # (Same parse_query function as in Colab script)
    print(f"   Parsing query: '{query}'")
    parsed = {'role': None, 'project': None, 'app': None, 'ent_code': None}
    if not conn: return parsed

    cursor = conn.cursor()
    try:
        ent_match = re.search(r'\b(APP\d{3,}_\w+)\b', query, re.IGNORECASE)
        if ent_match:
            parsed['ent_code'] = ent_match.group(1).upper()
            cursor.execute("SELECT id FROM Entitlements WHERE code = ?", (parsed['ent_code'],))
            if not cursor.fetchone(): parsed['ent_code'] = None
            else: print(f"      Found potential entitlement code: {parsed['ent_code']}")

        cursor.execute("SELECT id, name FROM Roles")
        roles_db = cursor.fetchall()
        for r in roles_db:
            if re.search(r'\b' + re.escape(r['name']) + r'\b', query, re.IGNORECASE):
                parsed['role'] = {'id': r['id'], 'name': r['name']}; print(f"      Found potential role: {parsed['role']}"); break

        cursor.execute("SELECT id, name FROM Projects")
        projects_db = cursor.fetchall()
        for p in projects_db:
            if re.search(r'\b' + re.escape(p['name']) + r'\b', query, re.IGNORECASE):
                parsed['project'] = {'id': p['id'], 'name': p['name']}; print(f"      Found potential project: {parsed['project']}"); break

        cursor.execute("SELECT id, name FROM Applications")
        apps_db = cursor.fetchall()
        for a in apps_db:
            if re.search(r'\b' + re.escape(a['name']) + r'\b', query, re.IGNORECASE):
                parsed['app'] = {'id': a['id'], 'name': a['name']}; print(f"      Found potential application: {parsed['app']}"); break
    except sqlite3.Error as e:
        print(f"      DB Error during parsing: {e}")
    except Exception as e:
        print(f"      Unexpected error during parsing: {e}")
    return parsed


def retrieve_structured_data(parsed_entities, conn):
    """Retrieves data from SQLite based on parsed entities."""
    # (Same retrieve_structured_data function as in Colab script)
    print("   Retrieving structured data from SQLite...")
    context_lines = []
    if not conn: print("      SQLite connection not available."); return context_lines
    cursor = conn.cursor()
    try:
        if parsed_entities.get('role') and parsed_entities.get('project'):
            role_id = parsed_entities['role']['id']; project_id = parsed_entities['project']['id']
            role_name = parsed_entities['role']['name']; project_name = parsed_entities['project']['name']
            print(f"      Querying inferred entitlements for Role '{role_name}' on Project '{project_name}'...")
            query = "SELECT E.code, E.description FROM RoleProjectMappings RPM JOIN Entitlements E ON RPM.entitlement_id = E.id WHERE RPM.role_id = ? AND RPM.project_id = ?"
            cursor.execute(query, (role_id, project_id))
            results = cursor.fetchall()
            if results:
                context_lines.append(f"Inferred Entitlements for {role_name} on {project_name}:")
                for row in results: context_lines.append(f"- {row['code']}: {row['description']}")
            else: context_lines.append(f"No specific entitlements were inferred for {role_name} on {project_name}.")
        elif parsed_entities.get('app'):
            app_id = parsed_entities['app']['id']; app_name = parsed_entities['app']['name']
            print(f"      Querying entitlements for Application '{app_name}'...")
            query = "SELECT E.code, E.description FROM AppEntitlementMappings AEM JOIN Entitlements E ON AEM.entitlement_id = E.id WHERE AEM.app_id = ?"
            cursor.execute(query, (app_id,))
            results = cursor.fetchall()
            if results:
                context_lines.append(f"Entitlements associated with Application '{app_name}':")
                for row in results: context_lines.append(f"- {row['code']}: {row['description']}")
            else: context_lines.append(f"No entitlements found mapped to Application '{app_name}'.")
        elif parsed_entities.get('ent_code'):
            ent_code = parsed_entities['ent_code']
            print(f"      Querying description for Entitlement Code '{ent_code}'...")
            cursor.execute("SELECT description FROM Entitlements WHERE code = ?", (ent_code,))
            result = cursor.fetchone()
            if result: context_lines.append(f"Description for {ent_code}: {result['description']}")
            else: context_lines.append(f"Could not find description for entitlement code '{ent_code}'.")
    except sqlite3.Error as e: print(f"      SQLite query error: {e}")
    except Exception as e: print(f"      Unexpected error during structured retrieval: {e}")
    if not context_lines: print("      No specific structured data found.")
    return context_lines

def retrieve_vector_data(query, collection):
    """Retrieves relevant documents from ChromaDB based on query similarity."""
    # (Same retrieve_vector_data function as in Colab script, gets model from config)
    print("   Retrieving relevant documents from ChromaDB...")
    context_lines = []
    api_key = current_app.config.get('GOOGLE_API_KEY')
    embedding_model = current_app.config.get('EMBEDDING_MODEL')
    n_results = current_app.config.get('CHROMA_N_RESULTS', 3)

    if not api_key: print("      Skipping ChromaDB retrieval: API key missing."); return context_lines
    if not collection: print("      Skipping ChromaDB retrieval: Collection not available."); return context_lines
    if not embedding_model: print("      Skipping ChromaDB retrieval: Embedding model not configured."); return context_lines

    try:
        print(f"      Embedding query for ChromaDB using '{embedding_model}'...")
        query_embedding_result = genai.embed_content(model=embedding_model, content=query, task_type="RETRIEVAL_QUERY")
        query_embedding = query_embedding_result['embedding']
        print("      Query embedded. Searching collection...")
        results = collection.query(query_embeddings=[query_embedding], n_results=n_results, include=['documents', 'metadatas'])
        if results and results.get('ids') and results['ids'][0]:
            print(f"      Found {len(results['ids'][0])} potentially relevant documents.")
            context_lines.append("Potentially Relevant Entitlement Descriptions:")
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]; doc = results['documents'][0][i]
                context_lines.append(f"- {meta.get('code', 'Unknown Code')}: {doc}")
        else: print("      No relevant documents found in ChromaDB.")
    except Exception as e: print(f"      Error during ChromaDB retrieval/embedding: {e}")
    return context_lines

def generate_llm_response(query, context):
    """Generates response using Gemini based on query and context."""
    # (Same generate_llm_response function as in Colab script, gets model from config)
    print("   Generating response using Gemini...")
    api_key = current_app.config.get('GOOGLE_API_KEY')
    generation_model = current_app.config.get('GENERATION_MODEL')

    if not api_key: print("      Skipping LLM generation: API key missing."); return "Sorry, I cannot generate a response without API key configuration."
    if not generation_model: print("      Skipping LLM generation: Generation model not configured."); return "Sorry, I cannot generate a response due to configuration issue."

    prompt = f"""You are an Entitlement Assistant chatbot. Answer the user's query based *only* on the provided context below. Do not add information not present in the context. If the context doesn't contain the answer, say you don't have enough information.

Context:
---
{context}
---

User Query: {query}

Answer:"""
    print(f"      Sending prompt (length: {len(prompt)}) to model '{generation_model}'...")
    try:
        model = genai.GenerativeModel(generation_model)
        response = model.generate_content(prompt) # Using default safety settings
        if not response.parts:
             if response.prompt_feedback.block_reason:
                  details = f" Ratings: {response.prompt_feedback.safety_ratings}" if response.prompt_feedback.safety_ratings else ""
                  print(f"      Warning: Response blocked due to {response.prompt_feedback.block_reason}{details}")
                  return f"My response was blocked due to safety settings ({response.prompt_feedback.block_reason}). Please rephrase your query."
             else: print("      Warning: LLM returned no content."); return "Sorry, I could not generate a response for that query."
        response_text = getattr(response, 'text', None)
        if response_text is None: print("      Warning: LLM response did not contain text."); return "Sorry, I received an unexpected response format."
        print("      LLM response received.")
        return response_text
    except Exception as e: print(f"      Error during Gemini API call: {e}"); return "Sorry, an error occurred while generating the response."

