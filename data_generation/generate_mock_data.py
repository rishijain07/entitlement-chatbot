# data_generation/generate_mock_data.py
# Updated to generate detailed employee holdings data.

import random
import re
from faker import Faker
from collections import defaultdict
import pandas as pd
import math

# Initialize Faker globally for helpers
fake = Faker()

# --- Helper Functions ---
# (Same helper functions: generate_unique, get_role_level, get_entitlement_description)
def generate_unique(generator_func, existing_set, max_attempts=100):
    for _ in range(max_attempts):
        value = generator_func()
        if value not in existing_set:
            existing_set.add(value)
            return value
    unique_value = f"{generator_func()}_{fake.uuid4()[:4]}"
    existing_set.add(unique_value)
    print(f"Warning: Had to generate fallback unique value: {unique_value}")
    return unique_value

def get_role_level(role_name):
    name_lower = role_name.lower()
    if re.search(r'\bmanager\b|\bdirector\b', name_lower): return 5
    if re.search(r'\blead\b|\bprincipal\b', name_lower): return 4
    if re.search(r'\bsenior\b|\bsr\.\b', name_lower): return 3
    if re.search(r'\bjr\.\b|\bjunior\b|\bassistant\b|\bassociate\b', name_lower): return 1
    if re.search(r'\bdeveloper\b|\bengineer\b|\banalyst\b|\btester\b|\badministrator\b|\bofficer\b', name_lower): return 2
    return random.choice([1, 2, 3])

def get_entitlement_description(action, app_name):
    action_lower = action.lower()
    verb_map = {
        'READ': f"view data within the {app_name}", 'WRITE': f"create or modify data in the {app_name}",
        'DELETE': f"delete data from the {app_name}", 'EXECUTE': f"execute specific tasks or jobs using the {app_name}",
        'ADMIN': f"perform administrative functions for the {app_name}", 'VIEW': f"view information or dashboards in the {app_name}",
        'CREATE': f"create new records or items in the {app_name}", 'APPROVE': f"approve requests or workflows within the {app_name}",
        'CONFIG': f"configure settings for the {app_name}", 'AUDIT': f"access audit logs or perform audits related to the {app_name}",
        'MANAGE': f"manage resources or processes within the {app_name}"}
    default_desc = f"perform '{action_lower}' operations related to the {app_name}"
    return f"Grants permission to {verb_map.get(action, default_desc)}."


# --- Main Generation Function ---
def generate_data_with_holdings(
    num_employees=1000, num_roles=30, num_projects=60, num_apps=60,
    avg_ents_per_app=7, avg_proj_per_emp=1.5):
    """
    Generates base data (Projects, Roles, Apps, Entitlements) and detailed
    Employee data including their assigned projects and specific entitlement holdings.

    Returns:
        dict: A dictionary containing all generated data lists.
    """
    print("--- Starting Data Generation with Employee Holdings ---")
    # (Same generation logic as in colab_generate_employee_holdings_py)
    # ... (Full function logic pasted here for completeness) ...
    # Data Storage Lists
    PROJECTS, ROLES, APPLICATIONS, ENTITLEMENTS = [], [], [], []
    APP_ENTITLEMENT_MAPPINGS = []
    EMPLOYEES = []
    EMPLOYEE_PROJECT_ASSIGNMENTS = []
    EMPLOYEE_ENTITLEMENT_HOLDINGS = []
    # --- Part 1: Generate Base Data ---
    print("--- Part 1: Generating Base Data ---")
    role_names = set()
    common_roles = [ # Expanded list
        'Junior Software Developer', 'Software Developer', 'Senior Software Developer', 'Lead Software Developer', 'Principal Software Engineer',
        'QA Tester', 'Senior QA Tester', 'Test Lead', 'QA Manager', 'Project Manager', 'Senior Project Manager', 'Program Manager', 'Portfolio Manager',
        'Business Analyst', 'Senior Business Analyst', 'Lead Business Analyst', 'System Administrator', 'Senior System Administrator', 'Cloud Engineer',
        'DevOps Engineer', 'Senior DevOps Engineer', 'Database Administrator', 'Senior Database Administrator', 'Security Analyst', 'Senior Security Analyst',
        'Lead Security Analyst', 'Security Architect', 'Branch Operations Manager', 'Loan Processing Officer', 'Senior Loan Officer', 'Credit Risk Analyst',
        'Senior Credit Risk Analyst', 'Compliance Officer', 'Internal Auditor', 'Relationship Manager', 'IT Support Specialist', 'Data Scientist',
        'Data Engineer', 'Machine Learning Engineer']
    random.shuffle(common_roles)
    for common_role in common_roles:
         if len(ROLES) < num_roles and common_role not in role_names:
                role_names.add(common_role)
                ROLES.append({'id': len(ROLES) + 1, 'name': common_role, 'level': get_role_level(common_role)})
    while len(ROLES) < num_roles:
        role_name = generate_unique(fake.job, role_names)
        if not any(keyword in role_name.lower() for keyword in ['manager', 'lead', 'senior', 'junior', 'principal']):
            ROLES.append({'id': len(ROLES) + 1, 'name': role_name, 'level': get_role_level(role_name)})
        if len(ROLES) >= num_roles : break
    role_ids = [r['id'] for r in ROLES]
    role_level_map = {r['id']: r['level'] for r in ROLES}
    project_names = set()
    for i in range(num_projects):
        project_name = generate_unique(fake.bs, project_names)
        PROJECTS.append({'id': i + 1, 'name': project_name.title(), 'description': fake.catch_phrase()})
    project_ids = [p['id'] for p in PROJECTS]
    BANK_APPS = [ # Base list
        {'name': 'Branch Customer Portal', 'description': 'Web portal for branch staff.'}, {'name': 'Core Banking System (CBS)', 'description': 'Main system for accounts.'},
        {'name': 'Home Loan Origination', 'description': 'Home loan application process.'}, {'name': 'Auto Loan Processing', 'description': 'Auto loan application process.'},
        {'name': 'Customer Data Hub (CDH)', 'description': 'Central customer data repository.'}, {'name': 'Transaction Monitoring Engine', 'description': 'Detects suspicious transactions.'},
        {'name': 'Risk Analysis Platform', 'description': 'Credit risk assessment.'}, {'name': 'Compliance Checker Service', 'description': 'Verifies regulatory compliance.'},
        {'name': 'Payments Gateway', 'description': 'Handles payment processing.'}, {'name': 'Authentication Service (SSO)', 'description': 'Single Sign-On service.'},
        {'name': 'API Management Gateway', 'description': 'Manages API access.'}, {'name': 'Document Management System (DMS)', 'description': 'Stores documents.'},
        {'name': 'Branch Governance Dashboard', 'description': 'Branch performance overview.'}, {'name': 'Teller Assist Application', 'description': 'Application for bank tellers.'},
        {'name': 'Investment Portfolio Manager', 'description': 'Tracks client investments.'}, {'name': 'Fraud Detection Analytics', 'description': 'Analytics for fraud teams.'},
        {'name': 'Regulatory Reporting System', 'description': 'Generates regulatory reports.'}, {'name': 'Internal Workflow Orchestrator', 'description': 'Manages business processes.'},
        {'name': 'Data Warehouse (DWH)', 'description': 'Repository for analytics.'}, {'name': 'IT Service Management (ITSM)', 'description': 'Manages IT incidents/requests.'},
    ]
    num_fake_apps_needed = num_apps - len(BANK_APPS)
    if num_fake_apps_needed > 0:
        fake_apps = [{'name': fake.company() + random.choice([" Suite", " Platform", " Service", " Hub"]), 'description': fake.catch_phrase()} for _ in range(num_fake_apps_needed)]
        BANK_APPS.extend(fake_apps)
    entitlement_codes = set(); current_entitlement_id = 100; app_id_counter = 1
    app_subset = BANK_APPS[:num_apps]; entitlements_by_app = defaultdict(list)
    for app_data in app_subset:
        app_name = app_data['name']; app_description = app_data['description']
        app_code = f"APP{app_id_counter:03d}"; app_id = app_id_counter; app_id_counter += 1
        APPLICATIONS.append({'id': app_id, 'name': app_name, 'description': app_description})
        num_entitlements = random.randint(max(1, avg_ents_per_app - 1), avg_ents_per_app + 2)
        possible_actions = ['READ', 'WRITE', 'EXECUTE', 'ADMIN', 'VIEW', 'CREATE', 'DELETE', 'APPROVE', 'CONFIG', 'AUDIT', 'MANAGE', 'REPORT', 'SEARCH']
        actions = random.sample(possible_actions, min(num_entitlements, len(possible_actions)))
        for action in actions:
            entitlement_code = f"{app_code}_{action}"
            if entitlement_code not in entitlement_codes:
                entitlement_codes.add(entitlement_code); current_entitlement_id += 1; entitlement_id = current_entitlement_id
                ent_data = {'id': entitlement_id, 'code': entitlement_code, 'description': get_entitlement_description(action, app_name)}
                ENTITLEMENTS.append(ent_data); APP_ENTITLEMENT_MAPPINGS.append({'app_id': app_id, 'entitlement_id': entitlement_id})
                entitlements_by_app[app_id].append(entitlement_id)
    all_entitlement_ids = [e['id'] for e in ENTITLEMENTS]
    print(f"Generated {len(PROJECTS)}P, {len(ROLES)}R, {len(APPLICATIONS)}A, {len(ENTITLEMENTS)}E")
    # --- Part 2: Generate Employees and Assign Holdings ---
    print("--- Part 2: Generating Employees and Assigning Holdings ---")
    core_entitlement_ids = random.sample(all_entitlement_ids, k=min(5, len(all_entitlement_ids))) if all_entitlement_ids else []
    for i in range(num_employees):
        emp_id = 1000 + i
        if not role_ids: continue
        assigned_role_id = random.choice(role_ids)
        emp_name = fake.name(); emp_email = f"{emp_name.lower().replace(' ', '.').replace(',','').replace('-','')}{random.randint(1,999)}@example.bank"
        EMPLOYEES.append({'id': emp_id, 'name': emp_name, 'email': emp_email, 'role_id': assigned_role_id})
        if(emp_id % 500 == 0): print(f"Generated {emp_id} - {emp_name} ({emp_email})")
        assigned_project_ids = []
        if project_ids:
            num_projects = max(1, int(random.gauss(avg_proj_per_emp, 0.5)))
            assigned_project_ids = random.sample(project_ids, min(num_projects, len(project_ids)))
            for proj_id in assigned_project_ids: EMPLOYEE_PROJECT_ASSIGNMENTS.append({'employee_id': emp_id, 'project_id': proj_id})
        role_level = role_level_map.get(assigned_role_id, 2); current_emp_entitlements = set()
        if not all_entitlement_ids: continue
        for core_id in core_entitlement_ids:
            if random.random() < 0.95: current_emp_entitlements.add(core_id)
        num_role_specific = 0
        if role_level == 5 and random.random() < 0.8: num_role_specific = random.randint(1, 3)
        elif role_level == 4 and random.random() < 0.7: num_role_specific = random.randint(2, 4)
        elif role_level <= 3 and random.random() < 0.6: num_role_specific = random.randint(1, 5)
        potential_role_entitlements = []
        for ent in ENTITLEMENTS:
            code = ent['code']
            if role_level == 5 and ('_APPROVE' in code or '_ADMIN' in code): potential_role_entitlements.append(ent['id'])
            elif role_level == 4 and ('_ADMIN' in code or '_CONFIG' in code): potential_role_entitlements.append(ent['id'])
            elif role_level <= 3 and ('_WRITE' in code or '_EXECUTE' in code or '_CREATE' in code or '_DELETE' in code): potential_role_entitlements.append(ent['id'])
            elif '_READ' in code or '_VIEW' in code: potential_role_entitlements.append(ent['id'])
        if potential_role_entitlements: current_emp_entitlements.update(random.sample(potential_role_entitlements, min(num_role_specific, len(potential_role_entitlements))))
        num_project_specific = random.randint(3, 10); current_emp_entitlements.update(random.sample(all_entitlement_ids, min(num_project_specific, len(all_entitlement_ids))))
        if random.random() < 0.1 and current_emp_entitlements: current_emp_entitlements.discard(random.choice(list(current_emp_entitlements)))
        if random.random() < 0.15: current_emp_entitlements.add(random.choice(all_entitlement_ids))
        for ent_id in current_emp_entitlements: EMPLOYEE_ENTITLEMENT_HOLDINGS.append({'employee_id': emp_id, 'entitlement_id': ent_id})
    print(f"Generated {len(EMPLOYEES)} employees, {len(EMPLOYEE_PROJECT_ASSIGNMENTS)} assignments, {len(EMPLOYEE_ENTITLEMENT_HOLDINGS)} holdings.")
    print("--- Data Generation Complete ---")
    return {'PROJECTS': PROJECTS, 'ROLES': ROLES, 'APPLICATIONS': APPLICATIONS, 'ENTITLEMENTS': ENTITLEMENTS,
            'APP_ENTITLEMENT_MAPPINGS': APP_ENTITLEMENT_MAPPINGS, 'EMPLOYEES': EMPLOYEES,
            'EMPLOYEE_PROJECT_ASSIGNMENTS': EMPLOYEE_PROJECT_ASSIGNMENTS, 'EMPLOYEE_ENTITLEMENT_HOLDINGS': EMPLOYEE_ENTITLEMENT_HOLDINGS}

# Example usage (if run directly)
if __name__ == '__main__':
    print("Running data generation standalone...")
    generated_data = generate_data_with_holdings(num_employees=50) # Smaller for test
    print("\n--- Standalone Run Summary ---")
    print(f"Generated Employees: {len(generated_data['EMPLOYEES'])}")
    print(f"Generated Holdings: {len(generated_data['EMPLOYEE_ENTITLEMENT_HOLDINGS'])}")

