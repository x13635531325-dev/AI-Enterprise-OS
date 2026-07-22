function ChatInput({
  inputValue,
  isGenerating,
  selectedWorkflow,
  workflowOptions,
  onInputChange,
  onInputKeyDown,
  onWorkflowChange,
  onSend,
}) {
  const canSend = inputValue.trim() !== '' && !isGenerating

  return (
    <div className="input-area">
      <select
        value={selectedWorkflow}
        onChange={onWorkflowChange}
        disabled={isGenerating}
      >
        {workflowOptions.map((workflow) => (
          <option key={workflow.value} value={workflow.value}>
            {workflow.label}
          </option>
        ))}
      </select>
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
