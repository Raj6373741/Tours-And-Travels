from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------- DATABASE CONNECTION -------------------
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

    # fetch all packages (or limit if you want)
    cursor.execute("SELECT * FROM tour_packages ORDER BY created_at DESC LIMIT 6")
    packages = cursor.fetchall()

    conn.close()

    return render_template("index.html", packages=packages)


@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/services")
def services():
    return render_template("services.html")

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
    if "user" not in session:
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
            (session["user"], booking_type, source, destination, travel_date)
        )
        conn.commit()
        conn.close()

        flash("Booking successful!", "success")
        return redirect(url_for("dashboard"))

    return render_template("book.html")

@app.route("/my_bookings")
def my_bookings():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bookings WHERE user_email=%s ORDER BY created_at DESC", (session["user"],))
    bookings = cursor.fetchall()
    conn.close()

    return render_template("my_bookings.html", bookings=bookings)

@app.route("/rent_car", methods=["GET", "POST"])
def rent_car():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        car_type = request.form["car_type"]
        pickup_location = request.form["pickup_location"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO car_rentals (user_email, car_type, pickup_location, start_date, end_date) VALUES (%s, %s, %s, %s, %s)",
            (session["user"], car_type, pickup_location, start_date, end_date)
        )
        conn.commit()
        conn.close()

        flash("Car rental booked successfully!", "success")
        return redirect(url_for("my_car_rentals"))

    return render_template("rent_car.html")

@app.route("/my_car_rentals")
def my_car_rentals():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM car_rentals WHERE user_email=%s ORDER BY created_at DESC", (session["user"],))
    rentals = cursor.fetchall()
    conn.close()

    return render_template("my_car_rentals.html", rentals=rentals)

@app.route("/packages")
def packages():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tour_packages")
    packages = cursor.fetchall()
    conn.close()
    return render_template("packages.html", packages=packages)

@app.route("/book_package/<int:package_id>", methods=["GET", "POST"])
def book_package(package_id):
    if "user" not in session:
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
            (session["user"], package_id, booking_date)
        )
        conn.commit()
        conn.close()

        flash("Package booked successfully!", "success")
        return redirect(url_for("my_packages"))

    conn.close()
    return render_template("book_package.html", package=package)

@app.route("/my_packages")
def my_packages():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT pb.id, tp.package_name, tp.category, tp.price, pb.booking_date, pb.created_at
        FROM package_bookings pb
        JOIN tour_packages tp ON pb.package_id = tp.id
        WHERE pb.user_email=%s ORDER BY pb.created_at DESC
    """, (session["user"],))
    my_bookings = cursor.fetchall()
    conn.close()

    return render_template("my_packages.html", my_bookings=my_bookings)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    user_email = session["user"]

    # Fetch user’s own bookings, rentals, packages
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
                           user=user_email,
                           bookings=user_bookings,
                           rentals=user_rentals,
                           packages=user_packages)

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

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admins (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_pw))
        conn.commit()
        conn.close()

        flash("Admin registered successfully!", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_register.html")


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
            session["user"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully!", "info")
    return redirect(url_for("home"))

# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(debug=True)
