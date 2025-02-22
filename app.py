from flask import Flask, request, jsonify, g
from flask_cors import CORS
import os
import json
from datetime import datetime, timedelta
import uuid

# Import database and utility modules
from sqlite_setup import create_database, generate_test_data, AppointmentSystemDB
from api_utilities import (
    get_db, close_db, init_app, 
    hash_password, verify_password, auth_required,
    success_response, error_response,
    parse_datetime, process_db_row, process_db_rows,
    validate_required_fields, validate_email, validate_appointment_creation
)

# Create and configure the app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Configure the database path
DB_FILE = os.environ.get('DB_FILE', 'appointment_system.db')

# Initialize app with database handling
init_app(app)

# Create the database if it doesn't exist
if not os.path.exists(DB_FILE):
    create_database(DB_FILE)
    generate_test_data(DB_FILE)

#--------------------------
# Authentication endpoints
#--------------------------

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.json
    
    # Validate required fields
    required_fields = ['email', 'password', 'name']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    # Validate email format
    valid, message = validate_email(data['email'])
    if not valid:
        return error_response(message)
    
    db = get_db()
    
    # Check if email is already registered
    existing_user = db.get_user_by_email(data['email'])
    if existing_user:
        return error_response("Email is already registered", 409)
    
    try:
        # Hash the password
        password_hash = hash_password(data['password'])
        
        # Create user
        details = data.get('details', {})
        # Convert details to JSON string if it's a dictionary
        if isinstance(details, dict):
            details = json.dumps(details)
            
        user_id = db.create_user(
            data['email'], 
            password_hash, 
            data['name'],
            data.get('contact_number'),
            details
        )
        
        # Assign requested role or default to student_parent
        role = data.get('role', 'student_parent')
        if role not in ['student_parent', 'professional']:
            role = 'student_parent'  # Only allow these two roles on registration
        
        db.assign_role_to_user(user_id, role)
        
        # Create verification record
        verification_code = str(uuid.uuid4())[:8]
        db.conn.execute('''
        INSERT INTO VERIFICATION (id, user_id, verification_type, verification_code, expires_at, is_used)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), user_id, 'email', verification_code,
            datetime.now() + timedelta(days=3), False
        ))
        
        # In a real system, send verification email here
        
        return success_response(
            {"user_id": user_id, "email": data['email']},
            "User registered successfully. Please verify your email.",
            201
        )
    
    except Exception as e:
        return error_response(f"Registration failed: {str(e)}", 500)

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login and get auth token."""
    data = request.json
    
    # Validate required fields
    required_fields = ['email', 'password']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    db = get_db()
    
    # Get user by email
    user = db.get_user_by_email(data['email'])
    if not user:
        return error_response("Invalid email or password", 401)
    
    # Verify password
    if not verify_password(user['password_hash'], data['password']):
        return error_response("Invalid email or password", 401)
    
    # Check if account is active
    if not user['is_active']:
        return error_response("Account is inactive", 403)
    
    # Generate auth token
    token = db.create_auth_token(user['id'], "session", 24)  # 24-hour token
    
    # Update last login timestamp
    db.conn.execute(
        "UPDATE USERS SET last_login = ? WHERE id = ?",
        (datetime.now(), user['id'])
    )
    db.conn.commit()
    
    # Get user roles
    roles = db.get_user_roles(user['id'])
    role_names = [role['name'] for role in roles]
    
    return success_response({
        "token": token,
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "roles": role_names,
            "is_verified": user['is_verified']
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
@auth_required()
def logout():
    """Revoke the current auth token."""
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(' ')[1]
    
    db = get_db()
    db.revoke_auth_token(token)
    
    return success_response(message="Logged out successfully")

@app.route('/api/auth/verify-email', methods=['POST'])
def verify_email():
    """Verify user email with verification code."""
    data = request.json
    
    # Validate required fields
    required_fields = ['email', 'code']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    db = get_db()
    
    # Get user by email
    user = db.get_user_by_email(data['email'])
    if not user:
        return error_response("Invalid email", 404)
    
    # Check verification record
    verification = db.conn.execute('''
    SELECT * FROM VERIFICATION 
    WHERE user_id = ? AND verification_type = 'email' AND is_used = 0 AND expires_at > ?
    ''', (user['id'], datetime.now())).fetchone()
    
    if not verification or verification['verification_code'] != data['code']:
        return error_response("Invalid or expired verification code", 400)
    
    # Mark verification as used
    db.conn.execute('''
    UPDATE VERIFICATION
    SET is_used = 1, used_at = ?
    WHERE id = ?
    ''', (datetime.now(), verification['id']))
    
    # Update user verified status
    db.conn.execute('''
    UPDATE USERS
    SET is_verified = 1
    WHERE id = ?
    ''', (user['id'],))
    
    db.conn.commit()
    
    return success_response(message="Email verified successfully")

#------------------------
# User endpoints
#------------------------

@app.route('/api/users/me', methods=['GET'])
@auth_required()
def get_current_user():
    """Get current user profile."""
    user = g.user
    
    # Remove sensitive fields
    if 'password_hash' in user:
        del user['password_hash']
    
    return success_response(user)

@app.route('/api/users/me', methods=['PATCH'])
@auth_required()
def update_current_user():
    """Update current user profile."""
    data = request.json
    user_id = g.user['id']
    db = get_db()
    
    # Fields that can be updated
    allowed_fields = ['name', 'contact_number', 'details']
    update_fields = {}
    
    # Create the SQL SET clause parts
    set_clauses = []
    params = []
    
    for field in allowed_fields:
        if field in data:
            if field == 'details' and data[field] is not None:
                # Ensure details is stored as JSON string
                update_fields[field] = json.dumps(data[field])
            else:
                update_fields[field] = data[field]
            
            set_clauses.append(f"{field} = ?")
            params.append(update_fields[field])
    
    if not set_clauses:
        return error_response("No valid fields to update", 400)
    
    # Add updated_at timestamp
    set_clauses.append("updated_at = ?")
    params.append(datetime.now())
    
    # Add user ID parameter
    params.append(user_id)
    
    # Execute update
    query = f"UPDATE USERS SET {', '.join(set_clauses)} WHERE id = ?"
    db.conn.execute(query, params)
    db.conn.commit()
    
    # Get updated user
    updated_user = db.get_user_by_id(user_id)
    user_dict = process_db_row(updated_user)
    
    # Remove sensitive fields
    if 'password_hash' in user_dict:
        del user_dict['password_hash']
    
    return success_response(user_dict, "Profile updated successfully")

#--------------------------
# Appointment Types endpoints
#--------------------------

@app.route('/api/appointment-types', methods=['GET'])
@auth_required()
def get_appointment_types():
    """Get all active appointment types."""
    db = get_db()
    
    types = db.conn.execute("SELECT * FROM APPOINTMENT_TYPES WHERE is_active = 1 ORDER BY name").fetchall()
    
    return success_response(process_db_rows(types))

#--------------------------
# Availability endpoints
#--------------------------

@app.route('/api/professionals', methods=['GET'])
@auth_required()
def get_professionals():
    """Get all professionals."""
    db = get_db()
    
    query = '''
    SELECT u.id, u.name, u.email, u.contact_number, u.details, u.is_verified, u.is_active
    FROM USERS u
    JOIN USER_ROLES ur ON u.id = ur.user_id
    JOIN ROLES r ON ur.role_id = r.id
    WHERE r.name = 'professional' AND u.is_active = 1
    ORDER BY u.name
    '''
    
    professionals = db.conn.execute(query).fetchall()
    
    # Process the result
    result = []
    for prof in professionals:
        prof_dict = process_db_row(prof)
        # Get credentials
        credentials = db.conn.execute('''
        SELECT * FROM PROFESSIONAL_CREDENTIALS
        WHERE user_id = ? AND verification_status = 'verified'
        ''', (prof['id'],)).fetchall()
        
        prof_dict['credentials'] = process_db_rows(credentials)
        result.append(prof_dict)
    
    return success_response(result)

@app.route('/api/professionals/<professional_id>/availability', methods=['GET'])
@auth_required()
def get_professional_availability(professional_id):
    """Get availability for a specific professional."""
    db = get_db()
    
    # Parse date range parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = parse_datetime(start_date)
    else:
        start_date = datetime.now()
    
    if end_date:
        end_date = parse_datetime(end_date)
    else:
        end_date = start_date + timedelta(days=30)  # Default to 30 days
    
    # Get availability
    availability = db.get_professional_availability(professional_id, start_date, end_date)
    
    # Get slots
    slots = db.get_available_slots(professional_id, start_date, end_date)
    
    return success_response({
        "availability": process_db_rows(availability),
        "slots": process_db_rows(slots)
    })

@app.route('/api/professionals/<professional_id>/availability', methods=['POST'])
@auth_required(['professional', 'admin'])
def create_professional_availability(professional_id):
    """Create new availability for a professional."""
    # Check if user is the professional or an admin
    if g.user['id'] != professional_id and 'admin' not in g.user['roles']:
        return error_response("Not authorized to modify this professional's availability", 403)
    
    data = request.json
    
    # Validate required fields
    required_fields = ['start_time', 'end_time', 'duration_minutes']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    try:
        db = get_db()
        
        # Parse datetime fields
        start_time = parse_datetime(data['start_time'])
        end_time = parse_datetime(data['end_time'])
        
        # Create availability
        availability_id = db.create_availability(
            professional_id,
            start_time,
            end_time,
            data.get('is_recurring', False),
            data.get('recurrence_pattern'),
            data['duration_minutes'],
            data.get('availability_type', 'regular')
        )
        
        # Generate slots if specified
        if data.get('generate_slots', True):
            slot_duration = data.get('slot_duration_minutes', 30)
            slots = db.generate_slots_from_availability(availability_id, slot_duration)
            
            return success_response({
                "availability_id": availability_id,
                "slots_created": len(slots)
            }, "Availability created with slots", 201)
        
        return success_response({
            "availability_id": availability_id
        }, "Availability created", 201)
        
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"Failed to create availability: {str(e)}", 500)

#--------------------------
# Appointment endpoints
#--------------------------

@app.route('/api/appointments', methods=['GET'])
@auth_required()
def get_user_appointments():
    """Get appointments for the current user."""
    user_id = g.user['id']
    user_roles = g.user['roles']
    
    # Determine role for filtering
    role = None
    if 'professional' in user_roles and 'student_parent' not in user_roles:
        role = 'professional'
    elif 'student_parent' in user_roles and 'professional' not in user_roles:
        role = 'student_parent'
    
    # Parse query parameters
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = parse_datetime(start_date)
    
    if end_date:
        end_date = parse_datetime(end_date)
    
    db = get_db()
    appointments = db.get_user_appointments(user_id, role, status, start_date, end_date)
    
    return success_response(process_db_rows(appointments))

@app.route('/api/appointments/<appointment_id>', methods=['GET'])
@auth_required()
def get_appointment_details(appointment_id):
    """Get detailed information about a specific appointment."""
    user_id = g.user['id']
    user_roles = g.user['roles']
    
    db = get_db()
    appointment = db.get_appointment(appointment_id)
    
    if not appointment:
        return error_response("Appointment not found", 404)
    
    # Check if user is authorized to view this appointment
    is_authorized = (
        appointment['student_parent_id'] == user_id or
        appointment['professional_id'] == user_id or
        'admin' in user_roles
    )
    
    if not is_authorized:
        return error_response("Not authorized to view this appointment", 403)
    
    # Get appointment history
    history = db.conn.execute('''
    SELECT ah.*, u.name as changed_by_name
    FROM APPOINTMENT_HISTORY ah
    LEFT JOIN USERS u ON ah.changed_by_user_id = u.id
    WHERE ah.appointment_id = ?
    ORDER BY ah.created_at DESC
    ''', (appointment_id,)).fetchall()
    
    # Get communications if authorized
    communications = []
    if is_authorized:
        communications = db.get_appointment_communications(appointment_id)
    
    # Process the result
    result = process_db_row(appointment)
    result['history'] = process_db_rows(history)
    result['communications'] = process_db_rows(communications)
    
    return success_response(result)

@app.route('/api/appointments', methods=['POST'])
@auth_required()
def create_appointment():
    """Create a new appointment."""
    data = request.json
    user_id = g.user['id']
    user_roles = g.user['roles']
    
    # If student_parent_id is not provided, use current user ID for student role
    if 'student_parent_id' not in data and 'student_parent' in user_roles:
        data['student_parent_id'] = user_id
    
    # If professional_id is not provided, use current user ID for professional role
    if 'professional_id' not in data and 'professional' in user_roles:
        data['professional_id'] = user_id
    
    db = get_db()
    
    # Validate appointment data
    valid, message = validate_appointment_creation(data, db)
    if not valid:
        return error_response(message, 400)
    
    try:
        # Create the appointment
        appointment_id = db.create_appointment(
            data['student_parent_id'],
            data['professional_id'],
            data['slot_id'],
            data['appointment_type_id'],
            None,  # start_time from slot
            None,  # end_time from slot
            data.get('status', 'scheduled'),
            data.get('metadata')
        )
        
        # Get the created appointment
        appointment = db.get_appointment(appointment_id)
        
        # Create notifications for both parties
        # For professional
        db.create_notification(
            data['professional_id'],
            'appointment_created',
            'New Appointment Scheduled',
            f"A new appointment has been scheduled for {appointment['start_time']}",
            {'appointment_id': appointment_id},
            None,
            {'student_name': appointment['student_name']},
            'email'
        )
        
        # For student/parent
        db.create_notification(
            data['student_parent_id'],
            'appointment_confirmed',
            'Appointment Confirmed',
            f"Your appointment with {appointment['professional_name']} has been scheduled for {appointment['start_time']}",
            {'appointment_id': appointment_id},
            None,
            {'professional_name': appointment['professional_name']},
            'email'
        )
        
        return success_response(
            process_db_row(appointment),
            "Appointment created successfully",
            201
        )
        
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"Failed to create appointment: {str(e)}", 500)

@app.route('/api/appointments/<appointment_id>/status', methods=['PUT'])
@auth_required()
def update_appointment_status(appointment_id):
    """Update the status of an appointment."""
    data = request.json
    user_id = g.user['id']
    user_roles = g.user['roles']
    
    # Validate required fields
    if 'status' not in data:
        return error_response("Status is required", 400)
    
    new_status = data['status']
    if new_status not in ['scheduled', 'confirmed', 'pending', 'cancelled', 'completed']:
        return error_response("Invalid status value", 400)
    
    db = get_db()
    
    # Get the appointment
    appointment = db.get_appointment(appointment_id)
    if not appointment:
        return error_response("Appointment not found", 404)
    
    # Check if user is authorized to update this appointment
    is_authorized = (
        appointment['student_parent_id'] == user_id or
        appointment['professional_id'] == user_id or
        'admin' in user_roles
    )
    
    if not is_authorized:
        return error_response("Not authorized to update this appointment", 403)
    
    # Check if status change is valid
    current_status = appointment['status']
    
    # Prevent changing completed appointments except by admin
    if current_status == 'completed' and new_status != 'completed' and 'admin' not in user_roles:
        return error_response("Cannot change status of completed appointments", 400)
    
    # Prevent changing cancelled appointments except back to scheduled and only by admin
    if current_status == 'cancelled' and new_status != 'cancelled' and new_status != 'scheduled' and 'admin' not in user_roles:
        return error_response("Cannot change status of cancelled appointments", 400)
    
    try:
        # Update the appointment status
        db.update_appointment_status(
            appointment_id,
            new_status,
            user_id,
            data.get('notes')
        )
        
        # Get the updated appointment
        updated_appointment = db.get_appointment(appointment_id)
        
        # Create notifications based on new status
        if new_status == 'cancelled':
            # Notify the other party about cancellation
            recipient_id = appointment['professional_id'] if user_id == appointment['student_parent_id'] else appointment['student_parent_id']
            canceller_name = g.user['name']
            
            db.create_notification(
                recipient_id,
                'appointment_cancelled',
                'Appointment Cancelled',
                f"Your appointment for {appointment['start_time']} has been cancelled by {canceller_name}",
                {'appointment_id': appointment_id},
                None,
                {'canceller_name': canceller_name},
                'email'
            )
        elif new_status == 'confirmed':
            # Notify both parties about confirmation
            db.create_notification(
                appointment['student_parent_id'],
                'appointment_confirmed',
                'Appointment Confirmed',
                f"Your appointment with {appointment['professional_name']} for {appointment['start_time']} has been confirmed",
                {'appointment_id': appointment_id},
                None,
                {'professional_name': appointment['professional_name']},
                'email'
            )
            
            db.create_notification(
                appointment['professional_id'],
                'appointment_confirmed',
                'Appointment Confirmed',
                f"Your appointment with {appointment['student_name']} for {appointment['start_time']} has been confirmed",
                {'appointment_id': appointment_id},
                None,
                {'student_name': appointment['student_name']},
                'email'
            )
        elif new_status == 'completed':
            # Create rating request notification for student/parent
            db.create_notification(
                appointment['student_parent_id'],
                'appointment_completed',
                'Appointment Completed - Please Rate Your Experience',
                f"Your appointment with {appointment['professional_name']} has been completed. Please take a moment to rate your experience.",
                {'appointment_id': appointment_id},
                None,
                {'professional_name': appointment['professional_name']},
                'email'
            )
        
        return success_response(
            process_db_row(updated_appointment),
            f"Appointment status updated to {new_status}"
        )
        
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"Failed to update appointment status: {str(e)}", 500)

#--------------------------
# Communication endpoints
#--------------------------

@app.route('/api/appointments/<appointment_id>/communications', methods=['POST'])
@auth_required()
def create_communication(appointment_id):
    """Add a communication log to an appointment."""
    data = request.json
    user_id = g.user['id']
    
    # Validate required fields
    required_fields = ['recipient_id', 'message_type', 'content']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    db = get_db()
    
    # Get the appointment
    appointment = db.get_appointment(appointment_id)
    if not appointment:
        return error_response("Appointment not found", 404)
    
    # Check if user is related to this appointment
    is_related = (
        appointment['student_parent_id'] == user_id or
        appointment['professional_id'] == user_id or
        'admin' in g.user['roles']
    )
    
    if not is_related:
        return error_response("Not authorized to add communication to this appointment", 403)
    
    # Check if recipient is related to this appointment
    recipient_id = data['recipient_id']
    is_recipient_related = (
        appointment['student_parent_id'] == recipient_id or
        appointment['professional_id'] == recipient_id or
        db.conn.execute('''
        SELECT 1 FROM USER_ROLES ur
        JOIN ROLES r ON ur.role_id = r.id
        WHERE ur.user_id = ? AND r.name = 'admin'
        ''', (recipient_id,)).fetchone() is not None
    )
    
    if not is_recipient_related:
        return error_response("Recipient is not related to this appointment", 400)
    
    try:
        # Create communication log
        communication_id = db.create_communication_log(
            appointment_id,
            user_id,
            recipient_id,
            data['message_type'],
            data['content'],
            data.get('attachment_urls'),
            data.get('visibility_level', 'public')
        )
        
        # Create notification for recipient
        sender_name = g.user['name']
        db.create_notification(
            recipient_id,
            'new_message',
            f"New message from {sender_name}",
            f"{sender_name} sent you a message regarding your appointment.",
            {
                'appointment_id': appointment_id,
                'communication_id': communication_id
            },
            None,
            {
                'sender_name': sender_name,
                'appointment_date': appointment['start_time']
            },
            'email'
        )
        
        # Get the created communication
        communication = db.conn.execute('''
        SELECT c.*, 
               s.name as sender_name,
               r.name as recipient_name
        FROM COMMUNICATION_LOGS c
        JOIN USERS s ON c.sender_user_id = s.id
        JOIN USERS r ON c.recipient_user_id = r.id
        WHERE c.id = ?
        ''', (communication_id,)).fetchone()
        
        return success_response(
            process_db_row(communication),
            "Communication sent successfully",
            201
        )
        
    except Exception as e:
        return error_response(f"Failed to send communication: {str(e)}", 500)

#--------------------------
# Notification endpoints
#--------------------------

@app.route('/api/notifications', methods=['GET'])
@auth_required()
def get_notifications():
    """Get notifications for the current user."""
    user_id = g.user['id']
    
    # Parse query parameters
    is_read = request.args.get('is_read')
    if is_read is not None:
        is_read = is_read.lower() == 'true'
    
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    db = get_db()
    notifications = db.get_user_notifications(user_id, is_read, limit, offset)
    
    return success_response(process_db_rows(notifications))

@app.route('/api/notifications/<notification_id>/read', methods=['PUT'])
@auth_required()
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    user_id = g.user['id']
    
    db = get_db()
    
    # Check if notification belongs to user
    notification = db.conn.execute(
        "SELECT * FROM NOTIFICATIONS WHERE id = ? AND user_id = ?",
        (notification_id, user_id)
    ).fetchone()
    
    if not notification:
        return error_response("Notification not found", 404)
    
    # Mark as read
    success = db.mark_notification_as_read(notification_id)
    
    if success:
        return success_response(message="Notification marked as read")
    else:
        return error_response("Failed to mark notification as read", 500)

#--------------------------
# Rating endpoints
#--------------------------

@app.route('/api/appointments/<appointment_id>/rating', methods=['POST'])
@auth_required()
def rate_appointment(appointment_id):
    """Add a rating for an appointment."""
    data = request.json
    user_id = g.user['id']
    
    # Validate required fields
    required_fields = ['rating']
    valid, message = validate_required_fields(data, required_fields)
    if not valid:
        return error_response(message)
    
    # Validate rating value
    rating = data['rating']
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return error_response("Rating must be an integer between 1 and 5", 400)
    
    db = get_db()
    
    # Get the appointment
    appointment = db.get_appointment(appointment_id)
    if not appointment:
        return error_response("Appointment not found", 404)
    
    # Check if user is related to this appointment
    is_related = (
        appointment['student_parent_id'] == user_id or
        appointment['professional_id'] == user_id
    )
    
    if not is_related:
        return error_response("Not authorized to rate this appointment", 403)
    
    # Check if appointment is completed
    if appointment['status'] != 'completed':
        return error_response("Only completed appointments can be rated", 400)
    
    try:
        # Check if user already rated this appointment
        existing_rating = db.conn.execute('''
        SELECT * FROM APPOINTMENT_RATINGS
        WHERE appointment_id = ? AND rated_by_user_id = ?
        ''', (appointment_id, user_id)).fetchone()
        
        if existing_rating:
            return error_response("You have already rated this appointment", 409)
        
        # Create rating
        rating_id = str(uuid.uuid4())
        now = datetime.now()
        
        db.conn.execute('''
        INSERT INTO APPOINTMENT_RATINGS 
        (id, appointment_id, rated_by_user_id, rating, feedback, is_anonymous, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rating_id, appointment_id, user_id, rating, 
            data.get('feedback'), data.get('is_anonymous', False),
            now, now
        ))
        
        db.conn.commit()
        
        # Get the created rating
        created_rating = db.conn.execute('''
        SELECT * FROM APPOINTMENT_RATINGS WHERE id = ?
        ''', (rating_id,)).fetchone()
        
        # Notify the other party
        other_party_id = appointment['professional_id'] if user_id == appointment['student_parent_id'] else appointment['student_parent_id']
        other_party_name = appointment['professional_name'] if user_id == appointment['student_parent_id'] else appointment['student_name']
        
        if not data.get('is_anonymous', False):
            db.create_notification(
                other_party_id,
                'new_rating',
                'New Appointment Rating',
                f"{g.user['name']} has rated your appointment with a score of {rating}/5.",
                {'appointment_id': appointment_id, 'rating_id': rating_id},
                None,
                {'rater_name': g.user['name'], 'rating': rating},
                'email'
            )
        else:
            db.create_notification(
                other_party_id,
                'new_rating',
                'New Anonymous Appointment Rating',
                f"Your appointment has received an anonymous rating of {rating}/5.",
                {'appointment_id': appointment_id, 'rating_id': rating_id},
                None,
                {'rating': rating},
                'email'
            )
        
        return success_response(
            process_db_row(created_rating),
            "Rating submitted successfully",
            201
        )
        
    except Exception as e:
        return error_response(f"Failed to submit rating: {str(e)}", 500)

#--------------------------
# Main application
#--------------------------

if __name__ == '__main__':
    # Set up the port (default to 8080)
    port = int(os.environ.get('PORT', 8080))
    
    # Set debug mode based on environment
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # Ensure database exists before starting
    if not os.path.exists(DB_FILE):
        print(f"Creating database at {DB_FILE}...")
        create_database(DB_FILE)
        generate_test_data(DB_FILE)
    
    print(f"Starting Appointment System API on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=debug)