import os
import asyncio
import tempfile
import edge_tts
import speech_recognition as sr
from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# ========================================
# ENV VARS
# ========================================
load_dotenv("gemini.env")
API_KEY = os.getenv("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)

# ========================================
# APP INIT
# ========================================
app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')
CORS(app)

# Store history in Google's expected format
chat_history = [] 

# ========================================
# HOME (SERVE FRONTEND)
# ========================================
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

    # 1. Add User Message (GOOGLE FORMAT)
    # Role: 'user' | Content is inside 'parts' -> 'text'
    chat_history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })

    # Keep only last 10 turns to avoid hitting limits
    chat_history_trimmed = chat_history[-20:] 

    try:
        # 2. Generate Response using the history list
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(chat_history_trimmed)
        
        bot_reply = response.text

        # 3. Add Bot Message (GOOGLE FORMAT)
        # Role must be 'model' (not 'assistant')
        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        # If error, remove the last user message so we don't break the history
        if chat_history:
            chat_history.pop()
        print(f"Error: {e}")
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
# VOICE INPUT TO TEXT
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

# ========================================
# RUN LOCALLY
# ========================================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
