import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL found.")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE posts ADD COLUMN impressions FLOAT DEFAULT 0;"))
        print("Added impressions column.")
    except Exception as e:
        print(f"Error adding impressions: {e}")
        
    try:
        conn.execute(text("ALTER TABLE posts ADD COLUMN watch_time_hours FLOAT DEFAULT 0;"))
        print("Added watch_time_hours column.")
    except Exception as e:
        print(f"Error adding watch_time_hours: {e}")
    conn.commit()
    
print("Done.")
