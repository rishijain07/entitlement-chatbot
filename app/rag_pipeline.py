# app/rag_pipeline.py
# Core RAG pipeline logic using Langchain for SQL generation and conversational memory.

import re
import sqlite3
import google.generativeai as genai
from flask import current_app, g # For app context and config
import traceback # For more detailed error logging
import json # For safely parsing potential list/dict string outputs
import random # For varied greeting responses

# Langchain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import AIMessage, HumanMessage

# --- SQL Agent Imports ---
from langchain_community.agent_toolkits import SQLDatabaseToolkit, create_sql_agent
from langchain.agents import AgentExecutor 

# Import utils for DB access
from . import utils

# --- Global or App-Context based LLM and Memory (Example) ---
# Initialize memory here, but it will be loaded/saved per session/request context
global_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)


def get_llm():
    """Initializes and returns the LLM instance."""
    if 'llm' not in g:
        model_name = current_app.config.get('GENERATION_MODEL_NAME', 'gemini-1.5-pro-latest')
        try:
            # Ensure convert_system_message_to_human is True if using older models or specific setups
            g.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, convert_system_message_to_human=True) 
            print(f"LLM initialized with model: {model_name}")
        except Exception as e:
            print(f"Error initializing LLM: {e}")
            traceback.print_exc()
            g.llm = None
    return g.llm

def get_session_memory():
    """
    Retrieves the conversational memory for the current session.
    In a real application, this might involve loading/saving session-specific memory.
    For this example, it returns a global memory instance.
    """
    return global_memory

# --- Langchain SQL Agent ---
def create_sql_agent_executor(llm, db):
    """Creates a Langchain SQL Agent Executor."""
    if not db:
        print("Database not available for SQL agent.")
        return None
    if not llm:
        print("LLM not available for SQL agent.")
        return None
        
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    top_k_val = current_app.config.get('LANGCHAIN_SQL_TOP_K', 5)
    
    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=current_app.config.get('LANGCHAIN_VERBOSE', True),
        handle_parsing_errors="Check your output and try again. If you are using a tool, make sure the input is a valid SQL query. If you are providing a final answer, ensure it addresses the original question.",
        top_k=top_k_val,
    )
    print(f"SQL Agent Executor created. Top_k for agent: {top_k_val}")
    return agent_executor

def is_result_empty_or_error(result_text: str) -> bool:
    """
    Checks if the agent's result text indicates no data found, an error, or is an empty list/dict.
    """
    if result_text is None:
        return True
    
    text_lower = result_text.strip().lower()

    no_result_phrases = [
        "no results found", "i don't know", "i couldn't find any information",
        "no data available", "the query returned no results", "no matching records",
        "n/a (no query executed)", "n/a (agent decided sql not required or question unanswerable)",
        "query executed successfully, no matching records found." 
    ]
    if any(phrase in text_lower for phrase in no_result_phrases):
        return True

    if text_lower == "[]" or text_lower == "{}" or text_lower == "none": 
        return True
    
    try:
        if text_lower.startswith('[') and text_lower.endswith(']') or \
           text_lower.startswith('{') and text_lower.endswith('}'):
            parsed_json = json.loads(result_text) 
            if isinstance(parsed_json, (list, dict)) and not parsed_json:
                return True
    except json.JSONDecodeError:
        pass 

    error_indicators = ["error executing sql", "sql agent error", "failed to execute", "an error occurred"]
    if any(indicator in text_lower for indicator in error_indicators):
        return True
        
    return False


def parse_agent_output(agent_response_text: str):
    """
    Parses the agent's output text to extract the SQL query and the actual result.
    Relies on the agent being prompted to return "SQL Query: ..." and "Result: ...".
    """
    generated_sql = "N/A (Agent did not explicitly state SQL)"
    query_result = agent_response_text 

    match = re.search(r"SQL Query:\s*(.*?)(?:\n(?:Result:|Answer:)\s*(.*)|$)", agent_response_text, re.DOTALL | re.IGNORECASE)

    if match:
        generated_sql = match.group(1).strip() if match.group(1) else "N/A (SQL query part was empty)"
        query_result = match.group(2).strip() if match.group(2) else "N/A (Result/Answer part was empty after SQL Query marker)"
        
        if query_result == "N/A (Result/Answer part was empty after SQL Query marker)" and generated_sql != "N/A (SQL query part was empty)":
             if "i don't need to query" in agent_response_text.lower() or \
               "no sql query is needed" in agent_response_text.lower() or \
               "n/a (no query executed)" in generated_sql.lower():
                generated_sql = "N/A (Agent decided SQL not required)"
                query_result = agent_response_text 
    else:
        if "i don't need to query" in agent_response_text.lower() or \
           "no sql query is needed" in agent_response_text.lower() or \
           ("i don't know" in agent_response_text.lower() and "select" not in agent_response_text.lower()): 
            generated_sql = "N/A (Agent decided SQL not required or question unanswerable)"
            query_result = agent_response_text 
        else:
            query_result = agent_response_text
            generated_sql = "N/A (No SQL Query marker found, or format mismatch)"

    if query_result == agent_response_text and "N/A" not in generated_sql:
        if generated_sql in agent_response_text:
            potential_result_start = agent_response_text.find(generated_sql) + len(generated_sql)
            query_result_candidate = agent_response_text[potential_result_start:].strip()
            if query_result_candidate: 
                 query_result = query_result_candidate

    if not query_result.strip() and "N/A (Agent decided SQL not required" not in generated_sql:
        query_result = "Agent provided SQL but the result part was empty or not found."
        
    if "N/A" not in generated_sql and query_result.lower().strip() in ["", "[]", "{}","none"]:
        query_result = "Query executed, but no specific data returned or result was empty."

    return generated_sql, query_result


# --- Vector Retrieval (ChromaDB) ---
def retrieve_vector_data(query, collection):
    """Retrieves relevant documents from ChromaDB based on query similarity."""
    print("   Retrieving relevant documents from ChromaDB...")
    context_lines = []
    api_key = current_app.config.get('GOOGLE_API_KEY')
    embedding_model_name = current_app.config.get('EMBEDDING_MODEL_NAME')
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
            print(f"      Found {len(results['ids'][0])} potentially relevant documents from Chroma.")
            context_lines.append("Potentially Relevant Entitlement Descriptions from Semantic Search:")
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
                doc = results['documents'][0][i] if results['documents'] and results['documents'][0] else "N/A"
                context_lines.append(f"- Code {meta.get('code', 'N/A')} (ID: {meta.get('id', 'N/A')}): {doc}")
        else: 
            print("      No relevant documents found in ChromaDB for the query.")
    except Exception as e: 
        print(f"      Error during ChromaDB retrieval/embedding: {e}")
        traceback.print_exc()
    return context_lines


def extract_mentioned_application_from_history(chat_history_messages, current_query):
    """
    Extracts the most recently mentioned application name from chat history,
    giving preference to applications mentioned in relation to entitlements.
    Returns the application name or None.
    """
    app_keywords = ["application", "portal", "system", "platform", "app ", " service", " hub"] 
    query_context_keywords = ["entitlement", "access", "permission", "manager", "role", "what is required for"]

    for message in reversed(chat_history_messages):
        text_to_search = ""
        if isinstance(message, HumanMessage):
            text_to_search = message.content.lower()
        elif isinstance(message, AIMessage):
            text_to_search = message.content.lower()
        
        if any(kw in text_to_search for kw in app_keywords):
            for kw in app_keywords:
                if kw in text_to_search:
                    if "branch customer portal" in text_to_search:
                        return "Branch Customer Portal"
            
            potential_apps = re.findall(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:application|portal|system|platform|service|hub)", text_to_search, re.IGNORECASE)
            if potential_apps:
                if any(q_kw in current_query.lower() for q_kw in query_context_keywords):
                    return potential_apps[0] 

    return None


# --- Main RAG Chain with Conversational Memory ---
def get_conversational_rag_answer(user_query, db_connection_for_sql_tool, chroma_collection_for_vector):
    """
    Processes the user query using a RAG pipeline with conversational memory
    and an LLM-powered SQL Agent. Handles greetings and no-result scenarios gracefully.
    """
    print(f"\n--- Executing Conversational RAG Pipeline for Query: '{user_query}' ---")
    
    memory = get_session_memory()
    chat_history_messages = memory.load_memory_variables({}).get("chat_history", [])
    llm = get_llm() # Get LLM instance early

    if not llm:
        return "Error: LLM not available. Please check configuration."

    # 1. Enhanced Greeting/Introductory Query Check
    query_lower_stripped = user_query.lower().strip()
    query_for_check = re.sub(r'[^\w\s]', '', query_lower_stripped) 

    greetings = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy"]
    # help_phrases = ["can you help", "i need help", "help me"] # Not used in the if condition below directly
    entitlement_keywords = [
        "entitlement", "access", "permission", "permit", "role", "project", 
        "application", "app", "system", "platform", "software", "tool", 
        "db", "database", "data", "report", "feature", "module", "functionality",
        "what are", "what is", "who has", "do i have", "can i get", "how to get", "list all",
        "manager", "required for" 
    ]

    is_simple_greeting_type = any(g in query_for_check for g in greetings)
    has_specific_entitlement_context = any(kw in query_for_check for kw in entitlement_keywords)
    
    name_match = re.search(r"\b(?:i'm|i am|im|my name is)\s+(\w+)", query_lower_stripped, re.IGNORECASE)
    user_name = name_match.group(1).capitalize() if name_match else None

    if is_simple_greeting_type and not has_specific_entitlement_context and len(query_for_check.split()) < 8:
        print("   Query identified as a simple greeting. Using LLM for response.")
        
        greeting_system_prompt = (
            "You are a friendly and helpful Entitlement Assistant chatbot. "
            "The user has just greeted you."
        )
        if user_name:
            greeting_system_prompt += f" The user's name is {user_name}."
        
        greeting_human_template = (
            "{user_greeting}\n\n"
            "Please provide a concise, welcoming response. Acknowledge the user's greeting (and name, if provided). "
            "Then, briefly offer to help with application entitlements."
        )

        greeting_prompt = ChatPromptTemplate.from_messages([
            ("system", greeting_system_prompt),
            ("human", greeting_human_template)
        ])
        
        greeting_chain = greeting_prompt | llm | StrOutputParser()
        
        try:
            response_text = greeting_chain.invoke({"user_greeting": user_query})
        except Exception as e:
            print(f"   Error during LLM greeting generation: {e}")
            traceback.print_exc()
            # Fallback to a simpler hardcoded greeting if LLM fails for this specific path
            base_greeting = "Hello"
            if user_name: base_greeting = f"Hello {user_name}!"
            offer_help = "How can I help you with application entitlements today?"
            response_text = f"{base_greeting} {offer_help}"

        memory.save_context({"input": user_query}, {"output": response_text})
        print(f"   Responding with LLM-generated greeting: {response_text}")
        return response_text

    # --- If not a simple greeting, proceed with the full RAG pipeline ---
    langchain_db_for_agent = db_connection_for_sql_tool 
    sql_agent_executor = None
    sql_agent_raw_output = "SQL Agent was not invoked." 
    generated_sql_for_context = "N/A"
    sql_result_for_context = "No information was retrieved from the database for this query." 

    recent_app_context = extract_mentioned_application_from_history(chat_history_messages, user_query)
    app_context_for_prompt = f"A relevant application from recent conversation history might be: '{recent_app_context}'. Prioritize this if the current query is a follow-up." if recent_app_context else "No specific application context from prior conversation turns was identified as immediately relevant for this query."

    if langchain_db_for_agent:
        sql_agent_executor = create_sql_agent_executor(llm, langchain_db_for_agent)
        if sql_agent_executor:
            try:
                print("   Attempting to get answer from SQL Agent...")
                agent_input_prompt_template = (
                    "User question: {user_query}\n\n"
                    "Consider the ongoing conversation. {app_context_for_prompt}\n\n"
                    "Based on the table schema, if a SQL query is needed, write and execute it. "
                    "Limit the number of results to {top_k} if selecting many rows or if the question implies a list. "
                    "Only ask for the specific columns needed to answer the question. "
                    "Pay close attention to entities like role names, project names, or application names in the user's question and history. "
                    "If an exact match for an entity is not found, consider using SQL `LIKE` clauses for partial matches or to find the closest matching entity name first, then use that identified name in your main query. "
                    "For example, if the user asks about 'Branch Portal' and the database has 'Branch Customer Portal', try to identify 'Branch Customer Portal' as the target application, especially if it was mentioned in recent conversation. "
                    "Do not hallucinate table or column names. Only use the tables you know about: {table_names}. "
                    "The most important tables for entitlements are 'Entitlements', 'Applications', 'AppEntitlementMappings', 'Roles'. "
                    "To find what entitlements are needed for a role in an application, you might need to join Applications with AppEntitlementMappings and then Entitlements, and filter by application name and potentially role descriptions or typical role functions (e.g., 'MANAGE' for managers). "
                    "PRIVACY INSTRUCTION: Your primary goal is to identify entitlements, not individuals. "
                    "Do NOT retrieve or list individual employee names, email addresses, or specific employee-to-entitlement/project assignments in your 'Result:'. "
                    "If the user asks about requirements for a role (e.g., 'manager') for an application, describe the *types* of entitlements or list the relevant entitlement codes and their descriptions (e.g., 'APP001_MANAGE: Allows management of resources'). "
                    "Do NOT mention who currently holds these entitlements or list the names of managers. Focus on the *what* (entitlements, applications, roles), not the *who*. "
                    "For example, if asked 'what is required for managers in Branch Portal?', a good response would list entitlements like 'APP001_MANAGE', not 'Gregory Flynn has APP001_MANAGE'.\n\n"
                    "IMPORTANT: After you have the result from the database (or if you decide no query is needed, or if an error occurs), "
                    "format your entire response as follows, making sure to include both parts clearly separated:\n"
                    "SQL Query: [The SQL query you attempted or used. If no query was used, state 'N/A (No query executed)'. If there was an error before execution, state the intended query and the error if possible.]\n"
                    "Result: [The result from the database, your textual answer if no query was executed, or a description of the error if one occurred. If the query ran but returned no data, explicitly state that, e.g., 'Query executed successfully, no matching records found.']"
                )
                
                agent_input = agent_input_prompt_template.format(
                    user_query=user_query,
                    app_context_for_prompt=app_context_for_prompt,
                    top_k=current_app.config.get('LANGCHAIN_SQL_TOP_K', 5),
                    table_names=langchain_db_for_agent.get_usable_table_names()
                )

                agent_response = sql_agent_executor.invoke({"input": agent_input})
                sql_agent_raw_output = agent_response.get('output', "SQL Agent did not return a standard output key.")
                print(f"   SQL Agent Raw Output: {sql_agent_raw_output}")

                parsed_sql, parsed_result = parse_agent_output(sql_agent_raw_output)
                generated_sql_for_context = parsed_sql
                
                print(f"   Parsed SQL from Agent: {generated_sql_for_context}")
                print(f"   Parsed Result from Agent (raw): {parsed_result[:300]}...") 

                if is_result_empty_or_error(parsed_result):
                    print(f"   SQL Agent result indicates no data or an error. Parsed result: '{parsed_result}'")
                    sql_result_for_context = parsed_result if parsed_result else "The database query did not return specific information for this request."
                else:
                    sql_result_for_context = parsed_result 
                    print(f"   SQL Agent provided data: {sql_result_for_context[:300]}...")

            except Exception as e:
                print(f"   Error invoking SQL Agent or parsing its output: {e}")
                traceback.print_exc()
                sql_result_for_context = f"An error occurred while trying to get information from the database. (Details: {str(e)[:100]})" 
                generated_sql_for_context = "Error during agent execution"
                sql_agent_raw_output = f"Exception during agent invocation: {e}"
        else:
            sql_result_for_context = "SQL Agent Executor could not be created. Database query not attempted."
            sql_agent_raw_output = "SQL Agent Executor was None."
    else:
        sql_result_for_context = "Database for SQL Agent is not configured or available. Query not attempted."
        sql_agent_raw_output = "Langchain DB for Agent was None."

    print(f"   DEBUG SQL Agent Interaction Summary:\n   User Query to Agent: {user_query}\n   Generated SQL (stated by agent): {generated_sql_for_context}\n   Raw Agent Output (first 300 chars): {sql_agent_raw_output[:300]}...\n   Interpreted Agent Result for Final Context (first 300 chars): {str(sql_result_for_context)[:300]}...")

    vector_context_lines = retrieve_vector_data(user_query, chroma_collection_for_vector)
    vector_context_str = "\n".join(vector_context_lines) if vector_context_lines else "No additional information was found through semantic search of entitlement descriptions."

    final_context_for_llm = f"""
    User Query: {user_query}

    Information from Database (via SQL Agent):
    Agent's Stated SQL: {generated_sql_for_context}
    Agent's Result/Answer (interpreted):
    {sql_result_for_context}

    Additional Information from Semantic Search (Vector DB of entitlement descriptions):
    {vector_context_str}
    """
    
    system_prompt_text = (
        "You are a specialized Entitlement Assistant. Your primary goal is to answer the user's questions about application entitlements "
        "based *solely* on the information provided in the 'Context' section below. The context includes an interpretation of results from a SQL Agent (which queries a database) and semantic searches of entitlement descriptions. "
        "Carefully review all parts of the context. "
        "The 'Agent's Stated SQL' shows the query the SQL Agent claims to have attempted or used. The 'Agent's Result/Answer (interpreted)' is what the SQL Agent found, or a summary if no specific data was returned or an error occurred. "
        "PRIVACY GUIDELINE: Absolutely do not reveal any personally identifiable information (PII) such as employee names, lists of employees, specific individuals associated with roles or applications, or employee emails, even if such data might accidentally appear in the 'Context' from the SQL agent. "
        "Your role is to provide information about entitlements, roles, and applications in a general, non-identifying way. "
        "If the context accidentally contains PII (like specific employee names when asked about general role requirements), you MUST ignore that PII for the purpose of your answer regarding individuals. Focus on the *what* (entitlements, applications, roles) and not the *who*. "
        "For instance, if asked about manager requirements for 'Branch Portal' and the context mentions 'Gregory Flynn has APP001_MANAGE', your answer should be about 'APP001_MANAGE' and its function for managers, NOT about Gregory Flynn. "
        "If the 'Agent's Result/Answer (interpreted)' indicates that no specific information was retrieved or an error happened, acknowledge this politely. For example, you might say 'I couldn't find specific details for that in our records' or 'I was unable to retrieve that specific information at the moment.' Do not say 'the database returned no results' or 'there was an error.' "
        "Similarly, if 'Additional Information from Semantic Search' indicates no relevant documents were found, integrate that smoothly. "
        "Synthesize a comprehensive and helpful answer from all available pieces of information in the context. "
        "If the combined context is insufficient to fully answer the question, clearly state that the information isn't available in the current knowledge base or ask clarifying questions that might help narrow down the search. "
        "Do not make up information or answer outside of the provided context. "
        "If a specific entitlement code is identified (e.g., APP001_READ), mention it and its description if available. "
        "Maintain a helpful, conversational, and professional tone. Use the chat history for conversational flow and to understand follow-up questions. Avoid technical jargon where possible."
    )

    prompt_messages = [
        SystemMessagePromptTemplate.from_template(system_prompt_text),
        MessagesPlaceholder(variable_name="chat_history"), 
        HumanMessagePromptTemplate.from_template("Context:\n{context}\n\nUser's Question: {question}\n\nAssistant's Answer:")
    ]
    final_answer_prompt = ChatPromptTemplate.from_messages(prompt_messages)

    final_chain = final_answer_prompt | llm | StrOutputParser()

    print("   Generating final response with aggregated context and history...")

    response_text = "Sorry, I encountered an issue while processing your request. Please try again." 
    try:
        response_text = final_chain.invoke({
            "context": final_context_for_llm,
            "question": user_query,
            "chat_history": chat_history_messages 
        })
    except Exception as e:
        print(f"   Error during final LLM response generation: {e}")
        traceback.print_exc()
        response_text = "Sorry, an error occurred while formulating the final answer. Please check the server logs for more details or try rephrasing your question."

    memory.save_context({"input": user_query}, {"output": response_text}) 
    print(f"--- RAG Pipeline Finished. Final Response (first 300 chars): {response_text[:300]}... ---")
    return response_text
