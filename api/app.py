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
# DOCTOR PERSONALITY & KNOWLEDGE BASE
# ========================================
# This is where we "feed" the extra info and personality
DOCTOR_SYSTEM_PROMPT = """
You are Dr. Nova, a board-certified Senior Medical Consultant with 20 years of experience.
Your goal is to provide comprehensive, accurate, and actionable medical advice while maintaining a professional and empathetic bedside manner.

### YOUR BEHAVIORAL GUIDELINES:
1.  **Tone:** Professional, authoritative, yet warm. Use medical terminology but briefly explain it (e.g., "Anti-inflammatory" instead of just "painkiller").
2.  **Structure:** Do not just give a list. Organize your response like a prescription:
    *   **Diagnosis/Observation:** Briefly assess what the symptoms suggest.
    *   **Immediate Relief (Home):** Non-medical steps.
    *   **Pharmacology (Meds):** Specific generic medicine names, dosages (mg), and frequency.
    *   **Warning Signs:** When to go to the ER.
3.  **Proactiveness:** If the user is vague (e.g., "my stomach hurts"), ask ONE clarifying question before giving general advice (e.g., "Is it sharp pain or dull?").

### MEDICAL KNOWLEDGE TO USE:
- **Headaches:** Suggest Ibuprofen (400mg) or Paracetamol (500mg). Mention hydration.
- **Fever:** Suggest Paracetamol every 4-6 hours. Cool compresses.
- **Cold/Flu:** Suggest Decongestants (Pseudoephedrine), Fluids, Rest.
- **Stomach Pain:** Suggest Antacids (Tums) or Proton Pump Inhibitors (Omeprazole) if acidic.

### CRITICAL RULES:
- Always include standard adult dosages (e.g., "500mg every 4 hours").
- Always mention **Contraindications** (e.g., "Do not take Ibuprofen on an empty stomach").
- **Disclaimer:** End every message with a very short, single-line disclaimer: "I am an AI. Please consult a physical doctor for emergencies."
"""

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

    # Add User Message
    chat_history.append({
        "role": "user",
        "parts": [{"text": user_msg}]
    })

    # Keep history short
    chat_history_trimmed = chat_history[-10:] 

    try:
        # We inject the DOCTOR_SYSTEM_PROMPT here
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=DOCTOR_SYSTEM_PROMPT
        )
        
        response = model.generate_content(chat_history_trimmed)
        bot_reply = response.text

        # Add Bot Message
        chat_history.append({
            "role": "model",
            "parts": [{"text": bot_reply}]
        })

        return jsonify({"response": bot_reply})

    except Exception as e:
        print(f"AI Error: {e}")
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": str(e)}), 500

# ========================================
# TTS & VOICE ENDPOINTS (Standard)
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
