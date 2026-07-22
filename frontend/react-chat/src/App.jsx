import { useEffect, useState } from 'react'
import MessageList from './components/MessageList.jsx'
import ChatInput from './components/ChatInput.jsx'
import ModelHealthPanel from './components/ModelHealthPanel.jsx'
import RunHistoryPanel from './components/RunHistoryPanel.jsx'
import RunStatusPanel from './components/RunStatusPanel.jsx'
import KnowledgePanel from './components/KnowledgePanel.jsx'
import SiteCrawlerPanel from './components/SiteCrawlerPanel.jsx'
import { Bot, DatabaseZap } from 'lucide-react'
import { initialMessages } from './data/initialMessages.js'
import { workflowOptions } from './data/workflowOptions.js'
import {
  createRun,
  getModelHealth,
  getRun,
  listRuns,
} from './api/chatApi.js'
import './App.css'

function App() {
  const [activeArea, setActiveArea] = useState('agent')
  const [inputValue, setInputValue] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [messages, setMessages] = useState(initialMessages)
  const [latestRun, setLatestRun] = useState(null)
  const [modelHealth, setModelHealth] = useState([])
  const [runHistory, setRunHistory] = useState([])
  const [isLoadingModelHealth, setIsLoadingModelHealth] = useState(false)
  const [isLoadingRunHistory, setIsLoadingRunHistory] = useState(false)
  const [selectedWorkflow, setSelectedWorkflow] = useState(
    'default_chat_workflow',
  )

  useEffect(() => {
    refreshModelHealth()
    refreshRunHistory()
  }, [])

  function refreshModelHealth() {
    setIsLoadingModelHealth(true)

    return getModelHealth()
      .then((healthItems) => {
        setModelHealth(healthItems)
      })
      .catch(() => {
        setModelHealth([])
      })
      .finally(() => {
        setIsLoadingModelHealth(false)
      })
  }

  function refreshRunHistory() {
    setIsLoadingRunHistory(true)

    return listRuns()
      .then((runs) => {
        setRunHistory(runs)
      })
      .catch(() => {
        setRunHistory([])
      })
      .finally(() => {
        setIsLoadingRunHistory(false)
      })
  }

  function handleSelectRun(runId) {
    getRun(runId).then((run) => {
      setLatestRun(run)
    })
  }

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

    createRun(userText, selectedWorkflow)
      .then((run) => {
        setLatestRun(run)
        refreshModelHealth()
        refreshRunHistory()

        setMessages((currentMessages) =>
          currentMessages.map((message) => {
            if (message.id === aiMessageId) {
              return {
                ...message,
                content: run.output,
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

  function handleWorkflowChange(event) {
    setSelectedWorkflow(event.target.value)
  }

  return (
    <div className="chat-page">
      <header className="app-header">
        <div className="app-brand">
          <span className="brand-mark">AE</span>
          <h1>AI Enterprise OS</h1>
        </div>
        <nav className="workspace-tabs" aria-label="工作区">
          <button className={activeArea === 'agent' ? 'active' : ''} type="button" onClick={() => setActiveArea('agent')}><Bot size={17} /> 智能体</button>
          <button className={activeArea === 'ingestion' ? 'active' : ''} type="button" onClick={() => setActiveArea('ingestion')}><DatabaseZap size={17} /> 数据采集</button>
        </nav>
      </header>

      <main className={`chat-container area-${activeArea}`}>
        {activeArea === 'ingestion' ? <SiteCrawlerPanel /> : <>
        <h2>智能体对话</h2>

        <ModelHealthPanel
          items={modelHealth}
          isLoading={isLoadingModelHealth}
          onRefresh={refreshModelHealth}
        />

        <RunHistoryPanel
          runs={runHistory}
          selectedRunId={latestRun?.id}
          isLoading={isLoadingRunHistory}
          onRefresh={refreshRunHistory}
          onSelect={handleSelectRun}
        />

        <KnowledgePanel />

        <MessageList messages={messages} />

        <RunStatusPanel run={latestRun} />

        <ChatInput
          inputValue={inputValue}
          isGenerating={isGenerating}
          selectedWorkflow={selectedWorkflow}
          workflowOptions={workflowOptions}
          onInputChange={handleInputChange}
          onInputKeyDown={handleInputKeyDown}
          onWorkflowChange={handleWorkflowChange}
          onSend={sendMessage}
        />
        </>}
      </main>
    </div>
  )
}

export default App
