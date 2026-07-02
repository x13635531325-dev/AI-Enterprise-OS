function ChatInput({
  inputValue,
  isGenerating,
  onInputChange,
  onInputKeyDown,
  onSend,
}) {
  const canSend = inputValue.trim() !== '' && !isGenerating

  return (
    <div className="input-area">
      <input
        type="text"
        placeholder="请输入你的问题"
        value={inputValue}
        onChange={onInputChange}
        onKeyDown={onInputKeyDown}
        disabled={isGenerating}
      />
      <button type="button">添加文件</button>
      <button type="button" onClick={onSend} disabled={!canSend}>
        {isGenerating ? '生成中……' : '发送'}
      </button>
    </div>
  )
}

export default ChatInput
