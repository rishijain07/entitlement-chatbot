# data_generation/visualize_db_data.py
# Connects to the existing SQLite database, prints sample data,
# and generates visualizations based on the stored employee holdings data.
# ** Updated to show sample data first and use single plt.show(). **

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from dotenv import load_dotenv

# Load environment variables (optional, for DB path override)
load_dotenv()

# --- Configuration ---
# Use environment variable or default to the name used in initialize_kb.py
SQLITE_DB_FILE = os.getenv('SQLITE_DB_FILE', 'entitlements_employee_db.db')

def visualize_data_from_db(db_file):
    """
    Connects to the database, prints sample data, queries full data,
    and generates visualizations.
    """
    print(f"--- Attempting to visualize data from: {db_file} ---")

    if not os.path.exists(db_file):
        print(f"Error: Database file not found at '{db_file}'.")
        print("Please run the 'initialize_kb.py' script first.")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print("Connected to SQLite database.")

        # --- Print Sample Data from Tables ---
        print("\n--- Sample Data from Database Tables (First 5 Rows) ---")
        tables_to_sample = [
            "Projects", "Roles", "Applications", "Entitlements",
            "Employees", "AppEntitlementMappings",
            "EmployeeProjectAssignments", "EmployeeEntitlementHoldings"
        ]
        for table_name in tables_to_sample:
            print(f"\nSample from '{table_name}':")
            try:
                # Query first 5 rows (or use ORDER BY RANDOM() LIMIT 5 for random sample)
                query = f"SELECT * FROM {table_name} LIMIT 5"
                # query = f"SELECT * FROM {table_name} ORDER BY RANDOM() LIMIT 5" # Alternative for random sample
                sample_df = pd.read_sql_query(query, conn)
                if not sample_df.empty:
                    print(sample_df.to_markdown(index=False))
                else:
                    print(f"Table '{table_name}' is empty or query failed.")
            except Exception as e:
                print(f"Could not query table '{table_name}'. Error: {e}")

        # --- Load Full Data into Pandas DataFrames for Plotting ---
        print("\n--- Loading full data for visualizations ---")
        try:
            employees_df = pd.read_sql_query("SELECT * FROM Employees", conn)
            roles_df = pd.read_sql_query("SELECT * FROM Roles", conn)
            projects_df = pd.read_sql_query("SELECT * FROM Projects", conn)
            emp_proj_df = pd.read_sql_query("SELECT * FROM EmployeeProjectAssignments", conn)
            emp_hold_df = pd.read_sql_query("SELECT * FROM EmployeeEntitlementHoldings", conn)
            print("Full data loaded successfully.")
        except Exception as e:
            print(f"Error loading full data from tables: {e}")
            print("Make sure the database schema matches the expected tables.")
            return # Stop if data loading fails

        # --- Generate Visualizations ---
        print("\n--- Generating Visualizations (will display at the end) ---")
        sns.set_theme(style="whitegrid")
        plot_generated = False # Flag to track if any plot was created

        # Plot 1: Employee Role Distribution
        if not employees_df.empty and not roles_df.empty:
             print("Configuring: Employee Role Distribution plot...")
             emp_roles = pd.merge(employees_df, roles_df, left_on='role_id', right_on='id', how='left')
             emp_roles['name_y'] = emp_roles['name_y'].fillna('Unknown Role')
             plt.figure(figsize=(12, 8))
             plot_order = emp_roles['name_y'].value_counts().index
             sns.countplot(data=emp_roles, y='name_y', order=plot_order, palette='viridis')
             plt.title('Distribution of Employees per Role')
             plt.xlabel('Number of Employees'); plt.ylabel('Role Name')
             plt.tight_layout()
             plot_generated = True
        else:
             print("Skipping Employee Role Distribution plot (data empty/missing).")

        # Plot 2: Projects per Employee Distribution
        if not emp_proj_df.empty:
            print("Configuring: Projects per Employee Distribution plot...")
            projs_per_emp = emp_proj_df.groupby('employee_id').size()
            plt.figure(figsize=(10, 6))
            sns.histplot(projs_per_emp, bins=max(1, int(projs_per_emp.max()) if not projs_per_emp.empty else 1), kde=False) # Ensure bins >= 1
            plt.title('Distribution of Projects Assigned per Employee')
            plt.xlabel('Number of Projects Assigned'); plt.ylabel('Number of Employees')
            plt.tight_layout()
            plot_generated = True
        else:
            print("Skipping Projects per Employee plot (data empty/missing).")

        # Plot 3: Entitlements per Employee Distribution
        if not emp_hold_df.empty:
            print("Configuring: Entitlements per Employee Distribution plot...")
            ents_per_emp = emp_hold_df.groupby('employee_id').size()
            plt.figure(figsize=(10, 6))
            sns.histplot(ents_per_emp, bins=20, kde=True)
            plt.title('Distribution of Entitlements Held per Employee')
            plt.xlabel('Number of Entitlements Held'); plt.ylabel('Number of Employees')
            plt.tight_layout()
            plot_generated = True
        else:
            print("Skipping Entitlements per Employee plot (data empty/missing).")

        # Plot 4: Employees per Project
        if not emp_proj_df.empty and not projects_df.empty:
            print("Configuring: Employees per Project plot...")
            emps_per_proj = emp_proj_df.groupby('project_id')['employee_id'].nunique().reset_index(name='employee_count')
            emps_per_proj = pd.merge(emps_per_proj, projects_df[['id', 'name']], left_on='project_id', right_on='id', how='left')
            emps_per_proj['name'] = emps_per_proj['name'].fillna('Unknown Project')
            plt.figure(figsize=(12, 10))
            display_limit = 40
            plot_data = emps_per_proj.nlargest(display_limit, 'employee_count') if len(emps_per_proj) > display_limit else emps_per_proj.sort_values('employee_count', ascending=False)
            sns.barplot(data=plot_data, x='employee_count', y='name', palette='coolwarm', orient='h')
            plt.title(f'Number of Employees Assigned per Project (Top {len(plot_data)})')
            plt.xlabel('Number of Employees'); plt.ylabel('Project Name')
            plt.tight_layout()
            plot_generated = True
        else:
            print("Skipping Employees per Project plot (data empty/missing).")

        # --- Display All Plots ---
        if plot_generated:
            print("\nDisplaying all generated plots...")
            plt.show() # Single call to display all figures created above
        else:
            print("\nNo plots were generated.")

    except sqlite3.Error as e:
        print(f"SQLite error during data loading or processing: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Main Execution Block ---
if __name__ == '__main__':
    visualize_data_from_db('D:\Projects\entitlement-chatbot\entitlements_employee_db.db')
