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

chat_history = [] 

# ========================================
# DEBUG ROUTE (CHECK AVAILABLE MODELS)
# ========================================
@app.route("/api/check", methods=["GET"])
def check_models():
    try:
        if not API_KEY:
            return jsonify({"error": "No API Key set"})
        
        # List all models available to your API key
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
                
        return jsonify({
            "status": "Online", 
            "library_version": genai.__version__,
            "available_models": available_models
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# ========================================
# HOME
# ========================================
@app.route("/")
def home():
    return render_template("index.html")

# ========================================
# TEXT CHAT
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

    chat_history_trimmed = chat_history[-20:] 

    try:
        # We use the standard flash model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        response = model.generate_content(chat_history_trimmed)
        bot_reply = response.text

        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        # If 404 persists, the client can use the /api/check route to find the real name
        print(f"Error: {e}")
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": str(e)}), 500

# ========================================
# TTS
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
# VOICE
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
