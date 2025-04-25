# run.py
# Main entry point to run the Flask application development server.

from app import create_app # Import the app factory function from the app package
import os

# Create the Flask app instance using the factory function
# This will load configuration from app.config based on environment variables
app = create_app()

if __name__ == '__main__':
    # Get debug status from environment variable or config
    # Defaulting to False if not explicitly set to True
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"Starting Flask app with debug mode: {debug_mode}")
    # Run the Flask development server
    # host='0.0.0.0' makes the server accessible from other devices on the network
    # In production, use a proper WSGI server like Gunicorn or Waitress
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

