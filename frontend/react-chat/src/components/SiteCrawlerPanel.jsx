import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSearch,
  Globe2,
  ListChecks,
  LogIn,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Square,
  TerminalSquare,
} from 'lucide-react'
import {
  cancelSiteCrawlerTask,
  createSiteCrawlerTask,
  listSiteCrawlerLogs,
  listSiteCrawlerTasks,
  listSiteCrawlers,
  retrySiteCrawlerTask,
} from '../api/chatApi.js'
import { statusLabel } from '../utils/displayText.js'
import CrawlPanel from './CrawlPanel.jsx'

const actionOptions = [
  { value: 'download', label: '下载并入库', icon: Download },
  { value: 'inspect', label: '检查登录与下载', icon: ShieldCheck },
  { value: 'probe', label: '探测站点', icon: Search },
  { value: 'login', label: '重新登录', icon: LogIn },
]

const activeStatuses = new Set(['queued', 'running', 'retrying'])

function SiteCrawlerPanel() {
  const [view, setView] = useState('sites')
  const [adapters, setAdapters] = useState([])
  const [tasks, setTasks] = useState([])
  const [selectedAdapterId, setSelectedAdapterId] = useState('')
  const [selectedAction, setSelectedAction] = useState('download')
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [logs, setLogs] = useState([])
  const [limit, setLimit] = useState(10)
  const [maxPages, setMaxPages] = useState(30)
  const [maxAttempts, setMaxAttempts] = useState(3)
  const [maxVerifyFailures, setMaxVerifyFailures] = useState(2)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [feedback, setFeedback] = useState('')

  const selectedAdapter = useMemo(
    () => adapters.find((adapter) => adapter.id === selectedAdapterId) ?? null,
    [adapters, selectedAdapterId],
  )
  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  )
  const selectedTaskStatus = selectedTask?.status
  const hasActiveTasks = useMemo(
    () => tasks.some((task) => activeStatuses.has(task.status)),
    [tasks],
  )

  useEffect(() => {
    refreshAll()
  }, [])

  useEffect(() => {
    if (!hasActiveTasks) return undefined
    const timer = window.setInterval(() => refreshTasks(false), 2000)
    return () => window.clearInterval(timer)
  }, [hasActiveTasks])

  useEffect(() => {
    if (!selectedTaskId) {
      setLogs([])
      return undefined
    }
    refreshLogs(selectedTaskId)
    if (!selectedTaskStatus || !activeStatuses.has(selectedTaskStatus)) return undefined
    const timer = window.setInterval(() => refreshLogs(selectedTaskId), 1500)
    return () => window.clearInterval(timer)
  }, [selectedTaskId, selectedTaskStatus])

  function refreshAll() {
    setIsLoading(true)
    setFeedback('')
    return Promise.all([listSiteCrawlers(), listSiteCrawlerTasks()])
      .then(([nextAdapters, nextTasks]) => {
        setAdapters(nextAdapters)
        setTasks(nextTasks)
        setSelectedAdapterId((current) => current || nextAdapters[0]?.id || '')
        setSelectedTaskId((current) => current || nextTasks[0]?.id || '')
      })
      .catch((error) => setFeedback(error.message))
      .finally(() => setIsLoading(false))
  }

  function refreshTasks(showLoading = true) {
    if (showLoading) setIsLoading(true)
    return listSiteCrawlerTasks()
      .then(setTasks)
      .catch((error) => setFeedback(error.message))
      .finally(() => {
        if (showLoading) setIsLoading(false)
      })
  }

  function refreshLogs(taskId) {
    return listSiteCrawlerLogs(taskId)
      .then(setLogs)
      .catch((error) => setFeedback(error.message))
  }

  function selectAdapter(adapter) {
    setSelectedAdapterId(adapter.id)
    const nextAction = adapter.actions.includes(selectedAction)
      ? selectedAction
      : adapter.actions.includes('download')
        ? 'download'
        : adapter.actions[0]
    setSelectedAction(nextAction)
  }

  function submitTask(event) {
    event.preventDefault()
    if (!selectedAdapter || !selectedAdapter.configured || isSubmitting) return
    setIsSubmitting(true)
    setFeedback('')
    const payload = {
      adapter_id: selectedAdapter.id,
      action: selectedAction,
      max_attempts: Number(maxAttempts),
    }
    if (selectedAction === 'download') {
      payload.limit = Number(limit)
      payload.max_pages = Number(maxPages)
      if (selectedAdapter.id === 'zxxk') {
        payload.max_verify_failures = Number(maxVerifyFailures)
      }
    }
    createSiteCrawlerTask(payload)
      .then((task) => {
        setTasks((current) => [task, ...current])
        setSelectedTaskId(task.id)
        setLogs([])
        setFeedback(`任务 ${task.id} 已进入队列。`)
      })
      .catch((error) => setFeedback(error.message))
      .finally(() => setIsSubmitting(false))
  }

  function retryTask(taskId) {
    retrySiteCrawlerTask(taskId)
      .then((task) => {
        setTasks((current) => current.map((item) => item.id === task.id ? task : item))
        setSelectedTaskId(task.id)
      })
      .catch((error) => setFeedback(error.message))
  }

  function stopTask(taskId) {
    cancelSiteCrawlerTask(taskId)
      .then((task) => {
        setTasks((current) => current.map((item) => item.id === task.id ? task : item))
      })
      .catch((error) => setFeedback(error.message))
  }

  return (
    <section className="site-crawler-console">
      <header className="site-crawler-header">
        <div>
          <div className="section-kicker"><Globe2 size={15} /> 资源采集</div>
          <h2>试卷爬虫调度中心</h2>
        </div>
        <div className="crawler-view-tabs" role="tablist" aria-label="爬虫类型">
          <button className={view === 'sites' ? 'active' : ''} type="button" onClick={() => setView('sites')}>
            <ListChecks size={16} /> 站点爬虫
          </button>
          <button className={view === 'generic' ? 'active' : ''} type="button" onClick={() => setView('generic')}>
            <FileSearch size={16} /> 公开网页采集
          </button>
        </div>
        <button className="icon-button" type="button" onClick={refreshAll} disabled={isLoading} title="刷新" aria-label="刷新">
          <RefreshCw size={17} className={isLoading ? 'spin' : ''} />
        </button>
      </header>

      {view === 'generic' ? <CrawlPanel /> : (
        <>
          <div className="adapter-strip">
            {adapters.map((adapter) => (
              <button
                key={adapter.id}
                className={`adapter-tile ${selectedAdapterId === adapter.id ? 'active' : ''}`}
                type="button"
                onClick={() => selectAdapter(adapter)}
              >
                <span className={`adapter-state ${adapter.configured ? 'ready' : 'missing'}`}>
                  {adapter.configured ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                  {adapter.configured ? '已连接' : '未连接'}
                </span>
                <strong>{adapter.name}</strong>
                <small>{adapter.configuration_detail}</small>
              </button>
            ))}
          </div>

          <div className="site-crawler-workbench">
            <form className="site-task-builder" onSubmit={submitTask}>
              <div className="workbench-title">
                <span>任务设置</span>
                <code>{selectedAdapter?.id ?? '--'}</code>
              </div>

              <div className="site-action-picker" role="group" aria-label="执行动作">
                {actionOptions
                  .filter((option) => selectedAdapter?.actions.includes(option.value))
                  .map((option) => {
                    const Icon = option.icon
                    return (
                      <button
                        key={option.value}
                        className={selectedAction === option.value ? 'active' : ''}
                        type="button"
                        onClick={() => setSelectedAction(option.value)}
                      >
                        <Icon size={16} /> {option.label}
                      </button>
                    )
                  })}
              </div>

              {selectedAction === 'download' && (
                <div className="site-task-fields">
                  <label>本次下载数量<input type="number" min="1" max="10000" value={limit} onChange={(event) => setLimit(event.target.value)} /></label>
                  <label>最多检查页数<input type="number" min="1" max="10000" value={maxPages} onChange={(event) => setMaxPages(event.target.value)} /></label>
                  <label>自动重试次数<input type="number" min="1" max="5" value={maxAttempts} onChange={(event) => setMaxAttempts(event.target.value)} /></label>
                  {selectedAdapter?.id === 'zxxk' && (
                    <label>连续验证停止阈值<input type="number" min="1" max="10" value={maxVerifyFailures} onChange={(event) => setMaxVerifyFailures(event.target.value)} /></label>
                  )}
                </div>
              )}

              <div className="adapter-capabilities">
                {(selectedAdapter?.capabilities ?? []).map((capability) => <span key={capability}>{capability}</span>)}
              </div>

              <div className="site-task-submit">
                <span>{feedback}</span>
                <button className="primary-action" type="submit" disabled={!selectedAdapter?.configured || isSubmitting}>
                  {selectedAction === 'login' ? <LogIn size={16} /> : <Download size={16} />}
                  {isSubmitting ? '提交中' : actionOptions.find((item) => item.value === selectedAction)?.label}
                </button>
              </div>
            </form>

            <section className="site-task-list">
              <div className="workbench-title"><span>运行任务</span><b>{tasks.length}</b></div>
              <div className="site-task-table">
                {tasks.length === 0 ? <p className="crawl-empty">暂无任务。</p> : tasks.map((task) => (
                  <div
                    key={task.id}
                    className={`site-task-row ${selectedTaskId === task.id ? 'selected' : ''}`}
                    role="button"
                    tabIndex="0"
                    onClick={() => setSelectedTaskId(task.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        setSelectedTaskId(task.id)
                      }
                    }}
                  >
                    <TaskState status={task.status} />
                    <span className="site-task-identity"><strong>{adapterName(adapters, task.adapter_id)}</strong><code>{task.id}</code></span>
                    <span className="site-task-action">{actionLabel(task.action)}</span>
                    <span className="site-task-attempt">{task.attempts}/{task.max_attempts}</span>
                    <time>{formatDate(task.created_at)}</time>
                    <span className="site-task-controls">
                      {activeStatuses.has(task.status) && <button className="icon-button danger" type="button" onClick={(event) => { event.stopPropagation(); stopTask(task.id) }} title="停止" aria-label="停止"><Square size={14} /></button>}
                      {['paused', 'failed', 'cancelled'].includes(task.status) && <button className="icon-button" type="button" onClick={(event) => { event.stopPropagation(); retryTask(task.id) }} title="重试" aria-label="重试"><RotateCcw size={15} /></button>}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <section className="crawler-log-panel">
            <div className="workbench-title">
              <span><TerminalSquare size={16} /> 任务日志</span>
              <code>{selectedTaskId || '--'}</code>
            </div>
            {selectedTask?.error && <div className="crawler-error"><AlertCircle size={16} /> <span>{selectedTask.error}</span></div>}
            <div className="crawler-log-output" role="log" aria-live="polite">
              {logs.length === 0 ? <span className="log-placeholder">选择任务后查看运行日志。</span> : logs.map((log) => (
                <div key={log.id} className={`log-line ${log.level}`}><time>{formatTime(log.created_at)}</time><span>{log.message}</span></div>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  )
}

function TaskState({ status }) {
  const active = activeStatuses.has(status)
  const Icon = status === 'completed' ? CheckCircle2 : status === 'failed' ? AlertCircle : active ? RefreshCw : AlertCircle
  return <span className={`task-state status-${status}`}><Icon size={15} className={active ? 'spin' : ''} /> {statusLabel(status)}</span>
}

function adapterName(adapters, id) {
  return adapters.find((adapter) => adapter.id === id)?.name ?? id
}

function actionLabel(action) {
  return actionOptions.find((item) => item.value === action)?.label ?? action
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''
}

function formatTime(value) {
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour12: false }) : ''
}

export default SiteCrawlerPanel
