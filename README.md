# ACC Portal System

A complete student portal prototype for **ACC (Abuyog Community College)** using:

- Backend: Python + Flask
- Frontend: HTML + CSS
- Database: SQLite
- Authentication: Flask sessions + Werkzeug password hashing

## Included features

1. Student registration
2. Username/email + password credentials
3. Valid ID upload (PDF/JPG/JPEG/PNG, max 5 MB)
4. Login/logout with session handling
5. Student dashboard
6. Scholarship application
7. SQLite database created automatically
8. Form validation and protected uploaded ID route
9. Responsive ACC-themed interface

## Project structure

```text
acc_portal_system/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── instance/
│   └── acc_portal.db        # generated automatically after first run
├── static/
│   ├── css/
│   │   └── style.css
│   └── uploads/
│       └── .gitkeep
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    └── scholarship.html
```

## How to run on Windows

Open CMD or PowerShell inside this project folder.

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate it

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

CMD:

```cmd
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the system

```powershell
python app.py
```

### 5. Open the portal

Go to:

`http://127.0.0.1:5000`

The SQLite database is automatically created at `instance/acc_portal.db`.

## Notes for school/demo use

- Change the `SECRET_KEY` environment variable before deploying publicly.
- Uploaded valid IDs are stored in `static/uploads/` and are protected by the application route.
- This is a student-project portal, not a production admissions system. A production deployment should add HTTPS, stronger account policies, rate limiting, audit logs, CSRF protection via a dedicated Flask extension, malware scanning for uploads, and a real administrator workflow.
