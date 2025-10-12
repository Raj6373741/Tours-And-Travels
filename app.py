from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadData
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
from io import BytesIO
import random
import re
import razorpay
from flask import Flask, render_template, request, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 🔐 Email Config (use an app password, not your real Gmail password)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'raj6373741@gmail.com'     # Replace
app.config['MAIL_PASSWORD'] = 'dtzt eizf zkno dvrj'      # Replace
mail = Mail(app)

# ✅ Razorpay setup
app.config['RAZORPAY_KEY_ID'] = 'rzp_test_RRWfulx7SidFou'
app.config['RAZORPAY_KEY_SECRET'] = 'NkX2fNWnrDnW4mKeaH2VGn3z'

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(
    app.config['RAZORPAY_KEY_ID'],
    app.config['RAZORPAY_KEY_SECRET']
))

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

        # ✅ Save to database (optional)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ DB insert error: {e}")

        # ✅ Send email to admin
        try:
            admin_email = "raj6373741@gmail.com"  # change to your admin email
            msg = Message(
                subject=f"📩 New Contact Message from {name}",
                sender=app.config['MAIL_USERNAME'],
                recipients=[admin_email]
            )
            msg.body = f"""
You’ve received a new message from the TravelBuddy Contact Form:

👤 Name: {name}
📧 Email: {email}
💬 Message:
{message}

Reply directly to this email to contact the sender.
"""
            mail.send(msg)
            flash("✅ Your message has been sent successfully! We'll get back to you soon.", "success")
        except Exception as e:
            print(f"❌ Mail error: {e}")
            flash("⚠️ Something went wrong while sending your message. Please try again.", "danger")

        return redirect(url_for("contact"))

    return render_template("contact.html")

@app.route("/create_order", methods=["POST"])
def create_order():
    data = request.get_json()
    amount = int(float(data.get("amount", 0)) * 100)  # Convert ₹ to paise

    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
    order = client.order.create(dict(amount=amount, currency="INR", payment_capture=1))

    return jsonify({
        "order_id": order["id"],
        "amount": amount,
        "key": app.config["RAZORPAY_KEY_ID"]
    })

@app.route("/book", methods=["GET", "POST"])
def book():
    if "user_email" not in session:
        flash("⚠️ Please login first", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        import requests, io, random, datetime, json
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        from flask_mail import Message

        # ---- Verify Razorpay payment ----
        razorpay_payment_id = request.form.get("razorpay_payment_id")
        razorpay_order_id = request.form.get("razorpay_order_id")
        razorpay_signature = request.form.get("razorpay_signature")

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            flash("❌ Payment verification failed. Please try again.", "danger")
            return redirect(url_for("book"))

        # Verify payment signature
        try:
            client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params)
        except Exception as e:
            print("❌ Payment signature verification failed:", e)
            flash("❌ Payment verification failed. Please try again.", "danger")
            return redirect(url_for("book"))

        # ---- Extract basic booking info ----
        booking_type = request.form.get("booking_type", "").strip().lower()
        travel_class = request.form.get("travel_class", "").strip().lower()
        source = request.form.get("source", "").strip().lower()
        destination = request.form.get("destination", "").strip().lower()
        travel_date = request.form.get("travel_date", "").strip()

        # Passengers: expected JSON array of dicts (from JS or hidden field)
        passengers_json = request.form.get("passengers")
        try:
            passengers = json.loads(passengers_json)
        except Exception:
            flash("❌ Invalid passenger data format.", "danger")
            return redirect(url_for("book"))

        # ---- Limit passenger count ----
        passenger_limit = 6 if booking_type in ["train", "bus"] else 9
        if len(passengers) == 0:
            flash("❌ Please add at least one passenger.", "danger")
            return redirect(url_for("book"))
        if len(passengers) > passenger_limit:
            flash(f"❌ You can only book up to {passenger_limit} passengers for {booking_type.title()}!", "danger")
            return redirect(url_for("book"))

        # ---- Static fare data ----
        fare_rates = {"flight": 10, "train": 1.5, "bus": 2.5}
        class_multipliers = {
            "economy": 1, "business": 2.5,
            "sleeper": 1, "3 ac": 1.5, "2 ac": 2, "1 ac": 3,
            "sleeper ac": 1.8, "sleeper non-ac": 1.2,
            "seater ac": 1.3, "seater non-ac": 1
        }

        distances = {
            "mumbai-pune": 150, "delhi-mumbai": 1400, "delhi-jaipur": 270,
            "bangalore-chennai": 350, "kolkata-delhi": 1500, "mumbai-goa": 590,
            "pune-nagpur": 700, "delhi-lucknow": 550, "bangalore-hyderabad": 570
        }

        # ---- Distance calculation ----
        route_key = f"{source}-{destination}"
        reverse_key = f"{destination}-{source}"
        distance = distances.get(route_key) or distances.get(reverse_key) or 500  # default fallback

        # Try dynamic API distance
        try:
            geo_url_src = f"https://nominatim.openstreetmap.org/search?format=json&limit=1&q={requests.utils.requote_uri(source)}"
            geo_url_dest = f"https://nominatim.openstreetmap.org/search?format=json&limit=1&q={requests.utils.requote_uri(destination)}"
            src_data = requests.get(geo_url_src, headers={"User-Agent": "travelbuddy-app"}, timeout=8).json()
            dest_data = requests.get(geo_url_dest, headers={"User-Agent": "travelbuddy-app"}, timeout=8).json()
            if src_data and dest_data:
                src_lat, src_lon = src_data[0]["lat"], src_data[0]["lon"]
                dest_lat, dest_lon = dest_data[0]["lat"], dest_data[0]["lon"]
                osrm_url = f"https://router.project-osrm.org/route/v1/driving/{src_lon},{src_lat};{dest_lon},{dest_lat}?overview=false"
                osrm_resp = requests.get(osrm_url, timeout=8).json()
                if osrm_resp.get("routes"):
                    distance = round(osrm_resp["routes"][0]["distance"] / 1000)
        except Exception as e:
            print("⚠️ Distance API Error:", e)

        base_rate = fare_rates.get(booking_type, 2.5)
        multiplier = class_multipliers.get(travel_class, 1.0)
        ticket_price = round(distance * base_rate * multiplier)

        total_price = ticket_price * len(passengers)

        # ---- Save bookings in DB ----
        conn = get_db_connection()
        cursor = conn.cursor()

        # One booking entry per passenger
        for psg in passengers:
            cursor.execute("""
                INSERT INTO bookings 
                (user_email, booking_type, travel_class, source, destination, travel_date, traveller_name, age, gender, phone, email, price, payment_id, order_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            """, (
                session["user_email"], booking_type, travel_class,
                source.title(), destination.title(), travel_date,
                psg["name"], psg["age"], psg["gender"], psg["phone"], psg["email"],
                ticket_price, razorpay_payment_id, razorpay_order_id
            ))

        conn.commit()
        conn.close()

        ticket_number = f"TB-{booking_type[:3].upper()}-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000,9999)}"

        # ---- Generate single PDF for all passengers ----
        pdf_buffer = io.BytesIO()
        p = canvas.Canvas(pdf_buffer, pagesize=letter)
        p.setTitle(f"{booking_type.title()} Ticket Confirmation")

        try:
            logo = ImageReader("static/images/logo.png")
            p.drawImage(logo, 60, 720, width=100, height=60)
        except:
            pass

        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(300, 750, f"{booking_type.title()} Ticket Confirmation")

        p.setFont("Helvetica", 12)
        y = 700
        p.drawString(80, y, f"Ticket Number: {ticket_number}")
        y -= 20
        p.drawString(80, y, f"From: {source.title()}  →  To: {destination.title()}")
        y -= 20
        p.drawString(80, y, f"Travel Date: {travel_date}")
        y -= 20
        p.drawString(80, y, f"Distance: {distance} km")
        y -= 30
        p.drawString(80, y, "Passengers:")
        y -= 20

        for i, psg in enumerate(passengers, start=1):
            p.drawString(100, y, f"{i}. {psg['name']} ({psg['age']} yrs, {psg['gender']}) - {psg['phone']}")
            y -= 15
            if y < 100:
                p.showPage()
                y = 750
                p.setFont("Helvetica", 12)

        y -= 20
        p.drawString(80, y, f"Price per Ticket: ₹{ticket_price}")
        y -= 20
        p.drawString(80, y, f"Total Price: ₹{total_price}")
        y -= 20
        p.drawString(80, y, f"Payment ID: {razorpay_payment_id}")

        p.setFont("Helvetica-Oblique", 11)
        p.drawCentredString(300, y - 30, "Thank you for choosing TravelBuddy!")
        p.setFont("Helvetica", 8)
        p.drawCentredString(300, 40, "© 2025 TravelBuddy. All rights reserved.")
        p.save()
        pdf_buffer.seek(0)

        # ---- Send Email ----
        try:
            msg = Message(
                subject=f"🎟️ {booking_type.title()} Ticket Confirmation - TravelBuddy",
                sender=app.config["MAIL_USERNAME"],
                recipients=[passengers[0]["email"]]
            )
            msg.body = f"""
Hello {passengers[0]['name']},

✅ Your {booking_type.title()} booking for {len(passengers)} passenger(s) is confirmed!

📋 Route: {source.title()} → {destination.title()}
🗓️ Date: {travel_date}
💰 Total Fare: ₹{total_price}
🔗 Payment ID: {razorpay_payment_id}

See attached PDF for ticket details.
"""
            msg.attach(f"{booking_type}_Ticket.pdf", "application/pdf", pdf_buffer.getvalue())
            mail.send(msg)
            flash("✅ Ticket booked successfully! Confirmation email sent.", "success")
        except Exception as e:
            print("❌ Email Error:", e)
            flash("✅ Ticket booked but email sending failed.", "warning")

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

@app.route("/create_car_order", methods=["POST"])
def create_car_order():
    data = request.get_json()
    amount = int(float(data.get("amount", 0)) * 100)  # Convert ₹ to paise

    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
    order = client.order.create(dict(amount=amount, currency="INR", payment_capture=1))

    return jsonify({
        "order_id": order["id"],
        "amount": amount,
        "key": app.config["RAZORPAY_KEY_ID"]
    })

@app.route("/book_car", methods=["POST"])
def book_car():
    if "user_email" not in session:
        flash("⚠️ Please log in to book a car.", "warning")
        return redirect(url_for("login"))

    # ---- Verify Razorpay payment ----
    razorpay_payment_id = request.form.get("razorpay_payment_id")
    razorpay_order_id = request.form.get("razorpay_order_id")
    razorpay_signature = request.form.get("razorpay_signature")

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        flash("❌ Payment verification failed. Please try again.", "danger")
        return redirect(url_for("rent_car"))

    # Verify payment signature
    try:
        client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
        params = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        client.utility.verify_payment_signature(params)
    except Exception as e:
        print("❌ Payment signature verification failed:", e)
        flash("❌ Payment verification failed. Please try again.", "danger")
        return redirect(url_for("rent_car"))

    # Extract form data
    user_email = session["user_email"]
    user_name = request.form.get("user_name", "").strip()
    user_phone = request.form.get("user_phone", "").strip()
    license_no = request.form.get("license_no", "").strip()
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    car_id = request.form.get("car_id")

    # Validation
    if not (user_name and user_phone and license_no and start_date and end_date and car_id):
        flash("❌ All fields are required!", "danger")
        return redirect(url_for("rent_car"))

    if not user_phone.startswith("+91") or len(user_phone) != 13:
        flash("📱 Invalid mobile number. Must start with +91 and have 10 digits after it.", "danger")
        return redirect(url_for("rent_car"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if car exists
    cursor.execute("SELECT name, pickup_location, price_per_day FROM cars WHERE id = %s", (car_id,))
    car = cursor.fetchone()
    if not car:
        flash("❌ Car not found!", "danger")
        conn.close()
        return redirect(url_for("rent_car"))

    # Insert booking record
    cursor.execute("""
    INSERT INTO car_rentals (
        user_email, user_name, user_phone, license_no,
        car_id, car_type, pickup_location, start_date, end_date,
        payment_id, order_id, signature, created_at
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
""", (
    user_email, user_name, user_phone, license_no,
    car_id, car["name"], car["pickup_location"], start_date, end_date,
    razorpay_payment_id, razorpay_order_id, razorpay_signature
))

    conn.commit()
    conn.close()

    # 🧾 Generate PDF confirmation (your existing PDF code remains the same)
    pdf_buffer = io.BytesIO()
    p = canvas.Canvas(pdf_buffer, pagesize=letter)
    p.setTitle("Car Rental Booking Confirmation")

    # Logo at top
    logo_path = "static/images/logo.png"  # ✅ Ensure this path is correct
    try:
        logo = ImageReader(logo_path)
        p.drawImage(logo, 60, 720, width=100, height=60)
    except Exception as e:
        print(f"⚠️ Logo not loaded: {e}")

    # Title
    p.setFont("Helvetica-Bold", 18)
    p.drawString(180, 750, "Car Rental Confirmation")

    # Booking Details
    p.setFont("Helvetica", 12)
    y = 680
    lines = [
        f"Name: {user_name}",
        f"Email: {user_email}",
        f"Phone: {user_phone}",
        f"License No: {license_no}",
        f"Car Booked: {car['name']}",
        f"Pickup Location: {car['pickup_location']}",
        f"Start Date: {start_date}",
        f"End Date: {end_date}",
        f"Price per day: Rs.{car['price_per_day']}",
        f"Payment ID: {razorpay_payment_id}",
    ]
    for line in lines:
        p.drawString(100, y, line)
        y -= 20

    p.setFont("Helvetica-Oblique", 11)
    p.drawString(100, y - 20, "Thank you for choosing TravelBuddy!")

    # Copyright footer
    p.setFont("Helvetica", 8)
    p.drawCentredString(300, 40, "© 2025 TravelBuddy. All rights reserved.")

    p.save()
    pdf_buffer.seek(0)

    # 📧 Send email with PDF (your existing email code remains the same)
    try:
        msg = Message(
            subject="🚗 Your Car Rental Booking Confirmation - TravelBuddy",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user_email]
        )
        msg.body = f"""
Hello {user_name},

Your car rental booking has been successfully confirmed!

📋 Booking Details:
Car: {car['name']}
Pickup Location: {car['pickup_location']}
Start Date: {start_date}
End Date: {end_date}
Payment ID: {razorpay_payment_id}

Please find your booking confirmation PDF attached.

Thank you for choosing TravelBuddy!
"""

        # attach the PDF
        msg.attach("Car_Booking_Confirmation.pdf", "application/pdf", pdf_buffer.getvalue())
        mail.send(msg)
        flash("✅ Car booked and confirmation email sent successfully!", "success")

    except Exception as e:
        print(f"❌ Email Error: {e}")
        flash("Car booked, but confirmation email could not be sent.", "warning")

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

@app.route("/create_package_order", methods=["POST"])
def create_package_order():
    data = request.get_json()
    amount = int(float(data.get("amount", 0)) * 100)  # Convert ₹ to paise

    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
    order = client.order.create(dict(amount=amount, currency="INR", payment_capture=1))

    return jsonify({
        "order_id": order["id"],
        "amount": amount,
        "key": app.config["RAZORPAY_KEY_ID"]
    })

@app.route("/book_package/<int:package_id>", methods=["GET", "POST"])
def book_package(package_id):
    if "user_email" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch package details
    cursor.execute("SELECT * FROM tour_packages WHERE id=%s", (package_id,))
    package = cursor.fetchone()

    if not package:
        flash("Package not found!", "danger")
        conn.close()
        return redirect(url_for("packages"))

    if request.method == "POST":
        # ---- Verify Razorpay payment ----
        razorpay_payment_id = request.form.get("razorpay_payment_id")
        razorpay_order_id = request.form.get("razorpay_order_id")
        razorpay_signature = request.form.get("razorpay_signature")

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            flash("❌ Payment verification failed. Please try again.", "danger")
            return redirect(url_for("book_package", package_id=package_id))

        # Verify payment signature
        try:
            client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params)
        except Exception as e:
            print("❌ Payment signature verification failed:", e)
            flash("❌ Payment verification failed. Please try again.", "danger")
            return redirect(url_for("book_package", package_id=package_id))

        booking_date = request.form["booking_date"]
        group_size = int(request.form["group_size"])

        # Collect traveler info
        travelers = []
        for i in range(1, group_size + 1):
            name = request.form.get(f"traveler_name_{i}")
            age = request.form.get(f"traveler_age_{i}")
            phone = request.form.get(f"traveler_phone_{i}")
            travelers.append({"name": name, "age": age, "phone": phone})

        # Calculate total cost
        total_cost = group_size * package["price"]

        # Insert booking record with payment details
        cursor.execute("""
            INSERT INTO package_bookings 
            (user_email, package_id, booking_date, group_size, total_amount, payment_id, order_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session["user_email"], package_id, booking_date, group_size, total_cost, 
              razorpay_payment_id, razorpay_order_id))
        conn.commit()

        booking_id = cursor.lastrowid
        conn.close()

        # ✅ Generate PDF with logo (your existing PDF generation code remains the same)
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        width, height = letter
        y = height - 50

        # --- Add Logo ---
        logo_path = os.path.join("static", "images", "logo.png")
        if os.path.exists(logo_path):
            c.drawImage(logo_path, width/2 - 50, y - 60, width=100, height=60, preserveAspectRatio=True)
        y -= 100

        # --- Title ---
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, y, "Package Booking Confirmation")
        y -= 40

        # --- Booking Details ---
        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Booking ID: {booking_id}")
        y -= 20
        c.drawString(50, y, f"User Email: {session['user_email']}")
        y -= 20
        c.drawString(50, y, f"Booking Date: {booking_date}")
        y -= 20
        c.drawString(50, y, f"Payment ID: {razorpay_payment_id}")
        y -= 30

        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, f"Package: {package['package_name']}")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Category: {package['category']}")
        y -= 20
        c.drawString(50, y, f"Locations Covered: {package['locations_covered']}")
        y -= 30

        # --- Traveler Details ---
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, "Traveler Details:")
        y -= 20
        c.setFont("Helvetica", 12)

        for i, t in enumerate(travelers, start=1):
            c.drawString(60, y, f"{i}. {t['name']} (Age: {t['age']})  Phone: {t['phone'] or 'N/A'}")
            y -= 20

        y -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"Total Travelers: {group_size}")
        y -= 20
        c.drawString(50, y, f"Total Cost: Rs.{total_cost:,.2f}")

        # --- Thank You Note ---
        y -= 40
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(width / 2, y, "Thank you for choosing TravelBuddy!")

        # --- COPYRIGHT FOOTER ---
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)  # Soft gray text
        c.drawCentredString(width / 2, 40, "© 2025 TravelBuddy. All rights reserved.")
        c.setFillColorRGB(0, 0, 0)  # Reset color back to black

        c.showPage()
        c.save()
        pdf_buffer.seek(0)

        # ✅ Send email with PDF attachment (your existing email code remains the same)
        try:
            msg = Message(
                subject=f"Booking Confirmed - {package['package_name']}",
                sender=app.config['MAIL_USERNAME'],
                recipients=[session["user_email"]],
            )
            msg.body = (
                f"Hello,\n\nYour booking for '{package['package_name']}' has been confirmed!\n"
                f"Booking ID: {booking_id}\n"
                f"Start Date: {booking_date}\n"
                f"Total Travelers: {group_size}\n"
                f"Total Amount: ₹{total_cost:,.2f}\n"
                f"Payment ID: {razorpay_payment_id}\n\n"
                f"Please find the attached PDF confirmation.\n\n"
                f"Thank you for booking with TravelBuddy!\n✈️"
            )
            msg.attach("Package_Booking_Confirmation.pdf", "application/pdf", pdf_buffer.read())
            mail.send(msg)
            flash("✅ Package booked successfully! Confirmation email sent.", "success")
        except Exception as e:
            flash(f"Booking successful, but failed to send email: {str(e)}", "warning")

        return redirect(url_for("my_packages"))

    conn.close()
    return render_template("book_package.html", package=package, today=datetime.datetime.now().strftime('%Y-%m-%d'))

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

# 💬 Chatbot API Route
@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_message = request.json.get("message", "").strip().lower()

    if "chat_history" not in session:
        session["chat_history"] = {"context": None}

    context = session["chat_history"]["context"]
    response = ""

    if not user_message:
        return jsonify({"response": "Please type something to start chatting."})

    # --- Tour Packages Data ---
    packages = {
        "taj mahal": {
            "location": "Agra, Uttar Pradesh",
            "price": "₹9,999",
            "duration": "2 Days / 1 Night",
            "description": "Explore the magnificent Taj Mahal and nearby Agra Fort with guided tours and hotel stay.",
            "attraction": "Taj Mahal, Agra Fort, Mehtab Bagh"
        },
        "goa": {
            "location": "Goa, India",
            "price": "₹14,999",
            "duration": "4 Days / 3 Nights",
            "description": "Experience the beaches, nightlife, and Portuguese heritage of Goa with this all-inclusive tour.",
            "attraction": "Baga Beach, Fort Aguada, Basilica of Bom Jesus"
        },
        "jaipur": {
            "location": "Jaipur, Rajasthan",
            "price": "₹11,499",
            "duration": "3 Days / 2 Nights",
            "description": "Discover the Pink City’s palaces, forts, and markets in a royal getaway package.",
            "attraction": "Amber Fort, City Palace, Hawa Mahal"
        }
    }

    # --- Detect Intent ---
    if any(greet in user_message for greet in ["hi", "hello", "hey"]):
        response = "👋 Hello! I'm TravelBuddy. Would you like to book a flight, train, bus, car, or see our tour packages?"
        session["chat_history"]["context"] = "greeting"

    elif "package" in user_message or "tour" in user_message or "trip" in user_message:
        # Try to detect which package user is asking for
        found_pkg = None
        for name in packages.keys():
            if name in user_message:
                found_pkg = name
                break

        if found_pkg:
            pkg = packages[found_pkg]
            response = (
                f"🌍 **{found_pkg.title()} Package Details**\n"
                f"📍 Location: {pkg['location']}\n"
                f"📅 Duration: {pkg['duration']}\n"
                f"💰 Price: {pkg['price']}\n"
                f"🏖️ Attractions: {pkg['attraction']}\n"
                f"ℹ️ {pkg['description']}\n\n"
                f"Would you like to book this package?"
            )
            session["chat_history"]["context"] = f"booking_{found_pkg}_package"

        else:
            response = (
                "Here are our popular tour packages 🌎:\n"
                "1️⃣ Taj Mahal (Agra)\n"
                "2️⃣ Goa Beaches Tour\n"
                "3️⃣ Jaipur Heritage Trip\n\n"
                "Type a destination name to know more (e.g., 'Goa package')."
            )
            session["chat_history"]["context"] = "showing_packages"

    elif "book" in user_message and "package" in user_message:
        for name in packages.keys():
            if name in user_message:
                response = f"🎉 Great choice! Let’s start booking your **{name.title()}** package. Please provide your travel date and number of travelers."
                session["chat_history"]["context"] = f"booking_{name}_package"
                break
        else:
            response = "Please tell me which package you’d like to book — Taj Mahal, Goa, or Jaipur."

    elif "flight" in user_message:
        response = "✈️ Great! Where would you like to fly from?"
        session["chat_history"]["context"] = "booking_flight_source"

    elif context == "booking_flight_source":
        session["chat_history"]["flight_source"] = user_message.title()
        session["chat_history"]["context"] = "booking_flight_destination"
        response = f"Got it. Flying from {user_message.title()}. What's your destination?"

    elif context == "booking_flight_destination":
        session["chat_history"]["flight_destination"] = user_message.title()
        source = session["chat_history"].get("flight_source")
        dest = user_message.title()
        session["chat_history"]["context"] = None
        response = f"Perfect! ✈️ We'll search flights from {source} to {dest}. You can also visit the 'Book Flight' page to continue."

    elif "train" in user_message:
        response = "🚆 Sure! Please tell me your starting station."
        session["chat_history"]["context"] = "booking_train_source"

    elif context == "booking_train_source":
        session["chat_history"]["train_source"] = user_message.title()
        session["chat_history"]["context"] = "booking_train_destination"
        response = f"Nice. Traveling from {user_message.title()}. What's your destination station?"

    elif context == "booking_train_destination":
        session["chat_history"]["train_destination"] = user_message.title()
        source = session["chat_history"].get("train_source")
        dest = user_message.title()
        session["chat_history"]["context"] = None
        response = f"Awesome! 🚆 I’ll look for trains from {source} to {dest}. You can also use the 'Book Train' page."

    elif "bus" in user_message:
        response = "🚌 Sure! Where are you boarding from?"
        session["chat_history"]["context"] = "booking_bus_source"

    elif context == "booking_bus_source":
        session["chat_history"]["bus_source"] = user_message.title()
        session["chat_history"]["context"] = "booking_bus_destination"
        response = f"Okay, boarding from {user_message.title()}. What's your destination?"

    elif context == "booking_bus_destination":
        session["chat_history"]["bus_destination"] = user_message.title()
        source = session["chat_history"].get("bus_source")
        dest = user_message.title()
        session["chat_history"]["context"] = None
        response = f"Got it! 🚌 Searching buses from {source} to {dest}. You can also check the 'Book Bus' page."

    elif "car" in user_message:
        response = "🚗 Sure! From which city do you want to rent the car?"
        session["chat_history"]["context"] = "booking_car_city"

    elif context == "booking_car_city":
        session["chat_history"]["car_city"] = user_message.title()
        session["chat_history"]["context"] = None
        response = f"Perfect! 🚗 Cars are available in {user_message.title()}. Visit 'Rent a Car' to continue."

    elif "thank" in user_message:
        response = "You're very welcome! 😊 Anything else I can help with?"

    elif "help" in user_message:
        response = "I can assist with booking flights, trains, buses, cars, or tour packages. What would you like to do?"
        session["chat_history"]["context"] = None

    else:
        response = (
            "I'm your TravelBuddy assistant 🤖. Try saying:\n"
            "- 'Show packages'\n"
            "- 'Book flight from Mumbai to Delhi'\n"
            "- 'Tell me about Goa trip'"
        )

    # Save the updated session
    session.modified = True

    return jsonify({"response": response})
@app.route("/payment_success", methods=["POST"])
def payment_success():
    data = request.get_json()

    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"]
        })
        # ✅ Payment verified → proceed to confirm booking, generate PDF, send email
        return jsonify({"status": "success"})
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "failed"})




# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(debug=True)


