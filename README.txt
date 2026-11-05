HOSTELMATE — COMPLETE SMART HOSTEL MANAGEMENT DEMO
==================================================

FEATURES INCLUDED
- Student registration/login with hashed passwords and role-based access
- Admin and Warden demo accounts created automatically on first run
- Student dashboard and management dashboard with summary metrics
- Hostel complaint submission, priority selection, duplicate unresolved complaint detection
- Admin/Warden complaint status updates: Pending, In Progress, Resolved
- Resource sharing listings, search, category filtering, borrow/share offers
- Resource requests, owner approval/rejection, mark returned workflow
- Lost & Found posts and resolution workflow
- Mess menu publication by Admin/Warden and student feedback
- Hostel notices published by Admin/Warden
- Responsive HTML/CSS interface
- SQLite database is created automatically

REQUIREMENTS
- Python 3.10 or newer recommended
- Internet is not required for core functionality; Google Fonts are optional styling only.

RUN ON WINDOWS
1. Extract this ZIP into a folder.
2. Open the folder in VS Code.
3. Open Terminal > New Terminal.
4. Run:
     py -m pip install -r requirements.txt
     py app.py
5. Open in your browser:
     http://127.0.0.1:5000

DEMO ACCOUNTS (created automatically if missing)
Admin:
  Email: admin@hostelmate.com
  Password: Admin@123
Warden:
  Email: warden@hostelmate.com
  Password: Warden@123
Students can register through the Register page.

IMPORTANT
- Change app.secret_key and all demo passwords before any real deployment.
- This is a local hackathon/demo project, not a production-ready hostel system.
- No email/SMS/push notifications, payments, file uploads, or real AI model are included.
- Duplicate complaint detection and resource matching are rule-based, not machine-learning models.
- Avoid putting private student contact information in public posts. The Lost & Found contact field is optional.
- SQLite data is stored in hostelmate.db in the current working directory. Back it up before moving the project.
- Run only on your own computer for the demo; debug=True is enabled for local development.
