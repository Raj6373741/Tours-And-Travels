import csv
import os
import random
from werkzeug.utils import secure_filename
from app import get_db_connection  # ✅ use your existing DB connection function

# Path to your dataset file (make sure it exists)
DATASET_FILE = "datasets/Expanded_Indian_Travel_Dataset.csv"

# Folder where images are stored (place at least 3–5 placeholder images for now)
IMG_DIR = "static/img/packages/"


def load_expanded_dataset():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Read the CSV dataset
    with open(DATASET_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row.get("Destination Name")
            state = row.get("State")
            region = row.get("Region")
            category = row.get("Category")
            attraction = row.get("Popular Attraction")
            accessibility = row.get("Accessibility")
            airport = row.get("Nearest Airport")
            railway = row.get("Nearest Railway Station")

            # Skip empty records
            if not name:
                continue

            # Random duration & pricing for realism
            duration = random.choice([
                "3 Days / 2 Nights",
                "4 Days / 3 Nights",
                "5 Days / 4 Nights",
                "7 Days / 6 Nights"
            ])
            price = random.randint(6000, 45000)
            old_price = price + random.randint(1000, 8000)
            discount = int(((old_price - price) / old_price) * 100)

            # Pick a random image (placeholder for now)
            image_files = os.listdir(IMG_DIR) if os.path.exists(IMG_DIR) else []
            image = secure_filename(random.choice(image_files)) if image_files else "default.jpg"

            # Avoid duplicates
            cursor.execute("SELECT id FROM tour_packages WHERE package_name=%s", (name,))
            if cursor.fetchone():
                continue

            # Construct description using dataset info
            description = (
                f"Explore {name} in {state}, a {category.lower()} destination in {region} India. "
                f"Don't miss its popular attraction: {attraction}. "
                f"Accessibility: {accessibility}. "
                f"Nearest Airport: {airport}. "
                f"Nearest Railway Station: {railway}."
            )

            # Insert record into table
            cursor.execute("""
                INSERT INTO tour_packages 
                (package_name, category, price, description, image, duration, location,
                 region, popular_attraction, accessibility, nearest_airport, nearest_railway, old_price, discount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name,
                category or region or "Domestic",
                price,
                description,
                image,
                duration,
                state,
                region,
                attraction,
                accessibility,
                airport,
                railway,
                old_price,
                discount
            ))

    conn.commit()
    conn.close()
    print("✅ Successfully loaded Expanded Indian Travel Dataset into MySQL!")


if __name__ == "__main__":
    load_expanded_dataset()
