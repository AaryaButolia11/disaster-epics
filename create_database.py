import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')


def create_database():
    """Create tables in Supabase (PostgreSQL) if they don't exist"""
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            port=DB_PORT,
            sslmode='require'          # Required for Supabase
        )

        cursor = connection.cursor()

        # Create subscribers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id SERIAL PRIMARY KEY,
                phone_number VARCHAR(20) UNIQUE NOT NULL,
                area VARCHAR(100),
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        print("✓ Table 'subscribers' created successfully!")

        # Create emergency_requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_requests (
                id SERIAL PRIMARY KEY,
                phone_number VARCHAR(20) NOT NULL,
                category VARCHAR(50) NOT NULL,
                area VARCHAR(100) NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pending'
            )
        """)
        print("✓ Table 'emergency_requests' created successfully!")

        # Create resource_requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resource_requests (
                id SERIAL PRIMARY KEY,
                resource_type VARCHAR(100) NOT NULL,
                quantity INT NOT NULL,
                area VARCHAR(100) NOT NULL,
                requester_phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pending'
            )
        """)
        print("✓ Table 'resource_requests' created successfully!")

        connection.commit()
        print("\n✓ Database setup completed successfully!")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == '__main__':
    print("Creating tables in Supabase...\n")
    create_database()