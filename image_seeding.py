import csv
import mysql.connector

def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="raj",       
        password="1234",
        database="tours_travels"
    )
    return conn

def load_dataset_to_db():
    with open("india_travel_dataset.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        conn = get_db_connection()
        cursor = conn.cursor()
        for row in reader:
            # e.g. row has "place_name", "image_file", "description", "duration", "location"
            # check if exists in DB
            cursor.execute("SELECT id FROM tour_packages WHERE package_name=%s", (row["place_name"],))
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO tour_packages (package_name, category, price, description, image, duration, location) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (row["place_name"], row.get("category","Domestic"), row.get("price", 0.0),
                     row.get("description",""), row.get("image_file","default.jpg"),
                     row.get("duration",""), row.get("location",""))
                )
        conn.commit()
        conn.close()
