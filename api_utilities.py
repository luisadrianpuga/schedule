import os
import json
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, g
from sqlite_setup import AppointmentSystemDB

# Configure the database path
DB_FILE = os.environ.get('DB_FILE', 'appointment_system.db')

def get_db():
    """Get database connection for the current request."""
    if not hasattr(g, 'db'):
        g.db = AppointmentSystemDB(DB_FILE)
        g.db.connect()
    return g.db

def close_db(e=None):
    """Close database connection at the end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    """Initialize the Flask application with database handling."""
    app.teardown_appcontext(close_db)

# Authentication utilities
def hash_password(password):
    """Hash a password for storage."""
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 150000)
    return f"pbkdf2:sha256:150000${salt}${h.hex()}"

def verify_password(stored_hash, password):
    """Verify a password against its stored hash."""
    if not stored_hash or not password:
        return False
    
    try:
        # Parse the format "pbkdf2:sha256:150000$salt$hash"
        algorithm_parts = stored_hash.split('$')[0].split(':')
        if len(algorithm_parts) != 3:
            return False
            
        hash_name = algorithm_parts[1]
        iterations = int(algorithm_parts[2])
        
        parts = stored_hash.split('$')
        if len(parts) != 3:
            return False
            
        salt = parts[1]
        stored_hash_value = parts[2]
        
        computed_hash = hashlib.pbkdf2_hmac(
            hash_name, password.encode(), salt.encode(), iterations
        ).hex()
        return secrets.compare_digest(computed_hash, stored_hash_value)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False
def auth_required(roles=None):
    """Decorator to require authentication for a route."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get auth token from header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "Authorization header missing or invalid"}), 401
            
            token = auth_header.split(' ')[1]
            
            # Verify token
            db = get_db()
            user_id, token_type = db.verify_auth_token(token)
            
            if not user_id:
                return jsonify({"error": "Invalid or expired token"}), 401
            
            # Get user details
            user = db.get_user_by_id(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 401
            
            # Check if user is active
            if not user['is_active']:
                return jsonify({"error": "User account is inactive"}), 403
            
            # Check role if required
            user_roles = db.get_user_roles(user_id)
            user_role_names = [r['name'] for r in user_roles]
            
            # Store user in g for the view function
            g.user = dict(user)
            g.user['roles'] = user_role_names
            
            if roles:
                # Convert roles to list if it's a string
                required_roles = [roles] if isinstance(roles, str) else roles
                    
                if not any(role in user_role_names for role in required_roles):
                    return jsonify({"error": "Insufficient permissions"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Response utilities
def success_response(data=None, message=None, status_code=200):
    """Create a standard success response."""
    response = {"success": True}
    
    if message:
        response["message"] = message
    
    if data is not None:
        response["data"] = data
    
    return jsonify(response), status_code

def error_response(message, status_code=400, errors=None):
    """Create a standard error response."""
    response = {
        "success": False,
        "error": message
    }
    
    if errors:
        response["errors"] = errors
    
    return jsonify(response), status_code

# Data utilities
def parse_datetime(dt_str):
    """Parse a datetime string in various formats."""
    if not dt_str:
        return None
        
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with milliseconds and Z
        "%Y-%m-%dT%H:%M:%SZ",     # ISO format with Z
        "%Y-%m-%dT%H:%M:%S.%f",   # ISO format with milliseconds
        "%Y-%m-%dT%H:%M:%S",      # ISO format
        "%Y-%m-%d %H:%M:%S.%f",   # SQL format with milliseconds
        "%Y-%m-%d %H:%M:%S",      # SQL format
        "%Y-%m-%d"                # Date only
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime string: {dt_str}")

def format_datetime(dt):
    """Format a datetime object as ISO 8601 string."""
    if isinstance(dt, str):
        dt = parse_datetime(dt)
    return dt.isoformat() + "Z"

def row_to_dict(row):
    """Convert a sqlite3.Row to a dictionary."""
    if not row:
        return None
    return dict(row)

def process_db_row(row, date_fields=None):
    """Process a database row to convert date strings and JSON fields."""
    if not row:
        return None
    
    # Convert sqlite3.Row to dict if needed
    data = row_to_dict(row) if hasattr(row, 'keys') else dict(row)
    
    # Default date fields to look for if not specified
    if date_fields is None:
        date_fields = [
            'created_at', 'updated_at', 'last_login', 'start_time', 
            'end_time', 'expires_at', 'read_at', 'sent_at', 'used_at',
            'deleted_at', 'last_used_at', 'scheduled_for', 'assigned_at',
            'exception_start', 'exception_end'
        ]
    
    # Convert date strings to ISO format
    for field in date_fields:
        if field in data and data[field]:
            try:
                if isinstance(data[field], str):
                    data[field] = format_datetime(parse_datetime(data[field]))
                elif isinstance(data[field], datetime):
                    data[field] = format_datetime(data[field])
            except Exception:
                pass  # Keep original value if conversion fails
    
    # Convert JSON string fields to objects
    json_fields = ['details', 'metadata', 'document_urls', 'attachment_urls', 
                 'delivery_channels', 'reference_data', 'context_data',
                 'previous_state', 'new_state', 'notified_users']
    
    for field in json_fields:
        if field in data and data[field] and isinstance(data[field], str):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                pass  # Keep as string
    
    return data

def process_db_rows(rows, date_fields=None):
    """Process multiple database rows."""
    if not rows:
        return []
    return [process_db_row(row, date_fields) for row in rows]


# Validation utilities
def validate_required_fields(data, required_fields):
    """Validate that required fields are present in the data."""
    missing = [field for field in required_fields if field not in data or data[field] is None]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None

def validate_email(email):
    """Basic validation for email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    return True, None

def validate_appointment_creation(data, db):
    """Validate data for appointment creation."""
    # Required fields check
    required_fields = ['student_parent_id', 'professional_id', 'slot_id', 'appointment_type_id']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return False, message
    
    # Check if slot exists and is available
    slot = db.conn.execute("SELECT * FROM APPOINTMENT_SLOTS WHERE id = ? AND is_available = 1", 
                        (data['slot_id'],)).fetchone()
    if not slot:
        return False, "Selected slot is not available"
    
    # Check if professional matches slot
    if slot['professional_id'] != data['professional_id']:
        return False, "Professional ID does not match the selected slot"
    
    # Check if appointment type exists
    appointment_type = db.conn.execute("SELECT * FROM APPOINTMENT_TYPES WHERE id = ?", 
                                    (data['appointment_type_id'],)).fetchone()
    if not appointment_type:
        return False, "Invalid appointment type"
    
    return True, None