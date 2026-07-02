function getMessageContent(message) {
  if (message.status === 'loading') {
    return 'AI 正在思考……'
  }

  if (message.status === 'error') {
    return '生成失败，请重试'
  }

  return message.content
}

function getMessageClassName(message) {
  let className =
    message.role === 'user'
      ? 'message user-message'
      : 'message ai-message'

  if (message.status === 'error') {
    className = `${className} error-message`
  }

  if (message.status === 'loading') {
    className = `${className} loading-message`
  }

  return className
}

function MessageBubble({ message }) {
  return (
    <p className={getMessageClassName(message)}>
      <strong>{message.role === 'user' ? 'User: ' : 'AI: '}</strong>
      {getMessageContent(message)}
    </p>
  )
}

export default MessageBubble
