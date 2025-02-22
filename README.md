# 📆 Schedule - Appointment System API

A flexible, open-source appointment scheduling system built with Flask.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-orange.svg)

## ✨ Quick Start

```bash
# Clone the repository
git clone https://github.com/luisadrianpuga/schedule.git

# Navigate to project directory
cd schedule

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up the database
python3 sqlite_setup.py

# Run the application
python3 app.py
```

The API will be available at `http://localhost:8080`

## 🎯 Key Features

- **📱 User Management**: Registration, authentication, and role-based permissions
- **⏰ Availability Management**: Professionals can define their available time slots
- **📅 Appointment Booking**: Students/parents can book appointments with professionals
- **📣 Notifications**: Email notifications for appointment status changes
- **💬 Communication**: Messaging between professionals and students
- **⭐ Rating System**: Review completed appointments
- **🛡️ Role-Based Access**: Different capabilities for professionals, students/parents, and admins

## 📋 System Requirements

- Python 3.6+
- SQLite (embedded, no separate installation required)
- Virtual environment with dependencies (included in repo)

> **Note:** The repository includes a virtual environment (`venv`) with all required dependencies.

## 🔧 Configuration

Configuration is done through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | 8080 |
| `FLASK_ENV` | Environment (development/production) | development |
| `DB_FILE` | Database file path | appointment_system.db |

Example:
```bash
PORT=9000 FLASK_ENV=production python app.py
```

## 🔍 API Overview

The API is organized around RESTful principles with the following main endpoints:

### 🔐 Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register a new user |
| `/api/auth/login` | POST | Login and get auth token |
| `/api/auth/logout` | POST | Logout (revoke token) |
| `/api/auth/verify-email` | POST | Verify user email |

### 👤 Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/users/me` | GET | Get current user profile |
| `/api/users/me` | PATCH | Update current user profile |

### Default Test Users

When the database is created, the following test users are available:

| Type | Email | Password | Description |
|------|-------|----------|-------------|
| Admin | admin@example.com | adminpassword | System administrator with full access |
| Professional | professional0@example.com | password | Service provider with availability |
| Student/Parent | student5@example.com | password | User who can book appointments |

### 📅 Appointments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/appointments` | GET | Get user appointments |
| `/api/appointments` | POST | Create a new appointment |
| `/api/appointments/<id>` | GET | Get appointment details |
| `/api/appointments/<id>/status` | PUT | Update appointment status |
| `/api/appointments/<id>/rating` | POST | Rate an appointment |

### ⏰ Availability

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/professionals` | GET | List all professionals |
| `/api/professionals/<id>/availability` | GET | Get professional's availability |
| `/api/professionals/<id>/availability` | POST | Create availability for professional |

### 📨 Communication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/appointments/<id>/communications` | POST | Add communication to appointment |

### 🔔 Notifications

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications` | GET | Get user notifications |
| `/api/notifications/<id>/read` | PUT | Mark notification as read |

## 💻 Code Structure

```
schedule/
├── app.py               # Main application entry point
├── sqlite_setup.py      # Database schema and setup
├── api_utilities.py     # Shared utilities for the API
└── requirements.txt     # Python dependencies
```

## 📚 Example Usage

Here are some common API calls you can make with curl:

### Register a new user

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword",
    "name": "John Smith",
    "role": "student_parent"
  }'
```

### Login

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword"
  }'
```

Save the token from the response:
```json
{
  "success": true,
  "data": {
    "token": "your-auth-token-here",
    "user": {...}
  }
}
```

### Get available slots

```bash
curl -X GET http://localhost:8080/api/professionals/[professional_id]/availability \
  -H "Authorization: Bearer your-auth-token-here"
```

### Book an appointment

```bash
curl -X POST http://localhost:8080/api/appointments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-auth-token-here" \
  -d '{
    "professional_id": "[professional_id]",
    "slot_id": "[slot_id]",
    "appointment_type_id": "[appointment_type_id]"
  }'
```

## 🔄 Database Schema

The system uses SQLite with the following main tables:

- `USERS`: User accounts
- `ROLES`: System roles (admin, professional, student_parent)
- `AVAILABILITY`: Professional availability blocks
- `APPOINTMENT_SLOTS`: Individual bookable time slots
- `APPOINTMENTS`: Booked appointments
- `COMMUNICATION_LOGS`: Messages between users
- `NOTIFICATIONS`: System notifications

### Database Setup

The database needs to be set up manually before running the application:

```bash
# Create and populate the database
python3 sqlite_setup.py
```

This will create `appointment_system.db` with test data including:

- Admin user (email: admin@example.com, password: adminpassword)
- Test professional users with availability slots
- Test student/parent users
- Sample appointment types

If you want to reset the database:

```bash
# Delete the existing database
rm appointment_system.db

# Run the setup script again
python3 sqlite_setup.py
```

## 🛠️ Development

### Adding a new endpoint

1. Define the route in `app.py`
2. Implement authentication/authorization with `@auth_required()`
3. Add necessary database operations in the route function
4. Return standardized responses using `success_response()` or `error_response()`



## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [SQLite](https://www.sqlite.org/index.html) - Embedded database
- [Flask-CORS](https://flask-cors.readthedocs.io/) - CORS handling for the API