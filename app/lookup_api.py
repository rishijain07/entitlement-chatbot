# app/lookup_api.py
# Blueprint for the Entitlement Lookup API endpoint.

import time
import sqlite3
from flask import Blueprint, request, jsonify, current_app
from . import utils # Use utils to get DB connection

# Create Blueprint
lookup_bp = Blueprint('lookup_api', __name__, url_prefix='/api') # Add prefix

@lookup_bp.route('/entitlements', methods=['GET'])
def get_entitlements_by_email():
    """
    Looks up and returns the list of entitlement codes held by an employee,
    based on their email address queried from the database.
    Expects email as a query parameter: /api/entitlements?email=user@example.com
    """
    start_time = time.time()
    email = request.args.get('email')

    if not email:
        return jsonify({"error": "Missing 'email' query parameter"}), 400

    print(f"Received request at /api/entitlements for email: {email}")

    conn = utils.get_db_connection() # Get DB connection from utils
    if not conn:
        return jsonify({"error": "Database connection failed"}), 503

    entitlement_list = []
    employee_id = None
    status_code = 500
    response_data = {"error": "Failed to retrieve entitlements"}

    try:
        cursor = conn.cursor()
        # Step 1: Find Employee ID from Email
        cursor.execute("SELECT id FROM Employees WHERE email = ?", (email,))
        employee_row = cursor.fetchone()

        if employee_row:
            employee_id = employee_row['id']
            # Step 2: Lookup entitlements using Employee ID
            query = """
                SELECT E.code
                FROM EmployeeEntitlementHoldings EH
                JOIN Entitlements E ON EH.entitlement_id = E.id
                WHERE EH.employee_id = ?
            """
            cursor.execute(query, (employee_id,))
            entitlement_rows = cursor.fetchall()
            entitlement_list = [row['code'] for row in entitlement_rows]
            response_data = { "email": email, "employee_id_found": employee_id, "entitlements": entitlement_list }
            status_code = 200 # OK
        else:
            response_data = {"error": f"Employee not found for email: {email}"}
            status_code = 404 # Not Found

    except sqlite3.Error as e:
        print(f"  SQLite query error in lookup API: {e}")
        response_data = {"error": "Database query error"}
        status_code = 500
    except Exception as e:
        print(f"  Unexpected error in lookup API: {e}")
        response_data = {"error": "An unexpected error occurred"}
        status_code = 500
    # DB connection closed automatically by teardown context

    processing_time = time.time() - start_time
    print(f"Lookup API finished in {processing_time:.2f}s")
    return jsonify(response_data), status_code

