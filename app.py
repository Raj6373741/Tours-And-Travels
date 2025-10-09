from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadData
import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 🔐 Email Config (use an app password, not your real Gmail password)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'raj6373741@gmail.com'     # Replace
app.config['MAIL_PASSWORD'] = 'dtzt eizf zkno dvrj'      # Replace
mail = Mail(app)

# Token Serializer for secure password reset links
s = URLSafeTimedSerializer(app.secret_key)

# Upload config
UPLOAD_FOLDER = os.path.join("static", "uploads", "cars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="raj",       
        password="1234",
        database="tours_travels"
    )
    return conn

# ------------------- ROUTES -------------------

@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tour_packages ORDER BY created_at DESC LIMIT 6")
    packages = cursor.fetchall()
    conn.close()
    return render_template("index.html", packages=packages)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)",
            (name, email, message)
        )
        conn.commit()
        conn.close()

        flash("Your message has been sent successfully!", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")

@app.route("/book", methods=["GET", "POST"])
def book():
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        booking_type = request.form["booking_type"]
        source = request.form["source"]
        destination = request.form["destination"]
        travel_date = request.form["travel_date"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bookings (user_email, booking_type, source, destination, travel_date) VALUES (%s, %s, %s, %s, %s)",
            (session["user_email"], booking_type, source, destination, travel_date)
        )
        conn.commit()
        conn.close()

        flash("Booking successful!", "success")
        return redirect(url_for("dashboard"))

    return render_template("book.html")

@app.route("/my_bookings")
def my_bookings():
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bookings WHERE user_email=%s ORDER BY created_at DESC", (session["user_email"],))
    bookings = cursor.fetchall()
    conn.close()

    return render_template("my_bookings.html", bookings=bookings)

@app.route("/rent_car", methods=["GET", "POST"])
def rent_car():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    pickup_location = request.args.get("pickup_location")
    if pickup_location:
        cursor.execute("SELECT * FROM cars WHERE pickup_location LIKE %s", (f"%{pickup_location}%",))
    else:
        cursor.execute("SELECT * FROM cars")
    cars = cursor.fetchall()
    conn.close()
    return render_template("rent_car.html", cars=cars)

@app.route("/my_car_rentals")
def my_car_rentals():
    if "user_email" not in session:
        flash("Please log in to view your rentals.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM car_rentals WHERE user_email = %s ORDER BY created_at DESC", (session["user_email"],))
    rentals = cursor.fetchall()
    conn.close()
    return render_template("my_car_rentals.html", rentals=rentals)

@app.route("/book_car/<int:car_id>", methods=["POST"])
def book_car(car_id):
    if "user_email" not in session:
        flash("Please log in to book a car.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, pickup_location FROM cars WHERE id = %s", (car_id,))
    car = cursor.fetchone()

    if not car:
        flash("❌ Car not found.", "danger")
        conn.close()
        return redirect(url_for("rent_car"))

    # Prevent file overwrite (optional)
    cursor.execute("""
        INSERT INTO car_rentals (user_email, car_id, car_type, pickup_location, start_date, end_date, created_at)
        VALUES (%s, %s, %s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 1 DAY), NOW())
    """, (session["user_email"], car_id, car["name"], car["pickup_location"]))
    conn.commit()
    conn.close()

    flash("✅ Car booked successfully!", "success")
    return redirect(url_for("my_car_rentals"))

@app.route("/luxury_cars")
def luxury_cars():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM cars
        WHERE car_type LIKE '%Luxury%' OR car_type LIKE '%Sports%' OR car_type LIKE '%Supercar%'
        ORDER BY price_per_day DESC
    """)
    cars = cursor.fetchall()
    conn.close()
    return render_template("rent_car.html", cars=cars)

@app.route("/packages")
def packages():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    search = request.args.get("search", "")
    region = request.args.get("region", "")
    category = request.args.get("category", "")
    sort = request.args.get("sort", "")

    query = """
        SELECT id, package_name, category, price, old_price, discount, image, duration,
               location, region, popular_attraction, accessibility,
               nearest_airport, nearest_railway, description
        FROM tour_packages
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (package_name LIKE %s OR popular_attraction LIKE %s OR description LIKE %s)"
        search_term = f"%{search}%"
        params += [search_term, search_term, search_term]

    if region:
        query += " AND region = %s"
        params.append(region)

    if category:
        query += " AND category = %s"
        params.append(category)

    if sort == "low_high":
        query += " ORDER BY price ASC"
    elif sort == "high_low":
        query += " ORDER BY price DESC"
    else:
        query += " ORDER BY id DESC"

    cursor.execute(query, tuple(params))
    packages = cursor.fetchall()
    conn.close()

    # Fetch unique regions and categories
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT region FROM tour_packages WHERE region IS NOT NULL AND region != ''")
    regions = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT category FROM tour_packages WHERE category IS NOT NULL AND category != ''")
    categories = [c[0] for c in cursor.fetchall()]
    conn.close()

    return render_template("packages.html",
                           packages=packages,
                           regions=regions,
                           categories=categories,
                           search=search,
                           selected_region=region,
                           selected_category=category,
                           selected_sort=sort)

@app.route("/book_package/<int:package_id>", methods=["GET", "POST"])
def book_package(package_id):
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tour_packages WHERE id=%s", (package_id,))
    package = cursor.fetchone()

    if request.method == "POST":
        booking_date = request.form["booking_date"]
        cursor.execute(
            "INSERT INTO package_bookings (user_email, package_id, booking_date) VALUES (%s, %s, %s)",
            (session["user_email"], package_id, booking_date)
        )
        conn.commit()
        conn.close()
        flash("Package booked successfully!", "success")
        return redirect(url_for("my_packages"))

    conn.close()
    return render_template("book_package.html", package=package)

@app.route("/my_packages")
def my_packages():
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT pb.id, tp.package_name, tp.category, tp.price, pb.booking_date, pb.created_at
        FROM package_bookings pb
        JOIN tour_packages tp ON pb.package_id = tp.id
        WHERE pb.user_email=%s ORDER BY pb.created_at DESC
    """, (session["user_email"],))
    my_bookings = cursor.fetchall()
    conn.close()
    return render_template("my_packages.html", my_bookings=my_bookings)

@app.route("/dashboard")
def dashboard():
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    user_email = session["user_email"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM bookings WHERE user_email=%s", (user_email,))
    user_bookings = cursor.fetchall()

    cursor.execute("SELECT * FROM car_rentals WHERE user_email=%s", (user_email,))
    user_rentals = cursor.fetchall()

    cursor.execute("""
        SELECT tp.package_name, pb.booking_date, pb.created_at
        FROM package_bookings pb
        JOIN tour_packages tp ON pb.package_id = tp.id
        WHERE pb.user_email=%s
    """, (user_email,))
    user_packages = cursor.fetchall()

    conn.close()
    return render_template("dashboard.html",
                           user=session["user_name"],
                           bookings=user_bookings,
                           rentals=user_rentals,
                           packages=user_packages)

# ------------------- Admin Routes -------------------

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        flash("Please login as admin first", "warning")
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, email FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM bookings")
    bookings = cursor.fetchall()

    cursor.execute("SELECT * FROM car_rentals")
    rentals = cursor.fetchall()

    cursor.execute("""
        SELECT pb.id, pb.user_email, tp.package_name, pb.booking_date, pb.created_at
        FROM package_bookings pb
        JOIN tour_packages tp ON pb.package_id = tp.id
    """)
    package_bookings = cursor.fetchall()

    cursor.execute("SELECT * FROM contact_messages")
    contacts = cursor.fetchall()

    conn.close()
    return render_template("admin_dashboard.html",
                           users=users,
                           bookings=bookings,
                           rentals=rentals,
                           package_bookings=package_bookings,
                           contacts=contacts)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = admin["email"]
            flash("Admin login successful!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out successfully!", "info")
    return redirect(url_for("admin_login"))

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
        existing_admin = cursor.fetchone()
        if existing_admin:
            flash("Admin with this email already exists!", "danger")
            conn.close()
            return redirect(url_for("admin_register"))

        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO admins (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_pw))
        conn.commit()
        conn.close()

        flash("Admin registered successfully!", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_register.html")

# ------------------- User Auth -------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already registered!", "danger")
            conn.close()
            return redirect(url_for("login"))

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_pw)
        )
        conn.commit()
        conn.close()

        flash("Registration successful!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_email"] = user["email"]
            session["user_name"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    session.pop("user_name", None)
    flash("Logged out successfully!", "info")
    return redirect(url_for("home"))

# ------------------- Admin Add Car -------------------

@app.route("/admin/add_car", methods=["GET", "POST"])
def add_car():
    if "admin" not in session:
        flash("Please log in as admin.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        name = request.form["name"]
        car_type = request.form["car_type"]
        seats = request.form["seats"]
        transmission = request.form["transmission"]
        ac_type = request.form["ac_type"]
        price_per_day = request.form["price_per_day"]
        pickup_location = request.form["pickup_location"]
        rating = request.form["rating"]

        image = request.files["image"]
        image_filename = None

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            # Prevent overwrite
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}_{filename}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_filename = f"uploads/cars/{filename}"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cars (name, car_type, seats, transmission, ac_type, price_per_day, pickup_location, rating, image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (name, car_type, seats, transmission, ac_type, price_per_day, pickup_location, rating, image_filename))
        conn.commit()
        conn.close()

        flash("✅ Car added successfully!", "success")
        return redirect(url_for("manage_cars"))

    return render_template("admin_add_car.html")

# ------------------- Password Reset -------------------

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset - TravelBuddy',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f'''Hi {user['name']},

We received a request to reset your password.

Click the link below to reset it:
{reset_link}

If you didn't request this, just ignore this email.

- TravelBuddy Team'''
            mail.send(msg)
            flash("📧 A password reset link has been sent to your email.", "info")
        else:
            flash("⚠️ Email not found in our records.", "danger")

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=600)
    except BadData:
        flash("⏰ The password reset link has expired or is invalid.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_password = request.form["password"]
        hashed = generate_password_hash(new_password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        conn.commit()
        conn.close()

        flash("✅ Your password has been reset successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(debug=True)
