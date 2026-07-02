import { useState } from 'react'
import MessageList from './components/MessageList.jsx'
import ChatInput from './components/ChatInput.jsx'
import { initialMessages } from './data/initialMessages.js'
import { mockSendMessage } from './api/chatApi.js'
import './App.css'

function App() {
  const [inputValue, setInputValue] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [messages, setMessages] = useState(initialMessages)

  function sendMessage() {
    const userText = inputValue.trim()

    if (userText === '') {
      return
    }

    if (isGenerating) {
      return
    }

    const timestamp = Date.now()
    const aiMessageId = timestamp + 1

    const userMessage = {
      id: timestamp,
      role: 'user',
      content: userText,
      status: 'normal',
    }

    const aiMessage = {
      id: aiMessageId,
      role: 'ai',
      content: '',
      status: 'loading',
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
      aiMessage,
    ])
    setInputValue('')
    setIsGenerating(true)

    mockSendMessage(userText)
      .then((replyText) => {
        setMessages((currentMessages) =>
          currentMessages.map((message) => {
            if (message.id === aiMessageId) {
              return {
                ...message,
                content: replyText,
                status: 'normal',
              }
            }

            return message
          }),
        )
      })
      .catch(() => {
        setMessages((currentMessages) =>
          currentMessages.map((message) => {
            if (message.id === aiMessageId) {
              return {
                ...message,
                content: '',
                status: 'error',
              }
            }

            return message
          }),
        )
      })
      .finally(() => {
        setIsGenerating(false)
      })
  }

  function handleInputChange(event) {
    setInputValue(event.target.value)
  }

  function handleInputKeyDown(event) {
    if (event.key === 'Enter') {
      sendMessage()
    }
  }

  return (
    <div className="chat-page">
      <h1>AI Enterprise OS</h1>

      <div className="chat-container">
        <h2>Chat</h2>

        <MessageList messages={messages} />

        <ChatInput
          inputValue={inputValue}
          isGenerating={isGenerating}
          onInputChange={handleInputChange}
          onInputKeyDown={handleInputKeyDown}
          onSend={sendMessage}
        />
      </div>
    </div>
  )
}

export default App
