import MessageBubble from './MessageBubble.jsx'

function MessageList({ messages }) {
  return (
    <div className="message-list">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  )
}

export default MessageList