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
# We get the key directly from Render's Environment settings
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("❌ ERROR: GEMINI_API_KEY is missing! Add it in Render Environment settings.")

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
# CHAT ROUTE
# ========================================
@app.route("/api/chat", methods=["POST"])
def chat():
    # 1. Check for API Key
    if not API_KEY:
        return jsonify({"error": "Server missing API Key. Check Render Settings."}), 500
        
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # 2. Add User Message
    chat_history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })

    # Keep history short to prevent errors
    chat_history_trimmed = chat_history[-10:] 

    try:
        # 3. Generate Response
        # We use 'gemini-pro' because it is the most stable model
        model = genai.GenerativeModel("gemini-pro")
        
        response = model.generate_content(chat_history_trimmed)
        bot_reply = response.text

        # 4. Add Bot Message
        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        print(f"Generative AI Error: {e}")
        # Clean up history if it failed
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": f"AI Error: {str(e)}"}), 500

# ========================================
# TTS ROUTE
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
# VOICE ROUTE
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
