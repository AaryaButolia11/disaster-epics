from flask import Flask, render_template, request, jsonify
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from twilio.rest import Client
import json
from groq import Groq

# Load environment variables
load_dotenv()

groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Database Configuration (Supabase / PostgreSQL)
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def create_db_connection():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            port=DB_PORT,
            sslmode='require'
        )
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


def init_database():
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(20) UNIQUE NOT NULL,
                    area VARCHAR(100),
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fake_news_reports (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(20),
                    news_text TEXT,
                    risk_level VARCHAR(20),
                    fake_probability INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            connection.commit()
            print("Database tables initialized successfully")
        except Exception as e:
            print(f"Error initializing database: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()


def send_sms(phone_number, message):
    try:
        if not phone_number.startswith('+'):
            phone_number = '+91' + phone_number.lstrip('0')

        message_response = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        print(f"SMS sent successfully. SID: {message_response.sid}")
        return True
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False


@app.route('/')
def index():
    return render_template('index2.html')


@app.route('/cyclone')
def cyclone():
    return render_template('cyclone.html')


@app.route('/fake-news-checker')
def fake_news_checker():
    return render_template('fake-news-checker.html')


@app.route('/check-news', methods=['POST'])
def check_news():
    """Check if news is fake using Groq AI"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        phone = data.get('phone', '')

        if not text:
            return jsonify({'error': 'News text is required'}), 400

        if len(text) < 10:
            return jsonify({'error': 'Text too short for analysis'}), 400

        prompt = f"""You are an aggressive fake news detection expert for disaster news in India.

Analyze the following news text and respond ONLY with a valid JSON object — no markdown, no explanation, no extra text.

News text to analyze:
\"\"\"{text}\"\"\"

Return this exact JSON structure:
{{
  "credibility": "High / Medium / Low",
  "risk_level": "low / medium / high",
  "fake_probability": <integer 0-100>,
  "verdict": "One sentence verdict about this news",
  "explanation": "2-3 sentence explanation of your analysis",
  "indicators": {{
    "excessive_caps": <count of ALL-CAPS words>,
    "excessive_exclamation": <count of ! marks>,
    "urgency_words": <count of words like BREAKING URGENT SHARE NOW>,
    "call_to_action": <count of share/forward/send requests>,
    "unverified_claims": <count of unverified absolute claims>,
    "sensational_numbers": <count of extreme unverified numbers>
  }},
  "warnings": ["list", "of", "specific", "red", "flags", "found"]
}}

BE STRICT. Apply these rules:
- No source cited + extreme claim = fake_probability minimum 80
- Vague location + no official confirmation = fake_probability minimum 75
- "Flood in Bhopal" type claims with no source = fake_probability 85+ (Bhopal is inland, not flood-prone)
- Social media style writing with no evidence = fake_probability 70+
- fake_probability 0-30 = likely real (risk_level: low) — only for news with named sources, official statements
- fake_probability 31-60 = uncertain (risk_level: medium) — some details but unverified
- fake_probability 61-100 = likely fake (risk_level: high) — no sources, implausible, sensational
- When in doubt, rate HIGHER not lower
- Geography matters: flag claims about disasters in locations where that disaster is historically unlikely"""

        # Call Groq API
        response = groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1
        )
        response_text = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if response_text.startswith('```'):
            parts = response_text.split('```')
            response_text = parts[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()

        analysis = json.loads(response_text)

        # Save to DB and optionally send SMS
        if phone:
            try:
                connection = create_db_connection()
                if connection:
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT INTO fake_news_reports (phone_number, news_text, risk_level, fake_probability)
                        VALUES (%s, %s, %s, %s)
                    """, (phone, text[:500], analysis.get('risk_level'), analysis.get('fake_probability')))
                    connection.commit()
                    cursor.close()
                    connection.close()

                    if analysis.get('risk_level') == 'high':
                        sms_text = (f"SDRRAS Fact Check: The news you submitted has "
                                    f"{analysis.get('fake_probability')}% fake probability. "
                                    f"Please verify before sharing!")
                        send_sms(phone, sms_text)
            except Exception as db_err:
                print(f"DB/SMS error (non-fatal): {db_err}")

        return jsonify({'success': True, 'analysis': analysis}), 200

    except json.JSONDecodeError as e:
        print(f"JSON parse error from Groq: {e}")
        return jsonify({'error': 'AI response parsing failed. Try again.'}), 500
    except Exception as e:
        print(f"Fake news check error: {e}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@app.route('/subscribe', methods=['POST'])
def subscribe():
    connection = None
    try:
        data = request.get_json()
        phone_number = data.get('phone')
        area = data.get('area', 'Not specified')

        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400

        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("SELECT id FROM subscribers WHERE phone_number = %s", (phone_number,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE subscribers SET is_active = TRUE, area = %s WHERE phone_number = %s",
                (area, phone_number)
            )
            message = "Your subscription has been reactivated!"
        else:
            cursor.execute(
                "INSERT INTO subscribers (phone_number, area) VALUES (%s, %s)",
                (phone_number, area)
            )
            message = "Successfully subscribed for disaster alerts!"

        connection.commit()
        sms_message = f"SDRRAS Alert: {message} You will receive updates for {area} area."
        send_sms(phone_number, sms_message)

        return jsonify({'success': True, 'message': message}), 200

    except Exception as e:
        print(f"Database error: {e}")
        if connection:
            connection.rollback()
        return jsonify({'error': 'Failed to subscribe'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route('/emergency-request', methods=['POST'])
def emergency_request():
    connection = None
    try:
        data = request.get_json()
        phone_number = data.get('phone')
        category = data.get('category')
        area = data.get('area')
        message = data.get('message', '')

        if not all([phone_number, category, area]):
            return jsonify({'error': 'Missing required fields'}), 400

        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO emergency_requests (phone_number, category, area, message)
            VALUES (%s, %s, %s, %s)
        """, (phone_number, category, area, message))
        connection.commit()

        category_emojis = {'sos': '🆘', 'medical': '🏥', 'shelter': '🏠', 'food': '🍲'}
        emoji = category_emojis.get(category, '⚠️')
        sms_text = f"SDRRAS Emergency: {emoji} Your {category.upper()} request for {area} has been registered. Help is on the way!"
        send_sms(phone_number, sms_text)

        return jsonify({'success': True, 'message': 'Emergency request submitted successfully'}), 200

    except Exception as e:
        print(f"Database error: {e}")
        if connection:
            connection.rollback()
        return jsonify({'error': 'Failed to submit request'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route('/resource-request', methods=['POST'])
def resource_request():
    connection = None
    try:
        data = request.get_json()
        resource_type = data.get('resource')
        quantity = data.get('quantity')
        area = data.get('area')
        phone = data.get('phone')

        if not all([resource_type, quantity, area]):
            return jsonify({'error': 'Missing required fields'}), 400

        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO resource_requests (resource_type, quantity, area, requester_phone)
            VALUES (%s, %s, %s, %s)
        """, (resource_type, quantity, area, phone))
        connection.commit()

        if phone:
            sms_text = f"SDRRAS: Your request for {quantity}x {resource_type} in {area} has been submitted. We'll process it soon!"
            send_sms(phone, sms_text)

        return jsonify({'success': True, 'message': 'Resource request submitted successfully'}), 200

    except Exception as e:
        print(f"Database error: {e}")
        if connection:
            connection.rollback()
        return jsonify({'error': 'Failed to submit request'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route('/get-all-requests', methods=['GET'])
def get_all_requests():
    connection = None
    try:
        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, resource_type, quantity, area, requester_phone,
                   TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at, status
            FROM resource_requests
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        requests = cursor.fetchall()

        return jsonify({'success': True, 'requests': [dict(r) for r in requests]}), 200

    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Failed to fetch requests'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route('/fulfill-request', methods=['POST'])
def fulfill_request():
    connection = None
    try:
        data = request.get_json()
        request_id = data.get('request_id')

        if not request_id:
            return jsonify({'error': 'Request ID is required'}), 400

        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT resource_type, quantity, area, requester_phone
            FROM resource_requests WHERE id = %s
        """, (request_id,))
        request_details = cursor.fetchone()

        if not request_details:
            return jsonify({'error': 'Request not found'}), 404

        cursor.execute("UPDATE resource_requests SET status = 'fulfilled' WHERE id = %s", (request_id,))
        connection.commit()

        if request_details['requester_phone']:
            sms_text = (f"SDRRAS: Great news! Your request for {request_details['quantity']}x "
                        f"{request_details['resource_type']} in {request_details['area']} "
                        f"has been fulfilled and is on its way!")
            send_sms(request_details['requester_phone'], sms_text)

        return jsonify({'success': True, 'message': 'Request marked as fulfilled'}), 200

    except Exception as e:
        print(f"Database error: {e}")
        if connection:
            connection.rollback()
        return jsonify({'error': 'Failed to fulfill request'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route('/broadcast-alert', methods=['POST'])
def broadcast_alert():
    connection = None
    try:
        data = request.get_json()
        alert_message = data.get('message')
        target_area = data.get('area', None)

        if not alert_message:
            return jsonify({'error': 'Message is required'}), 400

        connection = create_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()
        if target_area:
            cursor.execute(
                "SELECT phone_number FROM subscribers WHERE is_active = TRUE AND area = %s",
                (target_area,)
            )
        else:
            cursor.execute("SELECT phone_number FROM subscribers WHERE is_active = TRUE")

        subscribers = cursor.fetchall()
        success_count = 0
        for (phone,) in subscribers:
            if send_sms(phone, f"SDRRAS ALERT: {alert_message}"):
                success_count += 1

        return jsonify({'success': True, 'message': f'Alert sent to {success_count} subscribers'}), 200

    except Exception as e:
        print(f"Error: {e}")
        if connection:
            connection.rollback()
        return jsonify({'error': 'Failed to broadcast alert'}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5000)