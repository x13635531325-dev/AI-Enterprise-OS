import { statusLabel, taskTypeLabel } from '../utils/displayText.js'

function ModelHealthPanel({ items, isLoading, onRefresh }) {
  return (
    <div className="model-health-panel">
      <div className="model-health-header">
        <h3>模型健康状态</h3>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? '刷新中' : '刷新'}
        </button>
      </div>

      {items.length === 0 ? (
        <p className="model-health-empty">暂无模型健康数据。</p>
      ) : (
        <div className="model-health-list">
          {items.map((item) => (
            <div key={item.key} className={`model-health-card ${item.status}`}>
              <div className="model-health-card-header">
                <strong>{item.model}</strong>
                <span className={`health-status health-status-${item.status}`}>
                  {statusLabel(item.status)}
                </span>
              </div>

              <div className="model-health-facts">
                <span>提供商：{item.provider}</span>
                <span>熔断器：{statusLabel(item.circuit_state)}</span>
                <span>
                  失败次数：{item.failure_count}/{item.failure_threshold}
                </span>
                <span>任务：{item.task_types.map(taskTypeLabel).join('、')}</span>
                {item.fallback_model && (
                  <span>备用模型：{item.fallback_model}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ModelHealthPanel
