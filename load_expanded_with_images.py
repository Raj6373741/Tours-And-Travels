import csv
import os
import random
import requests
from urllib.parse import quote
from werkzeug.utils import secure_filename
from app import get_db_connection

# === Configuration ===
DATASET_FILE = "datasets/Expanded_Indian_Travel_Dataset.csv"
IMG_DIR = "static/img/packages/"
UNSPLASH_ACCESS_KEY = "YOUR_UNSPLASH_ACCESS_KEY"  # 🔑 replace with your Unsplash key


def get_unsplash_image(query):
    """Fetch a photo URL from Unsplash for a given destination name."""
    try:
        url = f"https://api.unsplash.com/search/photos?page=1&query={quote(query)}&client_id={UNSPLASH_ACCESS_KEY}"
        res = requests.get(url, timeout=10).json()
        if res.get("results"):
            return res["results"][0]["urls"]["regular"]
    except Exception as e:
        print(f"❌ Error fetching Unsplash image for {query}: {e}")
    return None


def download_image(url, dest_path):
    """Download image from Unsplash URL if not already downloaded."""
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(res.content)
            return True
    except Exception as e:
        print(f"❌ Download error for {url}: {e}")
    return False


def load_packages_with_images():
    conn = get_db_connection()
    cursor = conn.cursor()

    os.makedirs(IMG_DIR, exist_ok=True)

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

            if not name:
                continue

            # Skip if already exists in DB
            cursor.execute("SELECT id FROM tour_packages WHERE package_name=%s", (name,))
            if cursor.fetchone():
                print(f"⚠️ Skipping existing destination: {name}")
                continue

            # Generate random values for missing fields
            duration = random.choice([
                "3 Days / 2 Nights",
                "4 Days / 3 Nights",
                "5 Days / 4 Nights",
                "7 Days / 6 Nights"
            ])
            price = random.randint(6000, 45000)
            old_price = price + random.randint(1000, 8000)
            discount = int(((old_price - price) / old_price) * 100)

            # Image handling
            filename = secure_filename(f"{name.lower().replace(' ', '_')}.jpg")
            img_path = os.path.join(IMG_DIR, filename)

            # Skip downloading if file already exists
            if os.path.exists(img_path):
                print(f"🖼️ Image already exists: {filename}")
            else:
                img_url = get_unsplash_image(f"{name} India")
                if img_url:
                    success = download_image(img_url, img_path)
                    if success:
                        print(f"✅ Downloaded image for {name}")
                    else:
                        filename = "default.jpg"
                else:
                    filename = "default.jpg"
                    print(f"⚠️ No image found for {name}, using default")

            # Create a detailed description
            description = (
                f"Discover {name} in {state}, a {category.lower()} destination located in {region} India. "
                f"Popular attraction: {attraction}. Accessibility: {accessibility}. "
                f"Nearest Airport: {airport}, Nearest Railway: {railway}."
            )

            # Insert record
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
                filename,
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
    print("\n🎉 Finished importing all destinations safely!")
    print("No duplicates or repeated downloads 🚀")


if __name__ == "__main__":
    load_packages_with_images()
