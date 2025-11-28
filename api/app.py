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
    
    # --- DEBUG: PRINT AVAILABLE MODELS TO LOGS ---
    try:
        print("\n=== GOOGLE API CONNECTED ===")
        print("🔍 Checking available models...")
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # Store strictly the name (e.g., models/gemini-1.5-flash)
                available_models.append(m.name.replace("models/", ""))
                print(f"   ✅ {m.name}")
        print("==============================\n")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
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
# CHAT ENDPOINT
# ========================================
@app.route("/api/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "API Key missing"}), 500
        
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    chat_history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })

    # Keep history short
    chat_history_trimmed = chat_history[-15:] 

    try:
        # USE THIS EXACT MODEL NAME
        # If this fails, check the logs for the list of '✅' models
        model = genai.GenerativeModel("gemini-1.0-nano")
        
        response = model.generate_content(chat_history_trimmed)
        bot_reply = response.text

        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        print(f"AI Error: {e}")
        # Remove failed user message to prevent history corruption
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": str(e)}), 500

# ========================================
# TTS & VOICE
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
