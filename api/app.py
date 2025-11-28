import os
import asyncio
import tempfile
import edge_tts
import speech_recognition as sr
from quart import Quart, jsonify, request, send_file
from quart_cors import cors
from dotenv import load_dotenv
import google.generativeai as genai

# ========================================
# ENV VARS
# ========================================
load_dotenv("gemini.env")
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise Exception("❌ GEMINI_API_KEY not loaded — fix gemini.env")

genai.configure(api_key=API_KEY)

# ========================================
# APP INIT
# ========================================
app = Quart(__name__)
app = cors(app, allow_origin="*")  # CORS

chat_history = []
current_tts_task = None
current_output_file = None

# ========================================
# TEXT CHAT ENDPOINT
# ========================================
@app.route("/api/chat", methods=["POST"])
async def chat():
    user_msg = (await request.get_json()).get("message", "")
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    chat_history.append({"role": "user", "content": user_msg})
    chat_history_trimmed = chat_history[-10:]  # only last 10 messages

    response = genai.GenerativeModel("gemini-pro").generate_content(chat_history_trimmed)
    bot_reply = response.text
    chat_history.append({"role": "assistant", "content": bot_reply})

    # Optional: trim chat_history to last 50
    chat_history[:] = chat_history[-50:]

    return jsonify({"response": bot_reply})

# ========================================
# TTS ENDPOINT
# ========================================
@app.route("/api/speak", methods=["POST"])
async def speak():
    global current_tts_task, current_output_file

    data = await request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Empty text"}), 400

    voice = "en-US-AriaNeural"
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    current_output_file = temp.name

    async def tts_job():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(current_output_file)

    current_tts_task = asyncio.create_task(tts_job())
    try:
        await current_tts_task
    except asyncio.CancelledError:
        return jsonify({"status": "speech cancelled"}), 200

    response = await send_file(current_output_file, as_attachment=True)
    os.remove(current_output_file)
    current_output_file = None
    current_tts_task = None
    return response

# ========================================
# STOP SPEECH
# ========================================
@app.route("/api/stop", methods=["POST"])
async def stop():
    global current_tts_task, current_output_file
    if current_tts_task and not current_tts_task.done():
        current_tts_task.cancel()
        if current_output_file and os.path.exists(current_output_file):
            os.remove(current_output_file)
        current_tts_task = None
        current_output_file = None
        return jsonify({"status": "speech stopped"})
    return jsonify({"status": "no speech running"})

# ========================================
# VOICE INPUT TO TEXT
# ========================================
@app.route("/api/voice", methods=["POST"])
async def voice():
    if "audio" not in (await request.files):
        return jsonify({"error": "No audio found"}), 400

    file = (await request.files)["audio"]
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    file.save(temp.name)

    recognizer = sr.Recognizer()
    with sr.AudioFile(temp.name) as source:
        audio = recognizer.record(source)

    os.remove(temp.name)  # cleanup

    try:
        text = recognizer.recognize_google(audio)
        return jsonify({"text": text})
    except sr.UnknownValueError:
        return jsonify({"text": ""})
    except sr.RequestError:
        return jsonify({"error": "Google Speech API error"}), 500

# ========================================
# HOME
# ========================================
@app.route("/", methods=["GET"])
async def home():
    return jsonify({"status": "API online"})

# ========================================
# SERVER ENTRY (for AWS Lambda / Vercel)
# ========================================
def handler(event, context):
    # Requires: pip install serverless-asgi
    from serverless_asgi import handle_request
    return handle_request(app, event, context)

# ========================================
# RUN LOCALLY
# ========================================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
