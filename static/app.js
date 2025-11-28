const chatWindow = document.getElementById('chatWindow');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const waveVisualizer = document.getElementById('waveVisualizer');

let isRecording = false;
let mediaRecorder;
let audioChunks = [];

// Helper: Scroll to bottom
function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Helper: Add Message to UI
function addMessage(text, sender) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = sender === 'user' ? '🧑' : '🤖'; // Or use icons from HTML
    if (sender === 'bot') {
        avatar.innerHTML = '<span class="material-symbols-rounded">medical_services</span>';
    }

    const content = document.createElement('div');
    content.className = 'content';

    // Parse Markdown for bot messages
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

// Function: Send Text Message
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // UI updates
    addMessage(text, 'user');
    userInput.value = '';

    // Show loading state?

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        if (data.response) {
            addMessage(data.response, 'bot');
            speakText(data.response);
        } else if (data.error) {
            addMessage(`Error: ${data.error}`, 'bot');
        }
    } catch (err) {
        console.error(err);
        addMessage("Sorry, I couldn't connect to the server.", 'bot');
    }
}

// Function: Speak Text (TTS)
async function speakText(text) {
    try {
        const response = await fetch('/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
            audio.onended = () => URL.revokeObjectURL(url);
        }
    } catch (err) {
        console.error("TTS Error:", err);
    }
}

// Function: Handle Voice Recording
async function toggleRecording() {
    if (!isRecording) {
        // Start Recording
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await processVoice(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('active');
            waveVisualizer.classList.remove('hidden');
        } catch (err) {
            console.error("Mic Error:", err);
            alert("Could not access microphone.");
        }
    } else {
        // Stop Recording
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('active');
        waveVisualizer.classList.add('hidden');

        // Stop tracks
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
}

// Function: Process Voice (Send to STT)
async function processVoice(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob);

    try {
        const response = await fetch('/voice', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.text) {
            userInput.value = data.text;
            sendMessage(); // Auto-send after voice
        }
    } catch (err) {
        console.error("Voice Processing Error:", err);
    }
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

micBtn.addEventListener('click', toggleRecording);
