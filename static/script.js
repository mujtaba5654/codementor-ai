const btn = document.getElementById("send-btn");
const input = document.getElementById("message");
const chatBox = document.getElementById("chat-box");

async function sendMessage() {

    const message = input.value.trim();

    if (!message) return;

    chatBox.innerHTML += `
        <div class="user-message">
            ${message}
        </div>
    `;

    input.value = "";

    chatBox.scrollTop = chatBox.scrollHeight;

    const response = await fetch("/chat", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            message: message
        })

    });

    const data = await response.json();

    chatBox.innerHTML += `
        <div class="bot-message">
            ${data.reply}
        </div>
    `;

    chatBox.scrollTop = chatBox.scrollHeight;

}

btn.addEventListener("click", sendMessage);

input.addEventListener("keypress", function(e){

    if(e.key==="Enter"){

        sendMessage();

    }

});