// static/app.js

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

// ---------------------------------------------------------
// HELPER FUNCTIONS
// ---------------------------------------------------------

function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// ANIMATION: Show "Thinking" Bubbles
function showLoading() {
    const loaderDiv = document.createElement('div');
    loaderDiv.id = 'loading-indicator';
    loaderDiv.className = 'message bot';
    loaderDiv.innerHTML = `
        <div class="avatar">
            <span class="material-symbols-rounded">medical_services</span>
        </div>
        <div class="content typing-indicator">
            <span></span><span></span><span></span>
        </div>`;
    chatWindow.appendChild(loaderDiv);
    scrollToBottom();
}

// ANIMATION: Remove "Thinking" Bubbles
function removeLoading() {
    const loader = document.getElementById('loading-indicator');
    if (loader) loader.remove();
}

// ---------------------------------------------------------
// UI MESSAGE RENDERER
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

    messageEl.appendChild(avatar);
    messageEl.appendChild(content);
    chatWindow.appendChild(messageEl);

    if (sender === 'bot') {
        // 1. Parse Markdown
        let htmlContent = typeof marked !== 'undefined' ? marked.parse(text) : text;
        
        // 2. Highlight Medicines (Safely check if MedicineDB exists)
        if (typeof MedicineDB !== 'undefined') {
            htmlContent = MedicineDB.highlightMedicines(htmlContent);
        }

        // 3. Typewriter Effect
        content.classList.add('typing-cursor');
        typeWriterEffect(content, htmlContent);
        
    } else {
        content.innerText = text;
        scrollToBottom();
    }
}

// ---------------------------------------------------------
// TYPEWRITER ANIMATION
// ---------------------------------------------------------
function typeWriterEffect(element, htmlString) {
    // Split by HTML tags so we don't break formatting
    const tokens = htmlString.split(/(<[^>]+>)/g);
    
    let tokenIndex = 0;
    let charIndex = 0;
    let currentToken = "";
    const TYPING_SPEED = 15; // Speed (ms)

    function type() {
        if (tokenIndex >= tokens.length) {
            element.classList.remove('typing-cursor');
            scrollToBottom();
            return;
        }

        currentToken = tokens[tokenIndex];

        if (currentToken.startsWith('<') && currentToken.endsWith('>')) {
            element.innerHTML += currentToken;
            tokenIndex++;
            type(); 
        } else {
            if (charIndex < currentToken.length) {
                element.innerHTML += currentToken.charAt(charIndex);
                charIndex++;
                scrollToBottom();
                setTimeout(type, TYPING_SPEED);
            } else {
                charIndex = 0;
                tokenIndex++;
                type();
            }
        }
    }
    type();
}

// ---------------------------------------------------------
// AUDIO & MESSAGING LOGIC
// ---------------------------------------------------------

async function stopSpeech() {
    if (speakingAudio) {
        speakingAudio.pause();
        speakingAudio.currentTime = 0;
    }
}

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

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Show User Message
    addMessage(text, 'user');
    userInput.value = '';

    await stopSpeech(); 
    
    // 2. Show Loading Animation
    showLoading();

    try {
        // 3. Send to Backend
        const response = await fetch(`${API_PREFIX}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        // 4. Remove Loading & Show Answer
        removeLoading();

        if (data.response) {
            addMessage(data.response, 'bot');
            speakText(data.response);
        } else if (data.error) {
            addMessage(`⚠️ Error: ${data.error}`, 'bot');
        } else {
            addMessage("⚠️ Server returned no response.", 'bot');
        }

    } catch (err) {
        removeLoading();
        console.error(err);
        addMessage("❌ Cannot reach server.", 'bot');
    }
}

// ---------------------------------------------------------
// VOICE INPUT
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

    // Show loading while transcribing voice
    showLoading();

    try {
        const response = await fetch(`${API_PREFIX}/voice`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        removeLoading();

        if (data.text) {
            userInput.value = data.text;
            sendMessage(); 
        }
    } catch (err) {
        removeLoading();
        console.error("STT Error:", err);
    }
}

// EVENT LISTENERS
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', e => e.key === 'Enter' && sendMessage());
micBtn.addEventListener('click', toggleRecording);
