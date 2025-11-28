import os
import asyncio
import tempfile
import edge_tts
import speech_recognition as sr
from pydub import AudioSegment
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.middleware.proxy_fix import ProxyFix

# ========================================
# ENV VARS
# ========================================
load_dotenv("gemini.env")
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise Exception("❌ GEMINI_API_KEY not loaded — fix gemini.env")

genai.configure(api_key=API_KEY)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)

chat_history = []
current_tts_task = None

# ========================================
# TEXT CHAT ENDPOINT
# ========================================
@app.post("/api/chat")
def chat():
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    chat_history.append({"role": "user", "content": user_msg})

    response = genai.GenerativeModel("gemini-pro").generate_content(chat_history[-10:])

    bot_reply = response.text
    chat_history.append({"role": "assistant", "content": bot_reply})

    return jsonify({"response": bot_reply})


# ========================================
# TTS ENDPOINT
# ========================================
@app.post("/api/speak")
async def speak():
    global current_tts_task

    text = request.json.get("text", "")
    if not text:
        return jsonify({"error": "Empty text"}), 400

    voice = "en-US-AriaNeural"

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    output_file = temp.name

    async def tts_job():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

    current_tts_task = asyncio.create_task(tts_job())
    await current_tts_task

    return send_file(output_file, as_attachment=True)


# ========================================
# STOP SPEECH
# ========================================
@app.post("/api/stop")
def stop():
    global current_tts_task
    if current_tts_task and not current_tts_task.done():
        current_tts_task.cancel()
        return jsonify({"status": "speech stopped"})
    return jsonify({"status": "no speech running"})


# ========================================
# VOICE INPUT TO TEXT
# ========================================
@app.post("/api/voice")
def voice():
    if "audio" not in request.files:
        return jsonify({"error": "No audio found"}), 400

    file = request.files["audio"]
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    file.save(temp.name)

    recognizer = sr.Recognizer()
    with sr.AudioFile(temp.name) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio)
        return jsonify({"text": text})
    except:
        return jsonify({"text": ""})

@app.get("/")
def home():
    return jsonify({"status": "API online"})


# REQUIRED: serverless entry
def handler(event, context):
    return app(event, context)
