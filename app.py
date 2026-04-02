"""
╔══════════════════════════════════════════════════════════════════╗
║   UTKARSH 2K26 — Tech Fare & Exhibition Registration Backend     ║
║   University Institute of Technology, Shimla                     ║
║   Developed by: Aradhya Kaul (Senior Developer, IIC UIT Shimla)  ║
║   Contact: aradhyakaul540@gmail.com | +91 8091077622             ║
╚══════════════════════════════════════════════════════════════════╝
"""
from dotenv import load_dotenv
load_dotenv()
import os
import uuid
import secrets
import hashlib
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, abort
import mysql.connector
from mysql.connector import Error

# ────────────────────────────────────────────
#  CONFIGURATION  (edit before running)
# ────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# Admin credentials (change these!)
ADMIN_CREDENTIALS = {
    os.getenv("ADMIN_1_USERNAME"): os.getenv("ADMIN_1_PASSWORD"),
    os.getenv("ADMIN_2_USERNAME"): os.getenv("ADMIN_2_PASSWORD"),
}

# Email config — use your Gmail / SMTP credentials
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME")

# Token store (in-memory; for production use Redis/DB)
_admin_tokens: dict[str, str] = {}  # token → username

# ────────────────────────────────────────────
#  FLASK APP
# ────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")


# ── SERVE FRONTEND ──────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/admin")
def admin_page():
    return send_from_directory(".", "admin.html")


# ── DB HELPER ───────────────────────────────
def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# ── AUTH DECORATOR ──────────────────────────
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if token not in _admin_tokens:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ────────────────────────────────────────────
#  PUBLIC — REGISTRATION
# ────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # ── Validate required top-level fields ──
    required = ["team_name", "category", "project_title", "abstract", "leader"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    leader = data["leader"]
    leader_required = ["name", "roll", "email", "phone", "branch", "semester"]
    missing_leader = [f for f in leader_required if not leader.get(f)]
    if missing_leader:
        return jsonify({"error": f"Leader fields missing: {', '.join(missing_leader)}"}), 400

    members = data.get("members", [])
    if len(members) > 4:
        return jsonify({"error": "Maximum 4 additional members allowed (5 total with leader)"}), 400

    # ── Generate registration ID ──
    reg_id = f"UTK2K26-{uuid.uuid4().hex[:8].upper()}"

    try:
        conn = get_db()
        cur = conn.cursor()

        # Insert team
        cur.execute("""
            INSERT INTO teams
              (registration_id, team_name, category, project_title, abstract, status, registered_at)
            VALUES (%s,%s,%s,%s,%s,'pending', NOW())
        """, (reg_id, data["team_name"].strip(), data["category"],
              data["project_title"].strip(), data["abstract"].strip()))
        team_id = cur.lastrowid

        # Insert leader
        cur.execute("""
            INSERT INTO team_members
              (team_id, name, roll_number, email, phone, branch, semester, is_leader)
            VALUES (%s,%s,%s,%s,%s,%s,%s,1)
        """, (team_id, leader["name"].strip(), leader["roll"].strip(),
              leader["email"].strip(), leader["phone"].strip(),
              leader["branch"].strip(), leader["semester"]))

        # Insert additional members
        for m in members:
            if not m.get("name"):
                continue
            cur.execute("""
                INSERT INTO team_members
                  (team_id, name, roll_number, email, phone, branch, semester, is_leader)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0)
            """, (team_id, m.get("name","").strip(), m.get("roll","").strip(),
                  m.get("email","").strip(), m.get("phone","").strip(),
                  m.get("branch","").strip(), m.get("semester","")))

        conn.commit()
        cur.close()
        conn.close()

        # Send acknowledgement email to leader
        _send_ack_email(leader["email"], leader["name"], data["team_name"], reg_id)

        return jsonify({"message": "Registration submitted successfully", "registration_id": reg_id}), 200

    except Error as e:
        app.logger.error(f"DB error on register: {e}")
        return jsonify({"error": "Database error. Please try again."}), 500


# ────────────────────────────────────────────
#  ADMIN — LOGIN
# ────────────────────────────────────────────
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    stored = ADMIN_CREDENTIALS.get(username)
    if not stored or stored != password:
        return jsonify({"error": "Invalid credentials"}), 401

    token = secrets.token_hex(32)
    _admin_tokens[token] = username
    return jsonify({"token": token, "username": username}), 200


# ────────────────────────────────────────────
#  ADMIN — GET ALL TEAMS (list)
# ────────────────────────────────────────────
@app.route("/api/admin/teams", methods=["GET"])
@require_admin
def admin_get_teams():
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT
                t.id, t.registration_id, t.team_name, t.category,
                t.project_title, t.status, t.registered_at,
                (SELECT name  FROM team_members WHERE team_id=t.id AND is_leader=1 LIMIT 1) AS leader_name,
                (SELECT email FROM team_members WHERE team_id=t.id AND is_leader=1 LIMIT 1) AS leader_email,
                (SELECT phone FROM team_members WHERE team_id=t.id AND is_leader=1 LIMIT 1) AS leader_phone,
                (SELECT branch FROM team_members WHERE team_id=t.id AND is_leader=1 LIMIT 1) AS leader_branch,
                (SELECT semester FROM team_members WHERE team_id=t.id AND is_leader=1 LIMIT 1) AS leader_semester,
                (SELECT COUNT(*) FROM team_members WHERE team_id=t.id) AS member_count
            FROM teams t
            ORDER BY t.registered_at DESC
        """)
        teams = cur.fetchall()

        # Make datetime JSON-serialisable
        for t in teams:
            if isinstance(t.get("registered_at"), datetime.datetime):
                t["registered_at"] = t["registered_at"].isoformat()

        cur.close(); conn.close()
        return jsonify({"teams": teams}), 200

    except Error as e:
        app.logger.error(f"DB error on admin/teams: {e}")
        return jsonify({"error": "Database error"}), 500


# ────────────────────────────────────────────
#  ADMIN — GET SINGLE TEAM (detail)
# ────────────────────────────────────────────
@app.route("/api/admin/teams/<int:team_id>", methods=["GET"])
@require_admin
def admin_get_team(team_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM teams WHERE id=%s", (team_id,))
        team = cur.fetchone()
        if not team:
            cur.close(); conn.close()
            return jsonify({"error": "Team not found"}), 404

        cur.execute("SELECT * FROM team_members WHERE team_id=%s ORDER BY is_leader DESC, id ASC", (team_id,))
        members = cur.fetchall()

        team["members"] = members
        if isinstance(team.get("registered_at"), datetime.datetime):
            team["registered_at"] = team["registered_at"].isoformat()

        cur.close(); conn.close()
        return jsonify(team), 200

    except Error as e:
        app.logger.error(f"DB error on team detail: {e}")
        return jsonify({"error": "Database error"}), 500


# ────────────────────────────────────────────
#  ADMIN — UPDATE STATUS + SEND EMAIL
# ────────────────────────────────────────────
@app.route("/api/admin/teams/<int:team_id>/status", methods=["POST"])
@require_admin
def admin_update_status(team_id):
    data = request.get_json(force=True) or {}
    new_status = data.get("status", "").lower()
    custom_msg = data.get("message", "")

    if new_status not in ("approved", "rejected"):
        return jsonify({"error": "Status must be 'approved' or 'rejected'"}), 400

    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # Fetch team + leader
        cur.execute("SELECT * FROM teams WHERE id=%s", (team_id,))
        team = cur.fetchone()
        if not team:
            cur.close(); conn.close()
            return jsonify({"error": "Team not found"}), 404

        cur.execute("SELECT * FROM team_members WHERE team_id=%s AND is_leader=1 LIMIT 1", (team_id,))
        leader = cur.fetchone()

        # Update status
        cur.execute("UPDATE teams SET status=%s, updated_at=NOW() WHERE id=%s", (new_status, team_id))
        conn.commit()
        cur.close(); conn.close()

        # Send email
        if leader and leader.get("email"):
            _send_decision_email(
                to_email=leader["email"],
                leader_name=leader["name"],
                team_name=team["team_name"],
                reg_id=team["registration_id"],
                status=new_status,
                custom_msg=custom_msg
            )

        return jsonify({"message": f"Team {new_status} and email sent successfully"}), 200

    except Error as e:
        app.logger.error(f"DB error on status update: {e}")
        return jsonify({"error": "Database error"}), 500


# ────────────────────────────────────────────
#  EMAIL HELPERS
# ────────────────────────────────────────────
def _build_email(to_email: str, subject: str, html_body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _send_via_smtp(msg: MIMEMultipart, to_email: str):
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        app.logger.info(f"Email sent to {to_email}")
    except Exception as e:
        app.logger.error(f"Email send failed to {to_email}: {e}")


def _send_ack_email(to_email, leader_name, team_name, reg_id):
    subject = f"[Utkarsh 2K26] Registration Received — {team_name}"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#020510;color:#e0f7fa;padding:40px;border:1px solid rgba(0,245,255,0.3);">
      <h2 style="color:#00f5ff;font-size:22px;letter-spacing:3px;">⚡ UTKARSH 2K26</h2>
      <p style="color:#4dd0e1;letter-spacing:2px;font-size:12px;">TECH FARE & EXHIBITION · UIT SHIMLA</p>
      <hr style="border-color:rgba(0,245,255,0.2);margin:20px 0;">
      <p>Dear <strong>{leader_name}</strong>,</p>
      <p>Your team <strong style="color:#00f5ff;">"{team_name}"</strong> has been successfully registered for <strong>Utkarsh 2K26 — Tech Fare & Exhibition</strong>.</p>
      <div style="background:rgba(0,245,255,0.05);border:1px solid rgba(0,245,255,0.2);padding:16px;margin:20px 0;">
        <p style="margin:0;">Registration ID: <strong style="color:#00f5ff;font-family:monospace;">{reg_id}</strong></p>
      </div>
      <p><strong style="color:#ffea00;">⚠ IMPORTANT:</strong> Your participation is <u>pending admin approval</u>. You will receive a confirmation/rejection email once reviewed.</p>
      <hr style="border-color:rgba(0,245,255,0.2);margin:20px 0;">
      <p style="font-size:12px;color:rgba(77,208,225,0.6);">For assistance: Aradhya Kaul (IIC UIT Shimla)<br>📞 +91 8091077622 | ✉️ aradhyakaul540@gmail.com</p>
      <p style="font-size:11px;color:rgba(77,208,225,0.4);margin-top:20px;">© 2026 Utkarsh 2K26 · University Institute of Technology, Shimla</p>
    </div>"""
    _send_via_smtp(_build_email(to_email, subject, body), to_email)


def _send_decision_email(to_email, leader_name, team_name, reg_id, status, custom_msg=""):
    color = "#39ff14" if status == "approved" else "#ff3131"
    icon = "✅" if status == "approved" else "❌"
    action_text = "APPROVED" if status == "approved" else "REJECTED"
    default_msg = (
        f"Congratulations! Your team <strong>\"{team_name}\"</strong> has been selected to participate in <strong>Utkarsh 2K26 — Tech Fare & Exhibition</strong>. Please report to the venue on the event date with your project setup. We look forward to seeing your innovation!"
        if status == "approved"
        else
        f"We regret to inform you that your team <strong>\"{team_name}\"</strong> has not been selected for Utkarsh 2K26 this time. We encourage you to keep innovating and apply again in future events."
    )
    final_msg = custom_msg.strip() if custom_msg.strip() else default_msg

    subject = f"[Utkarsh 2K26] Team {action_text} — {team_name}"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#020510;color:#e0f7fa;padding:40px;border:1px solid rgba(0,245,255,0.3);">
      <h2 style="color:#00f5ff;font-size:22px;letter-spacing:3px;">⚡ UTKARSH 2K26</h2>
      <p style="color:#4dd0e1;letter-spacing:2px;font-size:12px;">TECH FARE & EXHIBITION · UIT SHIMLA</p>
      <hr style="border-color:rgba(0,245,255,0.2);margin:20px 0;">
      <div style="text-align:center;padding:20px;background:rgba(255,255,255,0.03);border:1px solid {color}33;margin-bottom:24px;">
        <div style="font-size:48px;">{icon}</div>
        <div style="font-family:monospace;font-size:22px;color:{color};letter-spacing:4px;margin-top:8px;">TEAM {action_text}</div>
      </div>
      <p>Dear <strong>{leader_name}</strong>,</p>
      <p>{final_msg}</p>
      <div style="background:rgba(0,245,255,0.05);border:1px solid rgba(0,245,255,0.2);padding:16px;margin:20px 0;">
        <p style="margin:0 0 6px 0;">Team: <strong style="color:#00f5ff;">{team_name}</strong></p>
        <p style="margin:0;">Registration ID: <strong style="font-family:monospace;color:#00f5ff;">{reg_id}</strong></p>
      </div>
      <hr style="border-color:rgba(0,245,255,0.2);margin:20px 0;">
      <p style="font-size:12px;color:rgba(77,208,225,0.6);">For assistance: Aradhya Kaul (IIC UIT Shimla)<br>📞 +91 8091077622 | ✉️ aradhyakaul540@gmail.com</p>
      <p style="font-size:11px;color:rgba(77,208,225,0.4);margin-top:20px;">© 2026 Utkarsh 2K26 · University Institute of Technology, Shimla</p>
    </div>"""
    _send_via_smtp(_build_email(to_email, subject, body), to_email)


# ────────────────────────────────────────────
#  ENTRY POINT
# ────────────────────────────────────────────

if __name__ == "__main__":
    app.run()