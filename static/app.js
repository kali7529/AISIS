const BASE_URL = "https://aisis.onrender.com"; // YOUR BACKEND URL

const chatWindow = document.getElementById('chatWindow');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const waveVisualizer = document.getElementById('waveVisualizer');

let isRecording = false;
let mediaRecorder;
let audioChunks = [];

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

// Send text message
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    userInput.value = '';

    try {
        const response = await fetch(`${BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        if (data.response) {
            addMessage(data.response, 'bot');
            speakText(data.response);
        } else {
            addMessage("⚠️ Error from server.", 'bot');
        }

    } catch (err) {
        console.error(err);
        addMessage("❌ Server unreachable.", 'bot');
    }
}

// Text-to-Speech
async function speakText(text) {
    try {
        const response = await fetch(`${BASE_URL}/speak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) return;

        const blob = await response.blob();
        const audioURL = URL.createObjectURL(blob);

        const audio = new Audio(audioURL);
        audio.play();
        audio.onended = () => URL.revokeObjectURL(audioURL);

    } catch (err) {
        console.error("TTS Error:", err);
    }
}

// Voice input
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
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('active');
        waveVisualizer.classList.add('hidden');

        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
}

// Send voice -> backend speech-to-text
async function processVoice(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob);

    try {
        const response = await fetch(`${BASE_URL}/voice`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.text) {
            userInput.value = data.text;
            sendMessage();
        }

    } catch (err) {
        console.error("STT Error:", err);
    }
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', e => e.key === 'Enter' && sendMessage());
micBtn.addEventListener('click', toggleRecording);
