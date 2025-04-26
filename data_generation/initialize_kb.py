# data_generation/initialize_kb.py
# Initializes the KB (SQLite with employee holdings & ChromaDB) using generated data.

import sqlite3
import chromadb
import google.generativeai as genai
import os
import time
import math
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv

# Import the generation function
from generate_mock_data import generate_data_with_holdings

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SQLITE_DB_FILE = os.getenv('SQLITE_DB_FILE', 'entitlements_employee_db.db') # Updated default name
CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH', './chroma_db_employee') # Updated default name
CHROMA_COLLECTION_NAME = os.getenv('CHROMA_COLLECTION_NAME', 'entitlement_docs_employee') # Updated default name
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'models/embedding-001')
EMBEDDING_BATCH_SIZE = 100
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# --- Visualization Function (Optional) ---
def visualize_employee_data(data):
    """Generates visualizations specific to the employee holdings data."""
    # (Same visualization function as in colab_init_employee_db_py)
    # ... (omitted for brevity, assume function is pasted here) ...
    print("\n--- Generating Visualizations for Employee Data ---")
    try:
        sns.set_theme(style="whitegrid")
        employees_df = pd.DataFrame(data.get('EMPLOYEES',[]))
        projects_df = pd.DataFrame(data.get('PROJECTS',[]))
        roles_df = pd.DataFrame(data.get('ROLES',[]))
        emp_proj_df = pd.DataFrame(data.get('EMPLOYEE_PROJECT_ASSIGNMENTS',[]))
        emp_hold_df = pd.DataFrame(data.get('EMPLOYEE_ENTITLEMENT_HOLDINGS',[]))
        # Plot 1: Employee Role Distribution
        if not employees_df.empty and not roles_df.empty:
             emp_roles = pd.merge(employees_df, roles_df, left_on='role_id', right_on='id', how='left')
             plt.figure(figsize=(12, 7)); sns.countplot(data=emp_roles, y='name_y', order=emp_roles['name_y'].value_counts().index, palette='viridis')
             plt.title('Distribution of Employees per Role'); plt.xlabel('Number of Employees'); plt.ylabel('Role Name'); plt.tight_layout(); plt.show()
        # Plot 2: Projects per Employee Distribution
        if not emp_proj_df.empty:
            projs_per_emp = emp_proj_df.groupby('employee_id').size(); plt.figure(figsize=(10, 6)); sns.histplot(projs_per_emp, bins=max(1, projs_per_emp.max()), kde=False)
            plt.title('Distribution of Projects Assigned per Employee'); plt.xlabel('Number of Projects'); plt.ylabel('Number of Employees'); plt.tight_layout(); plt.show()
        # Plot 3: Entitlements per Employee Distribution
        if not emp_hold_df.empty:
            ents_per_emp = emp_hold_df.groupby('employee_id').size(); plt.figure(figsize=(10, 6)); sns.histplot(ents_per_emp, bins=20, kde=True)
            plt.title('Distribution of Entitlements Held per Employee'); plt.xlabel('Number of Entitlements Held'); plt.ylabel('Number of Employees'); plt.tight_layout(); plt.show()
        # Plot 4: Employees per Project
        if not emp_proj_df.empty and not projects_df.empty:
            emps_per_proj = emp_proj_df.groupby('project_id')['employee_id'].nunique().reset_index(name='employee_count')
            emps_per_proj = pd.merge(emps_per_proj, projects_df[['id', 'name']], left_on='project_id', right_on='id', how='left')
            plt.figure(figsize=(12, 10)); display_limit = 40
            plot_data = emps_per_proj.nlargest(display_limit, 'employee_count') if len(emps_per_proj) > display_limit else emps_per_proj.sort_values('employee_count', ascending=False)
            sns.barplot(data=plot_data, x='employee_count', y='name', palette='coolwarm', orient='h')
            plt.title(f'Number of Employees Assigned per Project (Top {len(plot_data)})'); plt.xlabel('Number of Employees'); plt.ylabel('Project Name'); plt.tight_layout(); plt.show()
        print("--- Visualizations Complete ---")
    except Exception as e: print(f"Error during visualization: {e}")


# --- SQLite Initialization ---
def init_sqlite_employee_db(db_file, data):
    """Creates and populates the SQLite database with employee holdings."""
    # (Same init_sqlite_employee_db function as in Colab script)
    # ... (omitted for brevity, assume function is pasted here) ...
    print(f"\n--- Initializing SQLite database: {db_file}... ---")
    projects = data.get('PROJECTS', []); roles = data.get('ROLES', [])
    applications = data.get('APPLICATIONS', []); entitlements = data.get('ENTITLEMENTS', [])
    app_ent_maps = data.get('APP_ENTITLEMENT_MAPPINGS', [])
    employees = data.get('EMPLOYEES', [])
    emp_proj_assigns = data.get('EMPLOYEE_PROJECT_ASSIGNMENTS', [])
    emp_ent_holds = data.get('EMPLOYEE_ENTITLEMENT_HOLDINGS', [])
    if not all([projects, roles, applications, entitlements, employees]):
         print("Error: Base data lists are empty. Cannot initialize DB.")
         return False
    conn = None
    try:
        conn = sqlite3.connect(db_file); cursor = conn.cursor()
        print("Dropping existing tables (if they exist)...")
        cursor.execute("DROP TABLE IF EXISTS EmployeeEntitlementHoldings"); cursor.execute("DROP TABLE IF EXISTS EmployeeProjectAssignments")
        cursor.execute("DROP TABLE IF EXISTS AppEntitlementMappings"); cursor.execute("DROP TABLE IF EXISTS Entitlements")
        cursor.execute("DROP TABLE IF EXISTS Applications"); cursor.execute("DROP TABLE IF EXISTS Employees")
        cursor.execute("DROP TABLE IF EXISTS Roles"); cursor.execute("DROP TABLE IF EXISTS Projects")
        print("Creating tables...")
        cursor.execute('CREATE TABLE Projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT)')
        cursor.execute('CREATE TABLE Roles (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, level INTEGER NOT NULL)')
        cursor.execute('CREATE TABLE Applications (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT)')
        cursor.execute('CREATE TABLE Entitlements (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, description TEXT NOT NULL)')
        cursor.execute('CREATE TABLE Employees (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role_id INTEGER, FOREIGN KEY (role_id) REFERENCES Roles (id))')
        cursor.execute('CREATE TABLE AppEntitlementMappings (app_id INTEGER NOT NULL, entitlement_id INTEGER NOT NULL, FOREIGN KEY (app_id) REFERENCES Applications (id), FOREIGN KEY (entitlement_id) REFERENCES Entitlements (id), PRIMARY KEY (app_id, entitlement_id))')
        cursor.execute('CREATE TABLE EmployeeProjectAssignments (employee_id INTEGER NOT NULL, project_id INTEGER NOT NULL, FOREIGN KEY (employee_id) REFERENCES Employees (id), FOREIGN KEY (project_id) REFERENCES Projects (id), PRIMARY KEY (employee_id, project_id))')
        cursor.execute('CREATE TABLE EmployeeEntitlementHoldings (employee_id INTEGER NOT NULL, entitlement_id INTEGER NOT NULL, FOREIGN KEY (employee_id) REFERENCES Employees (id), FOREIGN KEY (entitlement_id) REFERENCES Entitlements (id), PRIMARY KEY (employee_id, entitlement_id))')
        print("Inserting data...")
        cursor.executemany("INSERT INTO Projects (id, name, description) VALUES (:id, :name, :description)", projects)
        cursor.executemany("INSERT INTO Roles (id, name, level) VALUES (:id, :name, :level)", roles)
        cursor.executemany("INSERT INTO Applications (id, name, description) VALUES (:id, :name, :description)", applications)
        cursor.executemany("INSERT INTO Entitlements (id, code, description) VALUES (:id, :code, :description)", entitlements)
        cursor.executemany("INSERT INTO Employees (id, name, email, role_id) VALUES (:id, :name, :email, :role_id)", employees)
        if app_ent_maps: cursor.executemany("INSERT OR IGNORE INTO AppEntitlementMappings (app_id, entitlement_id) VALUES (:app_id, :entitlement_id)", app_ent_maps) # Use IGNORE just in case
        if emp_proj_assigns: cursor.executemany("INSERT OR IGNORE INTO EmployeeProjectAssignments (employee_id, project_id) VALUES (:employee_id, :project_id)", emp_proj_assigns)
        if emp_ent_holds: cursor.executemany("INSERT OR IGNORE INTO EmployeeEntitlementHoldings (employee_id, entitlement_id) VALUES (:employee_id, :entitlement_id)", emp_ent_holds)
        conn.commit(); print("SQLite database initialized successfully."); return True
    except sqlite3.Error as e: print(f"SQLite error: {e}"); conn.rollback()
    except Exception as e: print(f"Unexpected error during SQLite init: {e}"); conn.rollback()
    finally:
        if conn: conn.close()
    return False

# --- ChromaDB Initialization ---
def init_chromadb(db_path, collection_name, entitlements, embedding_model_name, api_key):
    """Initializes ChromaDB, generates embeddings, and stores entitlement data."""
    # (Same init_chromadb function as in Colab script)
    # ... (omitted for brevity, assume function is pasted here) ...
    print(f"\n--- Initializing ChromaDB collection: {collection_name} at {db_path}... ---")
    if not entitlements: print("No entitlements found. Skipping."); return False
    if not api_key: print("Google API Key not provided. Skipping ChromaDB init."); return False
    try:
        genai.configure(api_key=api_key)
        client = chromadb.PersistentClient(path=db_path)
        print(f"Getting or creating ChromaDB collection '{collection_name}'...")
        try: client.delete_collection(name=collection_name); print(f"Deleted existing collection '{collection_name}'.")
        except: pass
        collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        ids_to_add = [str(e['id']) for e in entitlements]
        documents_to_add = [e['description'] for e in entitlements]
        metadatas_to_add = [{'code': e['code'], 'id': e['id']} for e in entitlements]
        print(f"Generating embeddings for {len(documents_to_add)} descriptions...")
        all_embeddings = []
        num_batches = math.ceil(len(documents_to_add) / EMBEDDING_BATCH_SIZE)
        embeddings_generated_count = 0
        for i in range(num_batches):
            start_index = i * EMBEDDING_BATCH_SIZE; end_index = start_index + EMBEDDING_BATCH_SIZE
            batch_docs = documents_to_add[start_index:end_index]
            print(f"  Processing batch {i+1}/{num_batches} ({len(batch_docs)} items)...")
            try:
                if not batch_docs: continue
                result = genai.embed_content(model=embedding_model_name, content=batch_docs, task_type="RETRIEVAL_DOCUMENT")
                if 'embedding' in result and result['embedding']:
                    batch_embeddings = result['embedding']; all_embeddings.extend(batch_embeddings); embeddings_generated_count += len(batch_embeddings)
                else: print(f"  Warning: No embeddings returned for batch {i+1}.")
                time.sleep(1)
            except Exception as e: print(f"  Error embedding batch {i+1}: {e}"); return False
        print(f"Generated {embeddings_generated_count} embeddings.")
        if embeddings_generated_count != len(documents_to_add): print(f"Error: Embedding count mismatch. Aborting add."); return False
        print(f"Adding {len(ids_to_add)} items to ChromaDB collection...")
        try:
            collection.add(ids=ids_to_add, embeddings=all_embeddings, documents=documents_to_add, metadatas=metadatas_to_add)
            print("ChromaDB collection populated successfully."); return True
        except Exception as e: print(f"Error adding data to ChromaDB: {e}")
    except Exception as e: print(f"Unexpected error during ChromaDB init: {e}")
    return False

# --- Main Execution Block ---
if __name__ == '__main__':
    print("--- Running Knowledge Base Initialization with Employee Holdings ---")

    # 1. Generate Data
    # Parameters can be adjusted here or loaded from config
    data = generate_data_with_holdings(
        num_employees=1000, num_roles=30, num_projects=60, num_apps=60,
        avg_ents_per_app=7, avg_proj_per_emp=1.5
    )

    # Check if generation was successful
    if not all([data.get(k) for k in ['PROJECTS', 'ROLES', 'APPLICATIONS', 'ENTITLEMENTS', 'EMPLOYEES']]):
         print("\nError: Base data generation failed or produced empty lists. Aborting initialization.")
    else:
        # 2. Initialize SQLite
        sqlite_success = init_sqlite_employee_db(SQLITE_DB_FILE, data)

        # 3. Initialize ChromaDB (requires API Key)
        if GOOGLE_API_KEY:
            chroma_success = init_chromadb(
                db_path=CHROMA_DB_PATH,
                collection_name=CHROMA_COLLECTION_NAME,
                entitlements=data['ENTITLEMENTS'],
                embedding_model_name=EMBEDDING_MODEL,
                api_key=GOOGLE_API_KEY
            )
        else:
            print("\nSkipping ChromaDB initialization: GOOGLE_API_KEY not found in environment.")
            chroma_success = False

        # 4. Visualize Data (Optional)
        if os.getenv('VISUALIZE', 'False').lower() == 'true':
             visualize_employee_data(data)
        else:
            print("\nSkipping visualization (set VISUALIZE=True environment variable to enable).")

    print("\n--- Knowledge Base Initialization Script Finished ---")

