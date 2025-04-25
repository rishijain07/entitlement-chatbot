# data_generation/initialize_kb.py
# Initializes the knowledge base (SQLite and ChromaDB) using generated data.
# Should be run after reviewing/confirming generation parameters.

import sqlite3
import chromadb
import google.generativeai as genai
import os
import time
import math
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv # To load .env file for API key

# Import the generation function
from generate_mock_data import generate_all_data

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# These could also be loaded from a config file or environment variables
SQLITE_DB_FILE = os.getenv('SQLITE_DB_FILE', 'entitlements_inferred.db')
CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH', './chroma_db_inferred')
CHROMA_COLLECTION_NAME = os.getenv('CHROMA_COLLECTION_NAME', 'entitlement_docs_inferred')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'models/embedding-001')
EMBEDDING_BATCH_SIZE = 100
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') # Get API key from environment

# --- Visualization Function (Optional, moved here from generator) ---
def visualize_generated_data(employees_list, roles, projects, applications, app_ent_maps, role_proj_maps, analysis_df=None, inferred_mappings_df=None, freq_threshold=0.7):
    """Generates and displays visualizations of the mock data."""
    print("\n--- Generating Visualizations ---")
    try:
        sns.set_theme(style="whitegrid")
        roles_df = pd.DataFrame(roles)
        projects_df = pd.DataFrame(projects)
        apps_df = pd.DataFrame(applications)
        app_ent_map_df = pd.DataFrame(app_ent_maps)
        role_proj_map_df = pd.DataFrame(role_proj_maps) # Inferred mappings
        employees_df = pd.DataFrame(employees_list)

        # Plot 1: Role Distribution
        if not roles_df.empty:
            plt.figure(figsize=(10, 6)); level_order = sorted(roles_df['level'].unique())
            sns.countplot(data=roles_df, x='level', order=level_order, palette='viridis')
            plt.title('Distribution of Roles by Hierarchy Level'); plt.xlabel('Role Level (1=Junior, 5=Manager)'); plt.ylabel('Number of Roles'); plt.tight_layout(); plt.show()

        # Plot 2: Entitlements per App
        if not app_ent_map_df.empty and not apps_df.empty:
            ent_per_app = app_ent_map_df.groupby('app_id').size().reset_index(name='entitlement_count')
            ent_per_app = pd.merge(ent_per_app, apps_df[['id', 'name']], left_on='app_id', right_on='id', how='left')
            plt.figure(figsize=(12, 10)); display_limit = 40
            plot_data = ent_per_app.nlargest(display_limit, 'entitlement_count') if len(ent_per_app) > display_limit else ent_per_app.sort_values('entitlement_count', ascending=False)
            sns.barplot(data=plot_data, x='entitlement_count', y='name', palette='magma', orient='h')
            plt.title(f'Number of Entitlements per Application (Top {len(plot_data)})'); plt.xlabel('Number of Entitlements'); plt.ylabel('Application Name'); plt.tight_layout(); plt.show()

        # Plot 3: Frequency Distribution
        if analysis_df is not None and not analysis_df.empty:
            plt.figure(figsize=(10, 6)); sns.histplot(analysis_df['frequency'], bins=20, kde=False)
            plt.title('Distribution of Entitlement Frequencies within Profiles'); plt.xlabel('Frequency'); plt.ylabel('Count of Project/Role/Entitlement Combinations')
            plt.axvline(freq_threshold, color='r', linestyle='--', label=f'Threshold ({freq_threshold})'); plt.legend(); plt.tight_layout(); plt.show()

        # Plot 4: Inferred Mappings per Project
        if inferred_mappings_df is not None and not inferred_mappings_df.empty and not projects_df.empty:
            inferred_per_project = inferred_mappings_df.groupby('project_id').size().reset_index(name='inferred_count')
            inferred_per_project = pd.merge(inferred_per_project, projects_df[['id', 'name']], left_on='project_id', right_on='id', how='left')
            inferred_per_project['name'] = inferred_per_project['name'].fillna('Unknown Project')
            plt.figure(figsize=(12, 10)); display_limit = 40
            plot_data = inferred_per_project.nlargest(display_limit, 'inferred_count') if len(inferred_per_project) > display_limit else inferred_per_project.sort_values('inferred_count', ascending=False)
            sns.barplot(data=plot_data, x='inferred_count', y='name', palette='viridis', orient='h')
            plt.title(f'Number of Inferred Mappings per Project (Top {len(plot_data)})'); plt.xlabel('Number of Inferred Mappings'); plt.ylabel('Project Name'); plt.tight_layout(); plt.show()

        # Plot 5: Employees per Project
        if not employees_df.empty and 'project_ids' in employees_df.columns and not projects_df.empty:
            emp_proj_df = employees_df.explode('project_ids'); emp_proj_df.rename(columns={'project_ids': 'project_id', 'id': 'employee_id'}, inplace=True)
            emp_proj_df = emp_proj_df.dropna(subset=['project_id'])
            employees_per_project = emp_proj_df.groupby('project_id')['employee_id'].nunique().reset_index(name='employee_count')
            employees_per_project = pd.merge(employees_per_project, projects_df[['id', 'name']], left_on='project_id', right_on='id', how='left')
            employees_per_project['name'] = employees_per_project['name'].fillna('Unknown Project')
            plt.figure(figsize=(12, 10)); display_limit = 40
            plot_data = employees_per_project.nlargest(display_limit, 'employee_count') if len(employees_per_project) > display_limit else employees_per_project.sort_values('employee_count', ascending=False)
            sns.barplot(data=plot_data, x='employee_count', y='name', palette='coolwarm', orient='h')
            plt.title(f'Number of Unique Employees Assigned per Project (Top {len(plot_data)})'); plt.xlabel('Number of Employees'); plt.ylabel('Project Name'); plt.tight_layout(); plt.show()

        print("--- Visualizations Complete ---")
    except Exception as e:
        print(f"Error during visualization: {e}")


# --- SQLite Initialization ---
def init_sqlite(db_file, projects, roles, applications, entitlements, role_proj_maps, app_ent_maps):
    """Creates and populates the SQLite database."""
    print(f"\n--- Initializing SQLite database: {db_file}... ---")
    # (Same init_sqlite function as in Colab script)
    if not all([projects, roles, applications, entitlements]):
         print("Error: Base data lists are empty. Cannot initialize DB.")
         return False
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        print("Dropping existing tables (if they exist)...")
        cursor.execute("DROP TABLE IF EXISTS RoleProjectMappings"); cursor.execute("DROP TABLE IF EXISTS AppEntitlementMappings")
        cursor.execute("DROP TABLE IF EXISTS Entitlements"); cursor.execute("DROP TABLE IF EXISTS Applications")
        cursor.execute("DROP TABLE IF EXISTS Roles"); cursor.execute("DROP TABLE IF EXISTS Projects")
        print("Creating tables...")
        cursor.execute('CREATE TABLE Projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT)')
        cursor.execute('CREATE TABLE Roles (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, level INTEGER NOT NULL)')
        cursor.execute('CREATE TABLE Applications (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT)')
        cursor.execute('CREATE TABLE Entitlements (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, description TEXT NOT NULL)')
        cursor.execute('CREATE TABLE AppEntitlementMappings (app_id INTEGER NOT NULL, entitlement_id INTEGER NOT NULL, FOREIGN KEY (app_id) REFERENCES Applications (id), FOREIGN KEY (entitlement_id) REFERENCES Entitlements (id), PRIMARY KEY (app_id, entitlement_id))')
        cursor.execute('CREATE TABLE RoleProjectMappings (role_id INTEGER NOT NULL, project_id INTEGER NOT NULL, entitlement_id INTEGER NOT NULL, FOREIGN KEY (role_id) REFERENCES Roles (id), FOREIGN KEY (project_id) REFERENCES Projects (id), FOREIGN KEY (entitlement_id) REFERENCES Entitlements (id))')
        print("Inserting data...")
        cursor.executemany("INSERT INTO Projects (id, name, description) VALUES (:id, :name, :description)", projects)
        cursor.executemany("INSERT INTO Roles (id, name, level) VALUES (:id, :name, :level)", roles)
        cursor.executemany("INSERT INTO Applications (id, name, description) VALUES (:id, :name, :description)", applications)
        cursor.executemany("INSERT INTO Entitlements (id, code, description) VALUES (:id, :code, :description)", entitlements)
        if app_ent_maps: cursor.executemany("INSERT INTO AppEntitlementMappings (app_id, entitlement_id) VALUES (:app_id, :entitlement_id)", app_ent_maps)
        if role_proj_maps: cursor.executemany("INSERT INTO RoleProjectMappings (role_id, project_id, entitlement_id) VALUES (:role_id, :project_id, :entitlement_id)", role_proj_maps)
        conn.commit()
        print("SQLite database initialized successfully.")
        return True
    except sqlite3.Error as e: print(f"SQLite error: {e}"); conn.rollback()
    except Exception as e: print(f"Unexpected error during SQLite init: {e}"); conn.rollback()
    finally:
        if conn: conn.close()
    return False

# --- ChromaDB Initialization ---
def init_chromadb(db_path, collection_name, entitlements, embedding_model_name, api_key):
    """Initializes ChromaDB, generates embeddings, and stores entitlement data."""
    print(f"\n--- Initializing ChromaDB collection: {collection_name} at {db_path}... ---")
    # (Same init_chromadb function as in Colab script, but takes api_key)
    if not entitlements: print("No entitlements found. Skipping."); return False
    if not api_key: print("Google API Key not provided. Skipping ChromaDB init."); return False

    try:
        genai.configure(api_key=api_key) # Configure within function scope if needed
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
            print("ChromaDB collection populated successfully.")
            return True
        except Exception as e: print(f"Error adding data to ChromaDB: {e}")
    except Exception as e: print(f"Unexpected error during ChromaDB init: {e}")
    return False

# --- Main Execution Block ---
if __name__ == '__main__':
    print("--- Running Knowledge Base Initialization ---")

    # 1. Generate Data
    # Parameters can be adjusted here or loaded from config
    data = generate_all_data(
        num_employees=1000,
        num_roles=30,
        num_projects=60,
        num_apps=60,
        avg_ents_per_app=7,
        avg_proj_per_emp=1.5,
        freq_threshold=0.70
    )

    # Check if generation was successful before proceeding
    if not all([data['PROJECTS'], data['ROLES'], data['APPLICATIONS'], data['ENTITLEMENTS']]):
         print("\nError: Base data generation failed or produced empty lists. Aborting initialization.")
    else:
        # 2. Initialize SQLite
        sqlite_success = init_sqlite(
            db_file=SQLITE_DB_FILE,
            projects=data['PROJECTS'],
            roles=data['ROLES'],
            applications=data['APPLICATIONS'],
            entitlements=data['ENTITLEMENTS'],
            role_proj_maps=data['ROLE_PROJECT_MAPPINGS'], # Use inferred mappings
            app_ent_maps=data['APP_ENTITLEMENT_MAPPINGS']
        )

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
        # Set VISUALIZE=True in environment or uncomment to run
        if os.getenv('VISUALIZE', 'False').lower() == 'true':
             visualize_generated_data(
                 employees_list=data['employees'],
                 roles=data['ROLES'], projects=data['PROJECTS'], applications=data['APPLICATIONS'],
                 app_ent_maps=data['APP_ENTITLEMENT_MAPPINGS'], role_proj_maps=data['ROLE_PROJECT_MAPPINGS'],
                 analysis_df=data['analysis_df'], inferred_mappings_df=data['inferred_mappings_df'],
                 freq_threshold=data.get('freq_threshold', 0.70) # Pass threshold used
             )
        else:
            print("\nSkipping visualization (set VISUALIZE=True environment variable to enable).")


    print("\n--- Knowledge Base Initialization Script Finished ---")

