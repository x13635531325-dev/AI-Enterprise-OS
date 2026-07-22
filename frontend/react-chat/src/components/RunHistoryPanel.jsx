import { statusLabel, workflowLabel } from '../utils/displayText.js'

function RunHistoryPanel({ runs, selectedRunId, isLoading, onRefresh, onSelect }) {
  return (
    <div className="run-history-panel">
      <div className="run-history-header">
        <h3>运行历史</h3>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? '刷新中' : '刷新'}
        </button>
      </div>

      {runs.length === 0 ? (
        <p className="run-history-empty">暂无已保存的运行记录。</p>
      ) : (
        <div className="run-history-list">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              className={
                run.id === selectedRunId
                  ? 'run-history-item selected'
                  : 'run-history-item'
              }
              onClick={() => onSelect(run.id)}
            >
              <span className="run-history-title">{workflowLabel(run.workflow_name)}</span>
              <span className="run-history-input">{run.input}</span>
              <span className="run-history-meta">
                {statusLabel(run.status)} / {run.metrics.model_call_count} 次模型调用 /{' '}
                {formatDate(run.created_at)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function formatDate(value) {
  return new Date(value).toLocaleString('zh-CN')
}

export default RunHistoryPanel
