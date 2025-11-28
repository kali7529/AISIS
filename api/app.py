import os
import asyncio
import tempfile
import edge_tts
import speech_recognition as sr
from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS
import google.generativeai as genai

# ========================================
# CONFIGURATION
# ========================================
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("❌ ERROR: GEMINI_API_KEY is missing in Render settings!")

app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')
CORS(app)

chat_history = [] 

# ========================================
# HOME
# ========================================
@app.route("/")
def home():
    return render_template("index.html")

# ========================================
# CHAT ENDPOINT (DOCTOR MODE)
# ========================================
@app.route("/api/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "API Key missing"}), 500
        
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # Add User Message to History
    chat_history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })

    # Keep history short (last 10 turns)
    chat_history_trimmed = chat_history[-10:] 

    try:
        # UPDATED: We add a 'system_instruction' to force it to act like a Doctor
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction="""
            You are Dr. Nova, an expert AI Medical Consultant. 
            Your role is to provide detailed, comprehensive medical information.
            
            When a user describes symptoms, you must provide:
            1. **Potential Causes:** Explain what might be causing the issue strictly.
            2. **Medical Treatment:** List specific medications (generic names with standard dosages) and standard medical treatments.
            3. **Home Remedies:** Actionable advice for immediate relief.
            
            Tone: Professional, authoritative, and direct (like a senior doctor). 
            Do not be vague. Give maximum information possible.
            
            (Always end with a short standard disclaimer that you are an AI, but do not let it stop you from giving the advice).
            """
        )
        
        # Generate content
        response = model.generate_content(chat_history_trimmed)
        bot_reply = response.text

        # Add Bot Message to History
        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        print(f"AI Error: {e}")
        # Clean up history if it failed
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": str(e)}), 500

# ========================================
# TTS ENDPOINT
# ========================================
@app.route("/api/speak", methods=["POST"])
def speak():
    text = request.json.get("text", "")
    if not text:
        return jsonify({"error": "Empty text"}), 400

    voice = "en-US-AriaNeural"
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)

    async def tts_job():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)

    try:
        asyncio.run(tts_job())
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================
# VOICE ENDPOINT
# ========================================
@app.route("/api/voice", methods=["POST"])
def voice():
    if "audio" not in request.files:
        return jsonify({"error": "No audio found"}), 400

    file = request.files["audio"]
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    file.save(path)

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        return jsonify({"text": text})
    except sr.UnknownValueError:
        return jsonify({"text": ""})
    except sr.RequestError:
        return jsonify({"error": "Google Speech API error"}), 500
    finally:
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
