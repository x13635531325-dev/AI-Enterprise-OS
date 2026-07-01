const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const messageList = document.getElementById("messageList");

let isGenerating = false;

function addMessage(role, text) {
  const message = document.createElement("p");

  if (role === "user") {
    message.className = "message user-message";
  } else {
    message.className = "message ai-message";
  }

  const label = document.createElement("strong");
  label.textContent = role === "user" ? "User: " : "AI: ";

  const content = document.createElement("span");
  content.textContent = text;

  message.appendChild(label);
  message.appendChild(content);

  messageList.appendChild(message);

  return message;
}

function addThinkingMessage() {
  return addMessage("ai", "正在思考……");
}

function sendMessage() {
  if (isGenerating) {
    return;
  }

  const text = messageInput.value;

  if (text.trim() === "") {
    return;
  }

  addMessage("user", text);

  messageInput.value = "";

  isGenerating = true;
  sendButton.disabled = true;
  sendButton.innerText = "生成中……";

  const thinkingMessage = addThinkingMessage();

  setTimeout(function () {
    thinkingMessage.textContent = "";

    const label = document.createElement("strong");
    label.textContent = "AI: ";

    const content = document.createElement("span");
    content.textContent = "这是一个模拟的 AI 回复。后续会接入真实大模型 API。";

    thinkingMessage.appendChild(label);
    thinkingMessage.appendChild(content);

    isGenerating = false;
    sendButton.disabled = false;
    sendButton.innerText = "发送";
  }, 1000);
}

sendButton.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    sendMessage();
  }
});