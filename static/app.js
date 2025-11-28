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

// UI message renderer
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

    // Parse Markdown if available, otherwise plain text
    if (sender === 'bot' && typeof marked !== 'undefined') {
        content.innerHTML = marked.parse(text);
    } else {
        content.innerText = text;
    }

    messageEl.appendChild(avatar);
    messageEl.appendChild(content);
    chatWindow.appendChild(messageEl);

    scrollToBottom();
}

// STOP speech before playing new one
async function stopSpeech() {
    if (speakingAudio) {
        speakingAudio.pause();
        speakingAudio.currentTime = 0;
    }
}

// Main Send Message Function
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Show User Message
    addMessage(text, 'user');
    userInput.value = '';

    await stopSpeech(); 

    try {
        // 2. Send to Backend
        // Fixed: sending to /api/chat
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
        addMessage("❌ Cannot reach server. Is the backend running?", 'bot');
    }
}

// Text-to-Speech
async function speakText(text) {
    try {
        // Fixed: sending to /api/speak
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

// Voice mode
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

// Speech-to-text processing
async function processVoice(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob);

    try {
        // Fixed: sending to /api/voice
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
