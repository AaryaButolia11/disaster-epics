"""
Test script for Fake News Detection functionality
Run this after starting the Flask app to test the API
"""

import requests
import json
import time


BASE_URL = "http://localhost:5000"


def test_fake_news_detection():
    """Test the fake news detection endpoint"""

    print("=" * 60)
    print("FAKE NEWS DETECTION TEST")
    print("=" * 60)

    test_cases = [
        {
            "name": "Likely Fake News",
            "text": "BREAKING!!! Government HIDING true death toll!!! THOUSANDS DEAD!!! Share IMMEDIATELY before they delete this!!! 100% CONFIRMED SECRET CONSPIRACY!!!",
        },
        {
            "name": "Likely Real News",
            "text": "Cyclone Dana makes landfall in Odisha coast with wind speeds of 120 kmph. NDRF teams have been deployed for rescue operations. State government has opened 150 relief camps.",
        },
        {
            "name": "Uncertain News",
            "text": "BREAKING: Heavy rainfall expected in coastal areas. Authorities advise people to stay alert and follow safety guidelines. Share with family and friends.",
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"Test Case {i}: {test_case['name']}")
        print(f"{'=' * 60}")
        print(f"Text: {test_case['text']}")
        print()

        try:
            response = requests.post(
                f"{BASE_URL}/check-news",
                json={"text": test_case['text']},
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()

                if result.get('success'):
                    analysis = result['analysis']

                    print(f"✓ Analysis Results:")
                    print(f"  Verdict      : {analysis.get('verdict', 'N/A')}")
                    print(f"  Credibility  : {analysis.get('credibility', 'N/A')}")
                    print(f"  Risk Level   : {analysis.get('risk_level', 'N/A').upper()}")
                    print(f"  Fake Prob.   : {analysis.get('fake_probability', 'N/A')}%")
                    print(f"  Explanation  : {analysis.get('explanation', 'N/A')}")

                    indicators = analysis.get('indicators', {})
                    if any(v > 0 for v in indicators.values()):
                        print(f"\n  Indicators Detected:")
                        for indicator, count in indicators.items():
                            if count > 0:
                                print(f"    - {indicator}: {count}")

                    warnings = analysis.get('warnings', [])
                    if warnings:
                        print(f"\n  Warnings:")
                        for warning in warnings:
                            print(f"    ⚠ {warning}")
                else:
                    print(f"✗ Error: {result.get('error', 'Unknown error')}")
            else:
                print(f"✗ HTTP Error: {response.status_code}")
                print(f"  Response: {response.text}")

        except requests.exceptions.ConnectionError:
            print("✗ Error: Cannot connect to Flask app")
            print("  Make sure the app is running on http://localhost:5000")
            break
        except Exception as e:
            print(f"✗ Error: {str(e)}")

    print(f"\n{'=' * 60}")
    print("Test Complete!")
    print(f"{'=' * 60}\n")


def test_database_connection():
    """Test if Supabase connection works"""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION TEST (Supabase/PostgreSQL)")
    print("=" * 60)

    try:
        import psycopg2
        from dotenv import load_dotenv
        import os

        load_dotenv()

        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            dbname=os.getenv('DB_NAME', 'postgres'),
            port=os.getenv('DB_PORT', '5432'),
            sslmode='require'
        )

        cursor = connection.cursor()

        # List tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()

        print("✓ Connected to Supabase!")
        print("\nTables found:")
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name} ({count} records)")

        cursor.close()
        connection.close()
        print("\n✓ Database test passed!")

    except Exception as e:
        print(f"✗ Database error: {str(e)}")
        print("\nMake sure:")
        print("  1. .env is configured with Supabase credentials")
        print("  2. You've run create_database.py")


if __name__ == "__main__":
    print("\n")
    print("🚀 SDRRAS Fake News Detection - Test Suite")
    print("=" * 60)

    test_database_connection()

    print("\nStarting API tests in 3 seconds...")
    print("(Make sure Flask app is running on http://localhost:5000)")
    time.sleep(3)

    test_fake_news_detection()

    print("\n📊 View results at: http://localhost:5000/fake-news-checker")