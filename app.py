from flask import Flask, render_template, request, redirect, g, session
import sqlite3
import os

print("Starting Flask Application...")

app = Flask(__name__)
print("Flask app object created.")

app.secret_key = "secret123"   # ✅ MUST ADD
# SQLite Database Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "eventdb.sqlite3")

UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 🔥 ADD THIS (IMPORTANT)
upload_path = os.path.join(app.root_path, UPLOAD_FOLDER)
if not os.path.exists(upload_path):
    os.makedirs(upload_path)
from datetime import datetime

def cleanup_events():
    db = get_db()
    cursor = db.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # delete old events
    cursor.execute("DELETE FROM events WHERE event_date < ?", (today,))
    
    # delete related attendance
    cursor.execute("""
        DELETE FROM attendance 
        WHERE event_id NOT IN (SELECT id FROM events)
    """)

    db.commit()


from datetime import timedelta

def cleanup_gallery():
    db = get_db()
    cursor = db.cursor()

    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # get old images
    cursor.execute("SELECT image FROM gallery WHERE created_at < ?", (cutoff,))
    old_images = cursor.fetchall()

    # delete files from folder
    for img in old_images:
        path = os.path.join(app.config['UPLOAD_FOLDER'], img['image'])
        if os.path.exists(path):
            os.remove(path)

    # delete from database
    cursor.execute("DELETE FROM gallery WHERE created_at < ?", (cutoff,))

    db.commit()
# Ensure the database file exists and has the required tables
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
            """
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                event_date TEXT,
                event_location TEXT,
                max_slots INTEGER,
                fee INTEGER,
                payment_enabled INTEGER,
                qr_code TEXT
            )
            """
        )
        

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                person_name TEXT,
                payment_ss TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                image TEXT,
                created_at TEXT
            )
            """
        )
        

        conn.commit()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


try:
    print("Initializing SQLite database...", DB_PATH)
    init_db()
    print("Database Initialized Successfully")
except Exception as e:
    import traceback
    print("Database Initialization Error:")
    traceback.print_exc()

@app.route("/")
def home():
    return redirect('/login')
@app.route('/login', methods=['GET'])
def login():
    session.pop('user', None)   # 🔥 THIS LINE FIXES IT
    return render_template('login.html')


@app.route('/login_user', methods=['POST'])
def login_user():
    username = request.form['username']
    password = request.form['password']

    print("Entered:", username, password)  # 👈 DEBUG

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users")
    print("All Users:", cursor.fetchall())  # 👈 DEBUG

    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()

    print("Matched User:", user)  # 👈 DEBUG

    if user:
        session['user'] = username
        return redirect('/dashboard')
    else:
        return "Login Failed"


@app.route('/register')
def register():
    return render_template("register.html")


@app.route('/register_user', methods=['POST'])
def register_user():

    username = request.form['username']
    password = request.form['password']

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        return "Username already exists. Please choose another."

    cursor.execute(
        "INSERT INTO users(username,password) VALUES(?,?)",
        (username, password)
    )

    db.commit()

    return redirect('/')


@app.route('/dashboard')
def dashboard():
    cleanup_events()  
    cleanup_gallery()  # ✅ auto cleanup
    if 'user' not in session:
        return redirect('/login')
    return render_template("dashboard.html",title="Core Connect")


@app.route('/create_event')
def create_event():
    return render_template("create_event.html")


@app.route('/add_event', methods=['POST'])
def add_event():

    # 🔹 Basic event details
    name = request.form['event_name']
    date = request.form['event_date']
    location = request.form['event_location']

    # 🔹 Slot selection
    max_slots = request.form['max_slots']

    # 🔹 Payment toggle
    payment_enabled = request.form['payment_enabled']

    # 🔹 Upload folder setup
    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    # 🔥 PAYMENT LOGIC
    if payment_enabled == "1":
        fee = request.form['fee']
        qr = request.files['qr_code']

        # safe filename
        qr_name = qr.filename if qr and qr.filename != "" else ""

        if qr_name:
            qr.save(os.path.join(upload_path, qr_name))
    else:
        fee = 0
        qr_name = ""

    # 🔹 Database insert
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    INSERT INTO events(event_name, event_date, event_location, max_slots, fee, payment_enabled, qr_code)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, date, location, max_slots, fee, payment_enabled, qr_name))

    db.commit()

    return redirect('/events')


@app.route('/events')
def events():

    db = get_db()
    cursor = db.cursor()

    query = """
    SELECT events.id, events.event_name, events.event_date, events.event_location,
    COUNT(attendance.id) as total_attendees
    FROM events
    LEFT JOIN attendance ON events.id = attendance.event_id
    GROUP BY events.id
    """

    cursor.execute(query)
    data = cursor.fetchall()

    return render_template("events.html", events=data)

@app.route('/attendance/<int:event_id>')
def attendance(event_id):

    db = get_db()
    cursor = db.cursor()

    # get event details
    cursor.execute("SELECT * FROM events WHERE id=?", (event_id,))
    event = cursor.fetchone()

    return render_template("attendance.html", event=event)


@app.route('/add_attendee', methods=['POST'])
def add_attendee():

    event_id = request.form['event_id']
    person = request.form['person_name']

    db = get_db()
    cursor = db.cursor()

    # 🔥 CHECK CURRENT COUNT
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE event_id=?", (event_id,))
    count = cursor.fetchone()[0]

    # 🔥 GET MAX SLOTS
    cursor.execute("SELECT max_slots FROM events WHERE id=?", (event_id,))
    max_slots = cursor.fetchone()[0]

    if max_slots != 0 and count >= max_slots:
        return "⚠️ Event Full!"

    # 🔥 HANDLE PAYMENT SCREENSHOT
    file = request.files.get('payment_ss')
    filename = ""

    if file and file.filename != "":
        upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])

        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        filename = file.filename
        file.save(os.path.join(upload_path, filename))

    # 🔥 INSERT
    cursor.execute("""
        INSERT INTO attendance(event_id, person_name, payment_ss)
        VALUES (?, ?, ?)
    """, (event_id, person, filename))

    db.commit()

    return redirect('/events')


@app.route('/gallery/<int:event_id>')
def gallery(event_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM gallery WHERE event_id=?", (event_id,))
    photos = cursor.fetchall()

    return render_template("gallery.html", photos=photos)


# FIX ADDED HERE
@app.route('/upload_photo/<int:event_id>')
def upload_photo_page(event_id):
    return render_template("upload_photo.html", event_id=event_id)


@app.route('/upload_photo', methods=['POST'])
def upload_photo():

    event_id = request.form['event_id']
    file = request.files['photo']

    filename = file.filename

    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])

    # ensure uploads folder exists
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    file.save(os.path.join(upload_path, filename))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
    "INSERT INTO gallery(event_id,image,created_at) VALUES(?,?,?)",
    (event_id, filename, datetime.now().strftime("%Y-%m-%d"))
    )
    db.commit()
    return redirect(f'/gallery/{event_id}')

@app.route('/view_attendance/<int:event_id>')
def view_attendance(event_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
    "SELECT person_name, payment_ss FROM attendance WHERE event_id=?",
    (event_id,)
    )
    attendees = cursor.fetchall()

    total = len(attendees)

    return render_template(
        "view_attendance.html",
        attendees=attendees,
        total=total
    )


@app.route('/attendance_list')
def attendance_list():

    db = get_db()
    cursor = db.cursor()

    query = """
    SELECT events.event_name, attendance.person_name
    FROM attendance
    JOIN events ON events.id = attendance.event_id
    """

    cursor.execute(query)
    data = cursor.fetchall()

    return render_template("attendance_list.html", data=data)


@app.route('/gallery_list')
def gallery_list():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM gallery")
    photos = cursor.fetchall()

    return render_template("gallery.html", photos=photos)


@app.route('/attendance_events')
def attendance_events():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    return render_template("attendance_events.html", events=events)


@app.route('/gallery_events')
def gallery_events():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    return render_template("gallery_events.html", events=events)



   
@app.route('/check_events/<date>')
def check_events(date):

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM events WHERE event_date=?",
        (date,)
    )

    count = cursor.fetchone()[0]

    return {"count": count}
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


if __name__ == "__main__":
    print("Flask Server Starting...")
    try:
        app.run(debug=True, use_reloader=False)
    except Exception as e:
        print("Flask failed to start:", e)
        raise