# app/rag_pipeline.py
# Core RAG pipeline logic using Langchain for SQL generation and conversational memory.

import re
import sqlite3
import google.generativeai as genai
from flask import current_app, g # For app context and config
import traceback # For more detailed error logging

# Langchain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_sql_query_chain # To generate SQL
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain.memory import ConversationBufferMemory
# from langchain.agents import AgentExecutor, create_tool_calling_agent # For a more general agent
# from langchain_community.agent_toolkits import SQLDatabaseToolkit # For SQL agent
# from langchain.tools import Tool # For custom tools if needed

# Import utils for DB access
from . import utils

# --- Global or App-Context based LLM and Memory (Example) ---
global_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)


def get_llm():
    """Initializes and returns the LLM instance."""
    if 'llm' not in g:
        model_name = current_app.config.get('GENERATION_MODEL_NAME', 'gemini-1.5-pro-latest')
        try:
            g.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, convert_system_message_to_human=True) # Lower temp for factual tasks
            print(f"LLM initialized with model: {model_name}")
        except Exception as e:
            print(f"Error initializing LLM: {e}")
            g.llm = None
    return g.llm

def get_session_memory():
    """
    Placeholder for session-specific memory.
    Currently returns a global memory instance.
    """
    return global_memory


# --- Langchain SQL Query Chain ---
def create_db_query_chain(llm, db, k_for_prompt: int): # MODIFIED: Added k_for_prompt
    """Creates a Langchain chain to generate and execute SQL queries."""
    if not db:
        print("Database not available for SQL query chain.")
        return None
    try:
        sql_prompt_text = """Based on the table schema below, write a SQL query that would answer the user's question ({input}).
You are requested to limit the number of results to {top_k} if you are selecting many rows or if the question implies a list.
Only ask for the specific columns needed to answer the question. Do not select all columns unless explicitly asked.
Pay attention to the user's question to extract entities like role names, project names, or application names.
Only use the tables listed below. Do not hallucinate table or column names.
Return ONLY the raw SQL query with no formatting, no markdown, no code blocks, and no extra text.

Schema:
{table_info}

SQL Query:"""
        
        prompt = PromptTemplate(
            input_variables=["input", "table_info", "top_k"], 
            template=sql_prompt_text
        )
        
        # MODIFIED: Pass k_for_prompt as the 'k' argument to create_sql_query_chain
        # This 'k' argument will populate the {top_k} variable in your custom prompt.
        generate_query_chain = create_sql_query_chain(llm, db, prompt=prompt, k=k_for_prompt)
        return generate_query_chain
    except Exception as e:
        print(f"Error creating SQL query chain: {e}")
        traceback.print_exc() # Print full traceback for debugging
        return None

def clean_sql_query(query):
    """
    Clean SQL query by removing markdown code block syntax and any surrounding whitespace.
    """
    # Remove markdown code block syntax if present
    query = re.sub(r'^```\s*sql\s*', '', query)
    query = re.sub(r'```$', '', query)
    # Clean any leading/trailing whitespace
    query = query.strip()
    return query

def execute_sql_query(query, db):
    """Executes a SQL query using the Langchain SQLDatabase tool and returns the result."""
    # Clean the query before execution
    cleaned_query = clean_sql_query(query)
    print(f"   Original SQL: {query}")
    print(f"   Cleaned SQL: {cleaned_query}")
    
    if not db:
        return "Error: Database connection not available for SQL execution."
    try:
        result = db.run(cleaned_query) 
        print(f"   SQL Result (first 100 chars): {str(result)[:100]}...")
        return result
    except Exception as e:
        print(f"   Error executing SQL query '{cleaned_query}': {e}")
        traceback.print_exc() # Print full traceback for debugging
        return f"Error executing SQL: {e}"


# --- Vector Retrieval (ChromaDB) ---
def retrieve_vector_data(query, collection):
    """Retrieves relevant documents from ChromaDB based on query similarity."""
    print("   Retrieving relevant documents from ChromaDB...")
    context_lines = []
    api_key = current_app.config.get('GOOGLE_API_KEY')
    embedding_model_name = current_app.config.get('EMBEDDING_MODEL_NAME')
    # Use CHROMA_QUERY_N_RESULTS for querying, CHROMA_N_RESULTS might be for init or other uses
    n_results = current_app.config.get('CHROMA_QUERY_N_RESULTS', 5) 

    if not api_key: print("      Skipping ChromaDB retrieval: API key missing."); return context_lines
    if not collection: print("      Skipping ChromaDB retrieval: Collection not available."); return context_lines
    if not embedding_model_name: print("      Skipping ChromaDB retrieval: Embedding model not configured."); return context_lines

    try:
        print(f"      Embedding query for ChromaDB using '{embedding_model_name}'...")
        query_embedding_result = genai.embed_content(model=embedding_model_name, content=query, task_type="RETRIEVAL_QUERY")
        query_embedding = query_embedding_result['embedding']
        print(f"      Query embedded. Searching collection for {n_results} results...")
        results = collection.query(query_embeddings=[query_embedding], n_results=n_results, include=['documents', 'metadatas'])
        
        if results and results.get('ids') and results['ids'][0]:
            print(f"      Found {len(results['ids'][0])} potentially relevant documents.")
            context_lines.append("Potentially Relevant Entitlement Descriptions from Vector Search:")
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]; doc = results['documents'][0][i]
                context_lines.append(f"- Code {meta.get('code', 'N/A')} (ID: {meta.get('id', 'N/A')}): {doc}")
        else: print("      No relevant documents found in ChromaDB.")
    except Exception as e: 
        print(f"      Error during ChromaDB retrieval/embedding: {e}")
        traceback.print_exc()
    return context_lines

# --- Main RAG Chain with Conversational Memory ---
def get_conversational_rag_answer(user_query, db_connection_for_sql_tool, chroma_collection_for_vector):
    """
    Processes the user query using a RAG pipeline with conversational memory
    and LLM-powered SQL generation.
    """
    print("--- Executing Conversational RAG Pipeline ---")
    llm = get_llm()
    if not llm:
        return "Error: LLM not available."

    langchain_db = db_connection_for_sql_tool 

    sql_query_result = "No SQL query was executed or needed for this query." # Default message
    generated_sql = "N/A"
    
    if langchain_db:
        # MODIFIED: Get top_k_val for the k_for_prompt argument
        top_k_val = current_app.config.get('LANGCHAIN_SQL_TOP_K', 5) 
        db_query_chain = create_db_query_chain(llm, langchain_db, k_for_prompt=top_k_val)
        
        if db_query_chain:
            try:
                print("   Attempting to generate SQL query...")
                # MODIFIED: Invoke with "question" key
                generated_sql = db_query_chain.invoke({"question": user_query})
                
                # Improved check for valid SQL or LLM's decision not to query
                if "error" in generated_sql.lower() or \
                   not generated_sql.strip() or \
                   "select" not in generated_sql.lower() or \
                   len(generated_sql.strip()) < 10 or \
                   "i don't need to query" in generated_sql.lower() or \
                   "no sql query is needed" in generated_sql.lower():
                    
                    print(f"   LLM indicated an issue generating SQL or SQL not needed: {generated_sql}")
                    if "i don't need to query" in generated_sql.lower() or \
                       "no sql query is needed" in generated_sql.lower() or \
                       ("select" not in generated_sql.lower() and len(generated_sql.strip()) > 5) : # If it's a short non-SQL phrase
                        sql_query_result = "The Language Model determined that a SQL query was not necessary for this question."
                        generated_sql = "N/A (LLM decided SQL not required)"
                    else:
                        sql_query_result = f"Could not generate a suitable SQL query. LLM Output: {generated_sql}"
                        generated_sql = f"N/A (LLM failed to generate valid SQL: {generated_sql})"
                else:
                    # Store the original generated SQL before cleaning for display purposes
                    original_sql = generated_sql
                    sql_query_result = execute_sql_query(generated_sql, langchain_db)
                    # Keep the original SQL for display in final context
                    generated_sql = original_sql
            except KeyError as ke: # Specifically catch KeyError
                print(f"   KeyError during SQL generation/execution: {ke}")
                print("     This might indicate an issue with expected keys in Langchain's create_sql_query_chain or its inputs.")
                traceback.print_exc()
                sql_query_result = f"Error during SQL processing (KeyError: {ke}). Please check prompt and chain input configurations."
                generated_sql = "Error during generation (KeyError)"
            except Exception as e:
                print(f"   Error in SQL generation/execution part of the chain: {e}")
                traceback.print_exc()
                sql_query_result = f"Error during SQL processing: {e}"
                generated_sql = "Error during generation"
        else:
            sql_query_result = "SQL query chain could not be created (returned None)."
    else:
        sql_query_result = "Database for SQL queries is not configured or available."


    vector_context_lines = retrieve_vector_data(user_query, chroma_collection_for_vector)
    vector_context_str = "\n".join(vector_context_lines) if vector_context_lines else "No additional relevant information found via semantic search of entitlement descriptions."

    memory = get_session_memory()
    # Ensure chat_history is correctly loaded; it might be empty on first turn
    chat_history_messages = memory.load_memory_variables({}).get("chat_history", [])


    final_context = f"""
    User Query: {user_query}

    Information from Database (via SQL query, if attempted):
    Generated SQL: {generated_sql}
    SQL Query Result:
    {sql_query_result}

    Additional Information from Semantic Search (Vector DB of entitlement descriptions):
    {vector_context_str}
    """

    # Refined system prompt for better instruction
    system_prompt_text = (
        "You are a specialized Entitlement Assistant. Your primary goal is to answer the user's questions about application entitlements "
        "based *solely* on the information provided in the 'Context' section below. The context includes results from database queries and semantic searches. "
        "Carefully review all parts of the context. "
        "If the 'SQL Query Result' indicates an error, no data, or that a query wasn't needed, state that clearly. "
        "If 'Additional Information from Semantic Search' is empty or states no relevant documents were found, acknowledge that. "
        "Synthesize a comprehensive answer from all available pieces of information. "
        "If the combined context is insufficient to fully answer the question, clearly state what information is missing or unclear. "
        "Do not make up information or answer outside of the provided context. "
        "If a specific entitlement code is identified (e.g., APP001_READ), mention it. "
        "Maintain a helpful and professional tone."
    )

    final_answer_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_text),
        MessagesPlaceholder(variable_name="chat_history"), # Ensure this is correctly populated
        ("human", "Context:\n{context}\n\nUser's Question: {question}\n\nAssistant's Answer:"),
    ])

    final_chain = final_answer_prompt | llm | StrOutputParser()

    print("   Generating final response with aggregated context and history...")
    try:
        response_text = final_chain.invoke({
            "context": final_context,
            "question": user_query,
            "chat_history": chat_history_messages # Pass the actual messages
        })
    except Exception as e:
        print(f"   Error during final LLM response generation: {e}")
        traceback.print_exc()
        response_text = "Sorry, an error occurred while formulating the final answer. Please check the server logs for more details."

    memory.save_context({"input": user_query}, {"output": response_text})

    return response_text