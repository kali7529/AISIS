// static/app.js
// Use relative path so it works on Localhost AND Render automatically
const API_PREFIX = "/api"; 

const chatWindow = document.getElementById('chatWindow');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const waveVisualizer = document.getElementById('waveVisualizer');

let isRecording = false;
let mediaRecorder;
let audioChunks = [];
let speakingAudio = null; 

// Scroll helper
function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// ---------------------------------------------------------
// UI MESSAGE RENDERER (With Animation)
// ---------------------------------------------------------
function addMessage(text, sender) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = sender === 'bot'
        ? '<span class="material-symbols-rounded">medical_services</span>'
        : '🧑';

    const content = document.createElement('div');
    content.className = 'content';

    // Append elements to DOM first (so we can animate into them)
    messageEl.appendChild(avatar);
    messageEl.appendChild(content);
    chatWindow.appendChild(messageEl);

    // LOGIC: Typewriter for Bot, Instant for User
    if (sender === 'bot') {
        // 1. Parse Markdown to HTML
        let htmlContent = typeof marked !== 'undefined' ? marked.parse(text) : text;
        
        // 2. Add Medicine Highlights (if MedicineDB is loaded)
        if (typeof MedicineDB !== 'undefined') {
            htmlContent = MedicineDB.highlightMedicines(htmlContent);
        }

        // 3. Start Typewriter Effect
        content.classList.add('typing-cursor'); // Add blinking cursor
        typeWriterEffect(content, htmlContent);
        
    } else {
        // User message appears instantly
        content.innerText = text;
        scrollToBottom();
    }
}

// ---------------------------------------------------------
// TYPEWRITER ANIMATION LOGIC
// ---------------------------------------------------------
function typeWriterEffect(element, htmlString) {
    // 1. Split HTML into tokens (tags vs text) to prevent breaking HTML
    const tokens = htmlString.split(/(<[^>]+>)/g);
    
    let tokenIndex = 0;
    let charIndex = 0;
    let currentToken = "";

    // CONFIGURATION: Speed in milliseconds (Lower = Faster)
    // 10ms is a good "high speed" feel
    const TYPING_SPEED = 10; 

    function type() {
        // Stop if done
        if (tokenIndex >= tokens.length) {
            element.classList.remove('typing-cursor'); // Remove cursor
            scrollToBottom();
            return;
        }

        currentToken = tokens[tokenIndex];

        // CASE A: HTML Tag (e.g., <b>, <span class="...">) -> Append Instantly
        if (currentToken.startsWith('<') && currentToken.endsWith('>')) {
            element.innerHTML += currentToken;
            tokenIndex++;
            type(); // Recurse immediately (no delay)
        } 
        // CASE B: Plain Text -> Type char by char
        else {
            if (charIndex < currentToken.length) {
                element.innerHTML += currentToken.charAt(charIndex);
                charIndex++;
                scrollToBottom(); // Auto-scroll while typing
                setTimeout(type, TYPING_SPEED);
            } else {
                // Done with this string, move to next token
                charIndex = 0;
                tokenIndex++;
                type();
            }
        }
    }

    // Start typing
    type();
}

// ---------------------------------------------------------
// AUDIO LOGIC
// ---------------------------------------------------------

// STOP speech before playing new one
async function stopSpeech() {
    if (speakingAudio) {
        speakingAudio.pause();
        speakingAudio.currentTime = 0;
    }
}

// Text-to-Speech
async function speakText(text) {
    try {
        const response = await fetch(`${API_PREFIX}/speak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) return;

        const blob = await response.blob();
        const audioURL = URL.createObjectURL(blob);

        speakingAudio = new Audio(audioURL);
        speakingAudio.play();
        speakingAudio.onended = () => URL.revokeObjectURL(audioURL);

    } catch (err) {
        console.error("TTS Error:", err);
    }
}

// ---------------------------------------------------------
// MAIN MESSAGING LOGIC
// ---------------------------------------------------------
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Show User Message
    addMessage(text, 'user');
    userInput.value = '';

    await stopSpeech(); 

    try {
        // 2. Send to Backend
        const response = await fetch(`${API_PREFIX}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        // 3. Handle Response
        if (data.response) {
            addMessage(data.response, 'bot');
            speakText(data.response);
        } else if (data.error) {
            addMessage(`⚠️ Error: ${data.error}`, 'bot');
        } else {
            addMessage("⚠️ Server returned no response.", 'bot');
        }

    } catch (err) {
        console.error(err);
        addMessage("❌ Cannot reach server.", 'bot');
    }
}

// ---------------------------------------------------------
// VOICE INPUT LOGIC
// ---------------------------------------------------------
async function toggleRecording() {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await processVoice(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;

            micBtn.classList.add('active');
            waveVisualizer.classList.remove('hidden');

        } catch {
            alert("❌ Microphone permission blocked.");
        }

    } else {
        if(mediaRecorder) mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('active');
        waveVisualizer.classList.add('hidden');

        if(mediaRecorder && mediaRecorder.stream) {
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }
}

async function processVoice(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob);

    try {
        const response = await fetch(`${API_PREFIX}/voice`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.text) {
            userInput.value = data.text;
            sendMessage(); // Auto send after speaking
        }

    } catch (err) {
        console.error("STT Error:", err);
    }
}

// EVENT LISTENERS
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', e => e.key === 'Enter' && sendMessage());
micBtn.addEventListener('click', toggleRecording);
