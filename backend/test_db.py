from dotenv import load_dotenv
load_dotenv()
import os
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL")
print("LOADED DB URL:", DATABASE_URL)

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("✅ Database connected successfully!")
    except Exception as e:
        print("❌ Database connection failed:", e)
else:
    print("❌ DATABASE_URL not found in .env")
