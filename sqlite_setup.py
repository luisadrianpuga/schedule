import sqlite3
import uuid
import json
import os
from datetime import datetime, timedelta


def create_database(db_file="appointment_system.db"):
    """Create a new SQLite database and set up all tables for the appointment system."""
    # Remove existing database file if it exists
    if os.path.exists(db_file):
        os.remove(db_file)
    
    # Connect to database (this will create it if it doesn't exist)
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Create USERS table
    cursor.execute('''
    CREATE TABLE USERS (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        contact_number TEXT,
        is_verified BOOLEAN DEFAULT FALSE,
        details TEXT,  -- JSON data stored as text
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    )
    ''')
    
    # Create ROLES table
    cursor.execute('''
    CREATE TABLE ROLES (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create USER_ROLES table (junction table)
    cursor.execute('''
    CREATE TABLE USER_ROLES (
        user_id TEXT NOT NULL,
        role_id TEXT NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by TEXT,
        PRIMARY KEY (user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES ROLES(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_by) REFERENCES USERS(id) ON DELETE SET NULL
    )
    ''')
    
    # Create PROFESSIONAL_CREDENTIALS table
    cursor.execute('''
    CREATE TABLE PROFESSIONAL_CREDENTIALS (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        license_number TEXT UNIQUE NOT NULL,
        credential_type TEXT NOT NULL,
        credential_category TEXT,
        is_primary BOOLEAN DEFAULT FALSE,
        expiration_date DATE,
        issuing_authority TEXT,
        verification_status TEXT,
        document_urls TEXT,  -- JSON data stored as text
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        verified_by TEXT,
        FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (verified_by) REFERENCES USERS(id) ON DELETE SET NULL
    )
    ''')
    
    # Create APPOINTMENT_TYPES table
    cursor.execute('''
    CREATE TABLE APPOINTMENT_TYPES (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        duration_minutes INTEGER NOT NULL,
        is_virtual BOOLEAN DEFAULT FALSE,
        color_code TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create AVAILABILITY table
    cursor.execute('''
    CREATE TABLE AVAILABILITY (
        id TEXT PRIMARY KEY,
        professional_id TEXT NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        is_recurring BOOLEAN DEFAULT FALSE,
        recurrence_pattern TEXT,
        duration_minutes INTEGER NOT NULL,
        availability_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (professional_id) REFERENCES USERS(id) ON DELETE CASCADE,
        CHECK (recurrence_pattern IN ('daily', 'weekly', 'monthly', 'custom')),
        CHECK (end_time > start_time)
    )
    ''')
    
    # Create AVAILABILITY_EXCEPTIONS table
    cursor.execute('''
    CREATE TABLE AVAILABILITY_EXCEPTIONS (
        id TEXT PRIMARY KEY,
        professional_id TEXT NOT NULL,
        availability_id TEXT NOT NULL,
        exception_start TIMESTAMP NOT NULL,
        exception_end TIMESTAMP NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (professional_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (availability_id) REFERENCES AVAILABILITY(id) ON DELETE CASCADE,
        CHECK (exception_end > exception_start)
    )
    ''')
    
    # Create APPOINTMENT_SLOTS table
    cursor.execute('''
    CREATE TABLE APPOINTMENT_SLOTS (
        id TEXT PRIMARY KEY,
        availability_id TEXT NOT NULL,
        professional_id TEXT NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        is_available BOOLEAN DEFAULT TRUE,
        max_bookings INTEGER DEFAULT 1,
        current_bookings INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (availability_id) REFERENCES AVAILABILITY(id) ON DELETE CASCADE,
        FOREIGN KEY (professional_id) REFERENCES USERS(id) ON DELETE CASCADE,
        CHECK (current_bookings <= max_bookings),
        CHECK (current_bookings >= 0),
        CHECK (end_time > start_time)
    )
    ''')
    
    # Create APPOINTMENTS table
    cursor.execute('''
    CREATE TABLE APPOINTMENTS (
        id TEXT PRIMARY KEY,
        student_parent_id TEXT NOT NULL,
        professional_id TEXT NOT NULL,
        slot_id TEXT NOT NULL,
        appointment_type_id TEXT NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        status TEXT NOT NULL,
        metadata TEXT,  -- JSON data stored as text
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_parent_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (professional_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (slot_id) REFERENCES APPOINTMENT_SLOTS(id) ON DELETE CASCADE,
        FOREIGN KEY (appointment_type_id) REFERENCES APPOINTMENT_TYPES(id) ON DELETE CASCADE,
        CHECK (status IN ('scheduled', 'confirmed', 'pending', 'cancelled', 'completed')),
        CHECK (end_time > start_time)
    )
    ''')
    
    # Create APPOINTMENT_HISTORY table
    cursor.execute('''
    CREATE TABLE APPOINTMENT_HISTORY (
        id TEXT PRIMARY KEY,
        appointment_id TEXT NOT NULL,
        changed_by_user_id TEXT,
        previous_state TEXT,  -- JSON data stored as text
        new_state TEXT,  -- JSON data stored as text
        change_type TEXT NOT NULL,
        change_source TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES APPOINTMENTS(id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by_user_id) REFERENCES USERS(id) ON DELETE SET NULL,
        CHECK (change_type IN ('status_change', 'reschedule', 'cancellation', 'metadata_update')),
        CHECK (change_source IN ('user', 'admin', 'system'))
    )
    ''')
    
    # Create CANCELLATIONS table
    cursor.execute('''
    CREATE TABLE CANCELLATIONS (
        id TEXT PRIMARY KEY,
        appointment_id TEXT UNIQUE NOT NULL,
        cancelled_by_user_id TEXT,
        reason TEXT,
        notified_users TEXT,  -- JSON array stored as text
        is_notified BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES APPOINTMENTS(id) ON DELETE CASCADE,
        FOREIGN KEY (cancelled_by_user_id) REFERENCES USERS(id) ON DELETE SET NULL
    )
    ''')
    
    # Create NOTIFICATION_TEMPLATES table
    cursor.execute('''
    CREATE TABLE NOTIFICATION_TEMPLATES (
        id TEXT PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        title_template TEXT NOT NULL,
        message_template TEXT NOT NULL,
        delivery_channels TEXT,  -- JSON array stored as text
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create NOTIFICATIONS table
    cursor.execute('''
    CREATE TABLE NOTIFICATIONS (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        template_id TEXT,
        reference_data TEXT,  -- JSON data stored as text
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        context_data TEXT,  -- JSON data stored as text
        delivery_channel TEXT,
        scheduled_for TIMESTAMP,
        is_read BOOLEAN DEFAULT FALSE,
        is_sent BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        read_at TIMESTAMP,
        sent_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (template_id) REFERENCES NOTIFICATION_TEMPLATES(id) ON DELETE SET NULL
    )
    ''')
    
    # Create APPOINTMENT_RATINGS table
    cursor.execute('''
    CREATE TABLE APPOINTMENT_RATINGS (
        id TEXT PRIMARY KEY,
        appointment_id TEXT NOT NULL,
        rated_by_user_id TEXT NOT NULL,
        rating INTEGER NOT NULL,
        feedback TEXT,
        is_anonymous BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES APPOINTMENTS(id) ON DELETE CASCADE,
        FOREIGN KEY (rated_by_user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        UNIQUE (appointment_id, rated_by_user_id),
        CHECK (rating BETWEEN 1 AND 5)
    )
    ''')
    
    # Create COMMUNICATION_LOGS table
    cursor.execute('''
    CREATE TABLE COMMUNICATION_LOGS (
        id TEXT PRIMARY KEY,
        appointment_id TEXT NOT NULL,
        sender_user_id TEXT NOT NULL,
        recipient_user_id TEXT NOT NULL,
        message_type TEXT NOT NULL,
        content TEXT,
        attachment_urls TEXT,  -- JSON array stored as text
        is_read BOOLEAN DEFAULT FALSE,
        read_at TIMESTAMP,
        is_deleted BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP,
        deleted_by TEXT,
        visibility_level TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES APPOINTMENTS(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_user_id) REFERENCES USERS(id) ON DELETE CASCADE,
        FOREIGN KEY (deleted_by) REFERENCES USERS(id) ON DELETE SET NULL,
        CHECK (visibility_level IN ('public', 'private', 'admin_only'))
    )
    ''')
    
    # Create AUTH_TOKENS table
    cursor.execute('''
    CREATE TABLE AUTH_TOKENS (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        token_type TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE
    )
    ''')
    
    # Create VERIFICATION table
    cursor.execute('''
    CREATE TABLE VERIFICATION (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        verification_type TEXT NOT NULL,
        verification_code TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        is_used BOOLEAN DEFAULT FALSE,
        used_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE
    )
    ''')
    
    # Create necessary indexes to improve performance
    
    # Indexes for APPOINTMENTS
    cursor.execute('CREATE INDEX idx_appointments_by_professional_and_date ON APPOINTMENTS(professional_id, start_time)')
    cursor.execute('CREATE INDEX idx_appointments_by_student_parent ON APPOINTMENTS(student_parent_id, start_time)')
    cursor.execute('CREATE INDEX idx_appointments_by_start_time ON APPOINTMENTS(start_time)')
    cursor.execute('CREATE INDEX idx_appointments_by_slot_id ON APPOINTMENTS(slot_id)')
    
    # Indexes for APPOINTMENT_SLOTS
    cursor.execute('CREATE INDEX idx_appointment_slots_by_professional ON APPOINTMENT_SLOTS(professional_id, start_time)')
    cursor.execute('CREATE INDEX idx_appointment_slots_by_availability ON APPOINTMENT_SLOTS(availability_id)')
    
    # Index for AVAILABILITY
    cursor.execute('CREATE INDEX idx_availability_by_professional ON AVAILABILITY(professional_id)')
    
    # Index for NOTIFICATIONS
    cursor.execute('CREATE INDEX idx_notifications_by_user ON NOTIFICATIONS(user_id, is_read)')
    
    # Index for AUTH_TOKENS
    cursor.execute('CREATE INDEX idx_auth_tokens_by_user ON AUTH_TOKENS(user_id)')
    
    # Index for VERIFICATION
    cursor.execute('CREATE UNIQUE INDEX idx_unique_active_verification ON VERIFICATION(user_id, verification_type) WHERE is_used = 0')
    
    # Commit changes and close connection
    conn.commit()
    
    # Insert some initial data
    insert_initial_data(conn)
    
    conn.close()
    
    print(f"Database '{db_file}' created successfully with all tables and initial data.")
    return db_file


def insert_initial_data(conn):
    """Insert initial data into the database."""
    cursor = conn.cursor()
    
    # Insert roles
    roles = [
        (str(uuid.uuid4()), "admin", "System administrator with full access", datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "professional", "Service provider who can set availability and accept appointments", datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "student_parent", "User who can book appointments", datetime.now(), datetime.now())
    ]
    cursor.executemany("INSERT INTO ROLES (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", roles)
    
    # Insert a default admin user
    admin_id = str(uuid.uuid4())
    admin_user = (
        admin_id,
        "admin@example.com",
        "pbkdf2:sha256:150000$8AvVeQXB$d32387ccaa5ccfa026eae81b947d11e9ff2191c1900ad250a30b9fafd5e82c7b",  # hashed 'adminpassword'
        "System Administrator",
        "+1234567890",
        True,
        json.dumps({"bio": "System administrator"}),
        datetime.now(),
        datetime.now(),
        datetime.now(),
        True
    )
    cursor.execute('''
    INSERT INTO USERS (id, email, password_hash, name, contact_number, is_verified, details, 
                     created_at, updated_at, last_login, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', admin_user)
    
    # Insert appointment types
    appointment_types = [
        (str(uuid.uuid4()), "Initial Consultation", "First-time meeting to discuss needs", 60, True, "#4285F4", True, datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "Follow-up Session", "Regular follow-up appointment", 45, True, "#34A853", True, datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "Emergency Meeting", "Urgent appointment for pressing matters", 30, True, "#EA4335", True, datetime.now(), datetime.now())
    ]
    cursor.executemany('''
    INSERT INTO APPOINTMENT_TYPES (id, name, description, duration_minutes, is_virtual, color_code, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', appointment_types)
    
    # Insert notification templates
    templates = [
        (str(uuid.uuid4()), "appointment_reminder", "Reminder: {{appointment_type}} appointment", 
         "Dear {{user_name}}, this is a reminder about your {{appointment_type}} appointment scheduled on {{appointment_date}} at {{appointment_time}}.",
         json.dumps(["email", "sms"]), datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "appointment_confirmation", "Appointment Confirmed: {{appointment_type}}", 
         "Your {{appointment_type}} appointment has been confirmed for {{appointment_date}} at {{appointment_time}}. Thank you!",
         json.dumps(["email", "push"]), datetime.now(), datetime.now()),
        (str(uuid.uuid4()), "appointment_cancellation", "Appointment Cancelled: {{appointment_type}}", 
         "Your {{appointment_type}} appointment scheduled for {{appointment_date}} at {{appointment_time}} has been cancelled.",
         json.dumps(["email", "sms", "push"]), datetime.now(), datetime.now())
    ]
    cursor.executemany('''
    INSERT INTO NOTIFICATION_TEMPLATES (id, code, title_template, message_template, delivery_channels, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', templates)
    
    # Get admin role ID
    cursor.execute("SELECT id FROM ROLES WHERE name = 'admin'")
    admin_role_id = cursor.fetchone()[0]
    
    # Assign admin role to admin user
    cursor.execute('''
    INSERT INTO USER_ROLES (user_id, role_id, assigned_at, assigned_by)
    VALUES (?, ?, ?, ?)
    ''', (admin_id, admin_role_id, datetime.now(), admin_id))
    
    # Commit changes
    conn.commit()


def generate_test_data(db_file="appointment_system.db", num_users=10, num_appointments=20):
    """Generate test data for the appointment system."""
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    # Get role IDs
    cursor.execute("SELECT id FROM ROLES WHERE name = 'professional'")
    professional_role_id = cursor.fetchone()[0]
    
    cursor.execute("SELECT id FROM ROLES WHERE name = 'student_parent'")
    student_parent_role_id = cursor.fetchone()[0]
    
    # Generate test professionals
    professionals = []
    for i in range(num_users // 2):
        user_id = str(uuid.uuid4())
        professionals.append(user_id)
        
        user = (
            user_id,
            f"professional{i}@example.com",
            f"pbkdf2:sha256:150000$8AvVeQXB$d32387ccaa5ccfa026eae81b947d11e9ff2191c1900ad250a30b9fafd5e82c7b",  # hashed 'password'
            f"Professional User {i}",
            f"+1{i}23456789",
            True,
            json.dumps({"bio": f"Professional bio for user {i}", "specialization": "General"}),
            datetime.now(),
            datetime.now(),
            datetime.now(),
            True
        )
        cursor.execute('''
        INSERT INTO USERS (id, email, password_hash, name, contact_number, is_verified, details, 
                         created_at, updated_at, last_login, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', user)
        
        # Assign professional role
        cursor.execute('''
        INSERT INTO USER_ROLES (user_id, role_id, assigned_at, assigned_by)
        VALUES (?, ?, ?, ?)
        ''', (user_id, professional_role_id, datetime.now(), None))
        
        # Add professional credentials
        cursor.execute('''
        INSERT INTO PROFESSIONAL_CREDENTIALS (id, user_id, license_number, credential_type,
                                            credential_category, is_primary, expiration_date,
                                            issuing_authority, verification_status, document_urls,
                                            created_at, updated_at, verified_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), user_id, f"LIC-{i}0000", "Professional License",
            "Category A", True, (datetime.now() + timedelta(days=365)).date(),
            "State Board", "verified", json.dumps(["http://example.com/doc1.pdf"]),
            datetime.now(), datetime.now(), None
        ))
        
        # Add availability for each professional
        today = datetime.now()
        for day_offset in range(14):  # Two weeks of availability
            day = today + timedelta(days=day_offset)
            
            # Morning availability
            avail_id = str(uuid.uuid4())
            start_time = datetime(day.year, day.month, day.day, 9, 0)
            end_time = datetime(day.year, day.month, day.day, 12, 0)
            
            cursor.execute('''
            INSERT INTO AVAILABILITY (id, professional_id, start_time, end_time,
                                     is_recurring, recurrence_pattern, duration_minutes,
                                     availability_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                avail_id, user_id, start_time, end_time,
                False, None, 180, "regular", datetime.now(), datetime.now()
            ))
            
            # Create slots for the morning availability
            for hour in range(9, 12):
                for minute in [0, 30]:
                    slot_start = datetime(day.year, day.month, day.day, hour, minute)
                    slot_end = slot_start + timedelta(minutes=30)
                    
                    cursor.execute('''
                    INSERT INTO APPOINTMENT_SLOTS (id, availability_id, professional_id,
                                                 start_time, end_time, is_available,
                                                 max_bookings, current_bookings, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(uuid.uuid4()), avail_id, user_id,
                        slot_start, slot_end, True, 1, 0, datetime.now()
                    ))
            
            # Afternoon availability
            avail_id = str(uuid.uuid4())
            start_time = datetime(day.year, day.month, day.day, 13, 0)
            end_time = datetime(day.year, day.month, day.day, 17, 0)
            
            cursor.execute('''
            INSERT INTO AVAILABILITY (id, professional_id, start_time, end_time,
                                     is_recurring, recurrence_pattern, duration_minutes,
                                     availability_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                avail_id, user_id, start_time, end_time,
                False, None, 240, "regular", datetime.now(), datetime.now()
            ))
            
            # Create slots for the afternoon availability
            for hour in range(13, 17):
                for minute in [0, 30]:
                    slot_start = datetime(day.year, day.month, day.day, hour, minute)
                    slot_end = slot_start + timedelta(minutes=30)
                    
                    cursor.execute('''
                    INSERT INTO APPOINTMENT_SLOTS (id, availability_id, professional_id,
                                                 start_time, end_time, is_available,
                                                 max_bookings, current_bookings, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(uuid.uuid4()), avail_id, user_id,
                        slot_start, slot_end, True, 1, 0, datetime.now()
                    ))
    
    # Generate test students/parents
    students = []
    for i in range(num_users // 2, num_users):
        user_id = str(uuid.uuid4())
        students.append(user_id)
        
        user = (
            user_id,
            f"student{i}@example.com",
            f"pbkdf2:sha256:150000$8AvVeQXB$d32387ccaa5ccfa026eae81b947d11e9ff2191c1900ad250a30b9fafd5e82c7b",  # hashed 'password'
            f"Student User {i}",
            f"+1{i}23456789",
            True,
            json.dumps({"bio": f"Student/parent bio for user {i}"}),
            datetime.now(),
            datetime.now(),
            datetime.now(),
            True
        )
        cursor.execute('''
        INSERT INTO USERS (id, email, password_hash, name, contact_number, is_verified, details, 
                         created_at, updated_at, last_login, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', user)
        
        # Assign student/parent role
        cursor.execute('''
        INSERT INTO USER_ROLES (user_id, role_id, assigned_at, assigned_by)
        VALUES (?, ?, ?, ?)
        ''', (user_id, student_parent_role_id, datetime.now(), None))
    
    # Get appointment types
    cursor.execute("SELECT id FROM APPOINTMENT_TYPES")
    appointment_type_ids = [row[0] for row in cursor.fetchall()]
    
    # Generate some random appointments
    for i in range(num_appointments):
        # Randomly select a professional and student
        professional_id = professionals[i % len(professionals)]
        student_id = students[i % len(students)]
        
        # Get an available slot for the professional
        cursor.execute('''
        SELECT id, start_time, end_time 
        FROM APPOINTMENT_SLOTS 
        WHERE professional_id = ? AND is_available = 1 AND current_bookings = 0
        LIMIT 1
        ''', (professional_id,))
        
        slot = cursor.fetchone()
        if slot:
            slot_id, start_time, end_time = slot
            
            # Parse the timestamps
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
                end_time = datetime.fromisoformat(end_time)
            
            # Create the appointment
            appointment_id = str(uuid.uuid4())
            status = "scheduled" if i % 4 != 0 else "confirmed"
            
            cursor.execute('''
            INSERT INTO APPOINTMENTS (id, student_parent_id, professional_id, slot_id,
                                    appointment_type_id, start_time, end_time, status,
                                    metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                appointment_id, student_id, professional_id, slot_id,
                appointment_type_ids[i % len(appointment_type_ids)],
                start_time, end_time, status,
                json.dumps({"notes": f"Test appointment {i}"}),
                datetime.now(), datetime.now()
            ))
            
            # Update the slot's availability
            cursor.execute('''
            UPDATE APPOINTMENT_SLOTS 
            SET is_available = 0, current_bookings = 1 
            WHERE id = ?
            ''', (slot_id,))
            
            # Create an appointment history record
            cursor.execute('''
            INSERT INTO APPOINTMENT_HISTORY (id, appointment_id, changed_by_user_id,
                                           previous_state, new_state, change_type,
                                           change_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), appointment_id, student_id,
                None, json.dumps({"status": status}), "status_change",
                "user", datetime.now()
            ))
            
            # Create a notification
            cursor.execute('''
            INSERT INTO NOTIFICATIONS (id, user_id, template_id, reference_data,
                                     type, title, message, context_data,
                                     delivery_channel, scheduled_for, is_read,
                                     is_sent, created_at, read_at, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), professional_id, None,
                json.dumps({"appointment_id": appointment_id}),
                "appointment_created", "New Appointment Scheduled",
                f"A new appointment has been scheduled for {start_time}",
                json.dumps({"student_name": f"Student User {i % len(students) + (num_users // 2)}"}),
                "email", None, False, False, datetime.now(), None, None
            ))
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"Test data generated with {num_users} users and {num_appointments} appointments.")


class AppointmentSystemDB:
    """A wrapper class for interacting with the appointment system database."""
    
    def __init__(self, db_file="appointment_system.db"):
        self.db_file = db_file
        self.conn = None
    
    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_file)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionary-like objects
        return self.conn
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # User-related methods
    def get_user_by_id(self, user_id):
        """Get a user by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM USERS WHERE id = ?", (user_id,))
        return cursor.fetchone()
    
    def get_user_by_email(self, email):
        """Get a user by email."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM USERS WHERE email = ?", (email,))
        return cursor.fetchone()
    
    def create_user(self, email, password_hash, name, contact_number=None, details=None):
        """Create a new user."""
        user_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        now = datetime.now()
        
        if details and not isinstance(details, str):
            details = json.dumps(details)
        
        cursor.execute('''
        INSERT INTO USERS (id, email, password_hash, name, contact_number, details, 
                         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, name, contact_number, details, now, now))
        
        self.conn.commit()
        return user_id
    
    def assign_role_to_user(self, user_id, role_name, assigned_by=None):
        """Assign a role to a user by role name."""
        cursor = self.conn.cursor()
        
        # Get role ID
        cursor.execute("SELECT id FROM ROLES WHERE name = ?", (role_name,))
        role = cursor.fetchone()
        if not role:
            raise ValueError(f"Role '{role_name}' not found")
        
        role_id = role['id']
        
        # Check if user already has this role
        cursor.execute("SELECT 1 FROM USER_ROLES WHERE user_id = ? AND role_id = ?", 
                     (user_id, role_id))
        if cursor.fetchone():
            return False  # User already has this role
        
        # Assign role
        cursor.execute('''
        INSERT INTO USER_ROLES (user_id, role_id, assigned_at, assigned_by)
        VALUES (?, ?, ?, ?)
        ''', (user_id, role_id, datetime.now(), assigned_by))
        
        self.conn.commit()
        return True
    
    def get_user_roles(self, user_id):
        """Get all roles for a user."""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT r.id, r.name, r.description
        FROM ROLES r
        JOIN USER_ROLES ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
        ''', (user_id,))
        
        return cursor.fetchall()
    
    # Authentication-related methods
    def create_auth_token(self, user_id, token_type="session", expires_in_hours=24):
        """Create a new authentication token for a user."""
        token_id = str(uuid.uuid4())
        token = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=expires_in_hours)
        
        cursor = self.conn.cursor()
        
        # If it's a session token, optionally revoke existing session tokens
        if token_type == "session":
            cursor.execute('''
            UPDATE AUTH_TOKENS
            SET expires_at = ?
            WHERE user_id = ? AND token_type = ? AND expires_at > ?
            ''', (now, user_id, token_type, now))
        
        cursor.execute('''
        INSERT INTO AUTH_TOKENS (id, user_id, token, expires_at, token_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (token_id, user_id, token, expires_at, token_type, now))
        
        self.conn.commit()
        return token
    
    def verify_auth_token(self, token):
        """Verify an authentication token and return the user_id if valid."""
        now = datetime.now()
        cursor = self.conn.cursor()
        
        cursor.execute('''
        SELECT user_id, token_type
        FROM AUTH_TOKENS
        WHERE token = ? AND expires_at > ?
        ''', (token, now))
        
        result = cursor.fetchone()
        if result:
            # Update last_used_at
            cursor.execute('''
            UPDATE AUTH_TOKENS
            SET last_used_at = ?
            WHERE token = ?
            ''', (now, token))
            
            self.conn.commit()
            return result['user_id'], result['token_type']
        
        return None, None
    
    def revoke_auth_token(self, token):
        """Revoke an authentication token."""
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE AUTH_TOKENS
        SET expires_at = ?
        WHERE token = ?
        ''', (datetime.now(), token))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Availability and slots methods
    def get_professional_availability(self, professional_id, start_date=None, end_date=None):
        """Get availability for a professional within a date range."""
        cursor = self.conn.cursor()
        
        params = [professional_id]
        query = "SELECT * FROM AVAILABILITY WHERE professional_id = ?"
        
        if start_date:
            query += " AND end_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND start_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY start_time"
        cursor.execute(query, params)
        
        return cursor.fetchall()
    
    def create_availability(self, professional_id, start_time, end_time, is_recurring=False, 
                            recurrence_pattern=None, duration_minutes=None, availability_type="regular"):
        """Create a new availability block for a professional."""
        if not duration_minutes:
            # Calculate duration in minutes
            duration = end_time - start_time
            duration_minutes = int(duration.total_seconds() / 60)
        
        availability_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
        INSERT INTO AVAILABILITY (id, professional_id, start_time, end_time, is_recurring,
                               recurrence_pattern, duration_minutes, availability_type,
                               created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (availability_id, professional_id, start_time, end_time, is_recurring,
              recurrence_pattern, duration_minutes, availability_type, now, now))
        
        self.conn.commit()
        return availability_id
    
    def generate_slots_from_availability(self, availability_id, slot_duration_minutes=30):
        """Generate appointment slots from an availability block."""
        cursor = self.conn.cursor()
        
        # Get availability details
        cursor.execute("SELECT * FROM AVAILABILITY WHERE id = ?", (availability_id,))
        availability = cursor.fetchone()
        if not availability:
            raise ValueError(f"Availability with ID {availability_id} not found")
        
        professional_id = availability['professional_id']
        start_time = availability['start_time']
        end_time = availability['end_time']
        
        # If start_time/end_time are strings, convert to datetime objects
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
        
        # Generate slots
        slots = []
        current_time = start_time
        slot_duration = timedelta(minutes=slot_duration_minutes)
        
        while current_time + slot_duration <= end_time:
            slot_id = str(uuid.uuid4())
            slot_end = current_time + slot_duration
            
            cursor.execute('''
            INSERT INTO APPOINTMENT_SLOTS (id, availability_id, professional_id,
                                         start_time, end_time, is_available,
                                         max_bookings, current_bookings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (slot_id, availability_id, professional_id,
                  current_time, slot_end, True, 1, 0, datetime.now()))
            
            slots.append({
                'id': slot_id,
                'start_time': current_time,
                'end_time': slot_end
            })
            
            current_time = slot_end
        
        self.conn.commit()
        return slots
    
    def get_available_slots(self, professional_id=None, start_date=None, end_date=None):
        """Get available appointment slots."""
        cursor = self.conn.cursor()
        
        params = []
        query = """
        SELECT s.*, u.name as professional_name
        FROM APPOINTMENT_SLOTS s
        JOIN USERS u ON s.professional_id = u.id
        WHERE s.is_available = 1 AND s.current_bookings < s.max_bookings
        """
        
        if professional_id:
            query += " AND s.professional_id = ?"
            params.append(professional_id)
        
        if start_date:
            query += " AND s.end_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND s.start_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY s.start_time"
        cursor.execute(query, params)
        
        return cursor.fetchall()
    
    # Appointment methods
    def create_appointment(self, student_parent_id, professional_id, slot_id, appointment_type_id, 
                           start_time=None, end_time=None, status="scheduled", metadata=None):
        """Create a new appointment."""
        appointment_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        now = datetime.now()
        
        # If start/end time not provided, get them from the slot
        if not start_time or not end_time:
            cursor.execute("SELECT start_time, end_time FROM APPOINTMENT_SLOTS WHERE id = ?", (slot_id,))
            slot = cursor.fetchone()
            if not slot:
                raise ValueError(f"Slot with ID {slot_id} not found")
            
            start_time = slot['start_time']
            end_time = slot['end_time']
        
        if metadata and not isinstance(metadata, str):
            metadata = json.dumps(metadata)
        
        # Begin transaction
        self.conn.execute("BEGIN TRANSACTION")
        
        try:
            # Create appointment
            cursor.execute('''
            INSERT INTO APPOINTMENTS (id, student_parent_id, professional_id, slot_id,
                                    appointment_type_id, start_time, end_time, status,
                                    metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (appointment_id, student_parent_id, professional_id, slot_id,
                  appointment_type_id, start_time, end_time, status,
                  metadata, now, now))
            
            # Update slot availability
            cursor.execute('''
            UPDATE APPOINTMENT_SLOTS
            SET is_available = CASE WHEN current_bookings + 1 >= max_bookings THEN 0 ELSE 1 END,
                current_bookings = current_bookings + 1
            WHERE id = ?
            ''', (slot_id,))
            
            # Create appointment history record
            new_state = {
                'status': status,
                'start_time': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
                'end_time': end_time.isoformat() if isinstance(end_time, datetime) else end_time
            }
            
            cursor.execute('''
            INSERT INTO APPOINTMENT_HISTORY (id, appointment_id, changed_by_user_id,
                                           previous_state, new_state, change_type,
                                           change_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), appointment_id, student_parent_id,
                  None, json.dumps(new_state), "status_change",
                  "user", now))
            
            self.conn.commit()
            return appointment_id
        
        except Exception as e:
            self.conn.rollback()
            raise e
    
    def get_appointment(self, appointment_id):
        """Get appointment details by ID."""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT a.*, 
               s.name as student_name,
               p.name as professional_name,
               t.name as appointment_type_name,
               t.duration_minutes,
               t.color_code
        FROM APPOINTMENTS a
        JOIN USERS s ON a.student_parent_id = s.id
        JOIN USERS p ON a.professional_id = p.id
        JOIN APPOINTMENT_TYPES t ON a.appointment_type_id = t.id
        WHERE a.id = ?
        ''', (appointment_id,))
        
        return cursor.fetchone()
    
    def get_user_appointments(self, user_id, role=None, status=None, start_date=None, end_date=None):
        """Get appointments for a user, either as student/parent or professional."""
        cursor = self.conn.cursor()
        
        params = [user_id]
        query = """
        SELECT a.*, 
               s.name as student_name,
               p.name as professional_name,
               t.name as appointment_type_name,
               t.duration_minutes,
               t.color_code
        FROM APPOINTMENTS a
        JOIN USERS s ON a.student_parent_id = s.id
        JOIN USERS p ON a.professional_id = p.id
        JOIN APPOINTMENT_TYPES t ON a.appointment_type_id = t.id
        WHERE 
        """
        
        if role == "professional":
            query += "a.professional_id = ?"
        elif role == "student_parent":
            query += "a.student_parent_id = ?"
        else:
            query += "(a.professional_id = ? OR a.student_parent_id = ?)"
            params.append(user_id)
        
        if status:
            query += " AND a.status = ?"
            params.append(status)
        
        if start_date:
            query += " AND a.end_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND a.start_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY a.start_time"
        cursor.execute(query, params)
        
        return cursor.fetchall()
    
    def update_appointment_status(self, appointment_id, new_status, changed_by_user_id, notes=None):
        """Update the status of an appointment."""
        cursor = self.conn.cursor()
        now = datetime.now()
        
        # Begin transaction
        self.conn.execute("BEGIN TRANSACTION")
        
        try:
            # Get current appointment details for history
            cursor.execute("SELECT * FROM APPOINTMENTS WHERE id = ?", (appointment_id,))
            appointment = cursor.fetchone()
            if not appointment:
                raise ValueError(f"Appointment with ID {appointment_id} not found")
            
            previous_state = {
                'status': appointment['status'],
                'start_time': appointment['start_time'],
                'end_time': appointment['end_time']
            }
            
            # Update appointment status
            cursor.execute('''
            UPDATE APPOINTMENTS
            SET status = ?, updated_at = ?
            WHERE id = ?
            ''', (new_status, now, appointment_id))
            
            # Create appointment history record
            new_state = dict(previous_state)
            new_state['status'] = new_status
            
            cursor.execute('''
            INSERT INTO APPOINTMENT_HISTORY (id, appointment_id, changed_by_user_id,
                                           previous_state, new_state, change_type,
                                           change_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), appointment_id, changed_by_user_id,
                  json.dumps(previous_state), json.dumps(new_state), "status_change",
                  "user", now))
            
            # If cancelled, create cancellation record
            if new_status == "cancelled":
                cursor.execute('''
                INSERT INTO CANCELLATIONS (id, appointment_id, cancelled_by_user_id,
                                         reason, notified_users, is_notified,
                                         created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), appointment_id, changed_by_user_id,
                      notes, json.dumps([]), False, now))
                
                # Update the slot availability if cancelled
                cursor.execute('''
                UPDATE APPOINTMENT_SLOTS
                SET current_bookings = current_bookings - 1,
                    is_available = 1
                WHERE id = ?
                ''', (appointment['slot_id'],))
            
            self.conn.commit()
            return True
        
        except Exception as e:
            self.conn.rollback()
            raise e
    
    # Notification methods
    def create_notification(self, user_id, notification_type, title, message, 
                            reference_data=None, template_id=None, context_data=None,
                            delivery_channel="email", scheduled_for=None):
        """Create a notification for a user."""
        notification_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        now = datetime.now()
        
        if reference_data and not isinstance(reference_data, str):
            reference_data = json.dumps(reference_data)
            
        if context_data and not isinstance(context_data, str):
            context_data = json.dumps(context_data)
        
        cursor.execute('''
        INSERT INTO NOTIFICATIONS (id, user_id, template_id, reference_data,
                               type, title, message, context_data,
                               delivery_channel, scheduled_for, is_read,
                               is_sent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (notification_id, user_id, template_id, reference_data,
              notification_type, title, message, context_data,
              delivery_channel, scheduled_for, False, False, now))
        
        self.conn.commit()
        return notification_id
    
    def get_user_notifications(self, user_id, is_read=None, limit=50, offset=0):
        """Get notifications for a user."""
        cursor = self.conn.cursor()
        
        params = [user_id]
        query = "SELECT * FROM NOTIFICATIONS WHERE user_id = ?"
        
        if is_read is not None:
            query += " AND is_read = ?"
            params.append(1 if is_read else 0)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def mark_notification_as_read(self, notification_id):
        """Mark a notification as read."""
        cursor = self.conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
        UPDATE NOTIFICATIONS
        SET is_read = 1, read_at = ?
        WHERE id = ?
        ''', (now, notification_id))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Communication methods
    def create_communication_log(self, appointment_id, sender_user_id, recipient_user_id,
                                message_type, content, attachment_urls=None, 
                                visibility_level="public"):
        """Create a communication log entry for an appointment."""
        log_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        now = datetime.now()
        
        if attachment_urls and not isinstance(attachment_urls, str):
            attachment_urls = json.dumps(attachment_urls)
        
        cursor.execute('''
        INSERT INTO COMMUNICATION_LOGS (id, appointment_id, sender_user_id, recipient_user_id,
                                     message_type, content, attachment_urls, is_read,
                                     visibility_level, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_id, appointment_id, sender_user_id, recipient_user_id,
              message_type, content, attachment_urls, False,
              visibility_level, now))
        
        self.conn.commit()
        return log_id
    
    def get_appointment_communications(self, appointment_id, visibility_level=None):
        """Get communication logs for an appointment."""
        cursor = self.conn.cursor()
        
        params = [appointment_id]
        query = """
        SELECT c.*, 
               s.name as sender_name,
               r.name as recipient_name
        FROM COMMUNICATION_LOGS c
        JOIN USERS s ON c.sender_user_id = s.id
        JOIN USERS r ON c.recipient_user_id = r.id
        WHERE c.appointment_id = ? AND c.is_deleted = 0
        """
        
        if visibility_level:
            query += " AND c.visibility_level = ?"
            params.append(visibility_level)
        
        query += " ORDER BY c.created_at"
        cursor.execute(query, params)
        
        return cursor.fetchall()

    def mark_communication_as_read(self, communication_id, user_id):
        """Mark a communication log as read by the recipient."""
        cursor = self.conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
        UPDATE COMMUNICATION_LOGS
        SET is_read = 1, read_at = ?
        WHERE id = ? AND recipient_user_id = ?
        ''', (now, communication_id, user_id))
        
        self.conn.commit()
        return cursor.rowcount > 0


# Main execution
if __name__ == "__main__":
    # Create the database
    db_file = create_database()
    
    # Generate test data
    generate_test_data(db_file)
    
    # Test the database wrapper
    with AppointmentSystemDB(db_file) as db:
        # Get admin user
        admin = db.get_user_by_email("admin@example.com")
        if admin:
            print(f"Found admin user: {admin['name']}")
            
            # Get admin roles
            roles = db.get_user_roles(admin['id'])
            role_names = [role['name'] for role in roles]
            print(f"Admin roles: {', '.join(role_names)}")
        
        # Get available slots
        slots = db.get_available_slots()
        print(f"Found {len(slots)} available appointment slots")
        
        # Get appointments
        appointments = db.get_user_appointments(admin['id'])
        print(f"Found {len(appointments)} appointments for admin")
        
    print("Database setup and testing completed.")