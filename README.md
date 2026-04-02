# ⚡ UTKARSH 2K26 — Tech Fare & Exhibition Registration System
## University Institute of Technology, Shimla

---

## 📁 Project Structure
```
utkarsh2k26/
├── index.html      ← Main registration frontend
├── admin.html      ← Admin portal (served at /admin)
├── app.py          ← Flask backend (Python)
├── schema.sql      ← MySQL database schema
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Install Python packages
```bash
pip install -r requirements.txt
```

### 2. Set up MySQL Database (MySQL Workbench)
- Open MySQL Workbench
- Connect to your local MySQL server
- Run `schema.sql` (File → Run SQL Script or paste into editor)

### 3. Configure `app.py`
Edit the top of `app.py`:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",            # your MySQL username
    "password": "YOUR_PASSWORD", # your MySQL password
    "database": "utkarsh2k26"
}

EMAIL_FROM    = "aradhyakaul540@gmail.com"  # admin sender
EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"       # Gmail App Password
```

**Gmail App Password Setup:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Search "App Passwords" → Create for "Mail"
4. Copy the 16-char password into `EMAIL_PASSWORD`

### 4. Admin Credentials (change in `app.py`)
```python
ADMIN_CREDENTIALS = {
    "admin": "UTK2K26@Admin",
    "uitshimla": "IIC@2026Secure"
}
```

### 5. Run the application
```bash
python app.py
```
Visit: http://localhost:5000  
Admin: http://localhost:5000/admin

---

## 🔑 Admin Portal Features
| Feature | Description |
|---------|-------------|
| Secure Login | Username + password with token auth |
| Dashboard Stats | Total / Pending / Approved / Rejected |
| Team Table | Search, filter by status |
| Team Detail | View all member info (name, roll, email, phone) |
| Approve/Reject | One-click or via detail modal |
| Email Notification | Auto-sends to team leader on decision |
| Custom Email | Admin can write custom message |
| CSV Download | All teams with full contact details |

---

## 📧 Email Flow
```
Student registers → Acknowledgement email (auto)
Admin approves   → Approval email (green, celebratory)
Admin rejects    → Rejection email (with encouragement)
```

---

## 👨‍💻 Developer
**Aradhya Kaul** — Senior Developer, IIC UIT Shimla  
📞 +91 8091077622  
✉️ aradhyakaul540@gmail.com

---

© 2026 Utkarsh 2K26 · University Institute of Technology, Shimla · All Rights Reserved
