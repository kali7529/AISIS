import os
import asyncio
import tempfile
import edge_tts
import speech_recognition as sr
# ADDED: render_template
from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# ========================================
# ENV VARS
# ========================================
load_dotenv("gemini.env")
API_KEY = os.getenv("GEMINI_API_KEY")

# Optional: Safety check so app doesn't crash if env var is missing during build
if API_KEY:
    genai.configure(api_key=API_KEY)

# ========================================
# APP INIT
# ========================================
# CHANGED: Added template_folder and static_folder paths
# ".." means "go up one level" from the api folder
app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')
CORS(app)

chat_history = []

# ========================================
# HOME (SERVE FRONTEND)
# ========================================
# CHANGED: Now serves the HTML file instead of JSON
@app.route("/")
def home():
    return render_template("index.html")

# ========================================
# TEXT CHAT ENDPOINT
# ========================================
@app.route("/api/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "API Key missing on server"}), 500
        
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    chat_history.append({"role": "user", "content": user_msg})
    chat_history_trimmed = chat_history[-10:]

    try:
        response = genai.GenerativeModel("gemini-pro").generate_content(chat_history_trimmed)
        bot_reply = response.text
        chat_history.append({"role": "assistant", "content": bot_reply})
        chat_history[:] = chat_history[-50:]
        return jsonify({"response": bot_reply})
    except Exception as e:
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
    # Create temp file
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd) # Close file descriptor immediately

    async def tts_job():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)

    try:
        asyncio.run(tts_job())
        # Note: Sending file and deleting it immediately is tricky in Flask.
        # This setup works for small files usually.
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================
# VOICE INPUT TO TEXT
# ========================================
@app.route("/api/voice", methods=["POST"])
def voice():
    if "audio" not in request.files:
        return jsonify({"error": "No audio found"}), 400

    file = request.files["audio"]
    # Create temp file
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
        # cleanup
        if os.path.exists(path):
            os.remove(path)

# ========================================
# RUN LOCALLY
# ========================================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
