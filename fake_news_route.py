"""
Add this to your app.py

1. Add GEMINI_API_KEY to your .env file:
   GEMINI_API_KEY=your_gemini_api_key_here

2. Add this import at the top of app.py:
   import google.generativeai as genai

3. Add this config after load_dotenv():
   GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
   genai.configure(api_key=GEMINI_API_KEY)

4. Copy the /check-news route below into app.py

5. Install the package:
   pip install google-generativeai
"""

import google.generativeai as genai
import os

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)


@app.route('/check-news', methods=['POST'])
def check_news():
    """Check if news is fake using Gemini AI"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        phone = data.get('phone', '')

        if not text:
            return jsonify({'error': 'News text is required'}), 400

        if len(text) < 10:
            return jsonify({'error': 'Text too short for analysis'}), 400

        # Build Gemini prompt
        prompt = f"""You are a fake news detection expert specializing in disaster-related news in India.

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
    "urgency_words": <count of words like BREAKING, URGENT, SHARE NOW>,
    "call_to_action": <count of share/forward/send requests>,
    "unverified_claims": <count of unverified absolute claims>,
    "sensational_numbers": <count of extreme unverified numbers>
  }},
  "warnings": ["list", "of", "specific", "red", "flags", "found"]
}}

Guidelines:
- fake_probability 0-30 = likely real (risk_level: low)
- fake_probability 31-60 = uncertain (risk_level: medium)  
- fake_probability 61-100 = likely fake (risk_level: high)
- Focus on disaster/emergency news patterns common in India
- Sensationalism, lack of sources, ALL CAPS, urgency tactics = higher fake probability"""

        # Call Gemini API
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up response (remove markdown code fences if present)
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()

        import json
        analysis = json.loads(response_text)

        # Optionally save to DB and send SMS
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

                    # SMS alert for high risk
                    if analysis.get('risk_level') == 'high':
                        sms_text = (f"SDRRAS Fact Check: ⚠️ The news you submitted has "
                                    f"{analysis.get('fake_probability')}% fake probability. "
                                    f"Please verify before sharing!")
                        send_sms(phone, sms_text)
            except Exception as db_err:
                print(f"DB/SMS error (non-fatal): {db_err}")

        return jsonify({
            'success': True,
            'analysis': analysis
        }), 200

    except json.JSONDecodeError as e:
        print(f"JSON parse error from Gemini: {e}")
        print(f"Raw response: {response_text}")
        return jsonify({'error': 'AI response parsing failed. Try again.'}), 500
    except Exception as e:
        print(f"Fake news check error: {e}")
        return jsonify({'error': 'Analysis failed. Please try again.'}), 500