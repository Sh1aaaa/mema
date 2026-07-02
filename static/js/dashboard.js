function confirmPayrollGeneration() {
    return confirm("Are you sure you want to execute calculation compilation metrics on raw timecard registries?");
}

function runPayrollAudit() {
    const inputField = document.getElementById('ai-user-input');
    const stream = document.getElementById('chat-box-stream');
    const btn = document.getElementById('audit-trigger-btn');
    const message = inputField.value.trim();

    if (!message) return;

    const userBubble = document.createElement('div');
    userBubble.style.marginBottom = '12px';
    userBubble.style.textAlign = 'right';
    userBubble.style.color = 'var(--accent)';

    const userLabel = document.createElement('strong');
    userLabel.textContent = 'You: ';

    userBubble.appendChild(userLabel);
    userBubble.appendChild(document.createTextNode(message));
    stream.appendChild(userBubble);

    inputField.value = '';
    btn.disabled = true;
    btn.innerText = 'Analyzing...';
    stream.scrollTop = stream.scrollHeight;

    fetch('/audit-desk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(res => res.json())
    .then(data => {
        const aiBubble = document.createElement('div');
        aiBubble.style.background = 'white';
        aiBubble.style.border = '1px solid var(--border)';
        aiBubble.style.padding = '12px';
        aiBubble.style.borderRadius = '6px';
        aiBubble.style.marginBottom = '12px';
        aiBubble.style.borderLeft = '3px solid var(--accent)';
        aiBubble.style.lineHeight = '1.5';

        const aiLabel = document.createElement('strong');
        aiLabel.textContent = 'Assistant: ';
        aiBubble.appendChild(aiLabel);

        const contentText = data.explanation || data.error || 'No text response received.';
        aiBubble.appendChild(document.createTextNode(contentText));

        stream.appendChild(aiBubble);
        stream.scrollTop = stream.scrollHeight;
    })
    .catch(() => {
        const errorBubble = document.createElement('div');
        errorBubble.style.color = '#b91c1c';
        errorBubble.style.marginBottom = '12px';
        errorBubble.innerHTML = '<strong>System Error:</strong> Connection lost to generative AI portal endpoint.';
        stream.appendChild(errorBubble);
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerText = 'Send Query';
        inputField.focus();
    });
}

function handleAiKeyPress(event) {
    if (event.key === 'Enter') {
        runPayrollAudit();
    }
}