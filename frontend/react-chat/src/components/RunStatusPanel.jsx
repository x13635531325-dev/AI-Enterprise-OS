import {
  retrievalSourceLabel,
  statusLabel,
  stepLabel,
  taskTypeLabel,
  workflowLabel,
} from '../utils/displayText.js'

function RunStatusPanel({ run }) {
  if (!run) {
    return (
      <div className="run-status-panel">
        <h3>运行状态</h3>
        <p className="run-empty">暂无新的运行记录。</p>
      </div>
    )
  }

  return (
    <div className="run-status-panel">
      <h3>运行状态</h3>

      <div className="run-meta">
        <p>
          <strong>运行 ID：</strong> {run.id}
        </p>
        <p>
          <strong>状态：</strong> {statusLabel(run.status)}
        </p>
        <p>
          <strong>工作流：</strong> {workflowLabel(run.workflow_name)}
        </p>
      </div>

      {run.metrics && (
        <div className="run-metrics">
          <strong>运行指标</strong>
          <div className="metric-grid">
            <span>总 Token：{run.metrics.total_tokens}</span>
            <span>输入 Token：{run.metrics.total_input_tokens}</span>
            <span>输出 Token：{run.metrics.total_output_tokens}</span>
            <span>耗时：{run.metrics.total_latency_ms}ms</span>
            <span>模型调用：{run.metrics.model_call_count}</span>
            <span>失败调用：{run.metrics.failed_model_call_count}</span>
            <span>
              可重试失败：{run.metrics.retryable_failure_count}
            </span>
            <span>短路次数：{run.metrics.short_circuit_count}</span>
            <span>重试次数：{run.metrics.retry_count}</span>
            <span>工具调用：{run.metrics.tool_call_count ?? 0}</span>
            <span>
              工具失败：{run.metrics.failed_tool_call_count ?? 0}
            </span>
            <span>费用：${formatCost(run.metrics.total_cost_usd)}</span>
          </div>
        </div>
      )}

      <div className="run-steps">
        <strong>执行步骤</strong>
        <ul>
          {run.steps.map((step) => (
            <li key={step.id} className="run-step">
              <div className="run-step-header">
                <span>{stepLabel(step.name)}</span>
                <span>{statusLabel(step.status)}</span>
              </div>

              {hasModelMetadata(step) && (
                <div className="step-metadata">
                  <span>模型：{step.metadata.model}</span>
                  <span>提供商：{step.metadata.provider}</span>
                  <span>耗时：{step.metadata.latency_ms}ms</span>
                  <span>
                    Token：{step.metadata.input_tokens}/
                    {step.metadata.output_tokens}
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      {run.citations?.length > 0 && (
        <div className="run-citations">
          <strong>引用来源</strong>

          <div className="citation-list">
            {run.citations.map((citation) => (
              <div
                key={`${citation.document_id}-${citation.index}`}
                className="citation-item"
              >
                <div className="citation-header">
                  <span>[{citation.index}]</span>
                  <strong>{citation.document_title}</strong>
                </div>
                <p>{citation.excerpt}</p>
                <span className="citation-chunk">
                  文本块：{citation.chunk_id}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {run.trace && (
        <div className="run-trace">
          <strong>调用链路</strong>

          <div className="trace-meta">
            <span>ID: {run.trace.id}</span>
            <span>状态：{statusLabel(run.trace.status)}</span>
          </div>

          <div className="trace-spans">
            {run.trace.spans.map((span) => (
              <div key={span.id} className="trace-span">
                <div className="trace-span-header">
                  <span>{stepLabel(span.name)}</span>
                  <span>
                    {statusLabel(span.status)} - {span.latency_ms}ms
                  </span>
                </div>

                {hasRetrievalMetadata(span) && (
                  <RetrievalTrace metadata={span.metadata} />
                )}

                {hasPromptMetadata(span) && (
                  <PromptTrace metadata={span.metadata} />
                )}

                {hasCitationGuardrailMetadata(span) && (
                  <CitationGuardrailTrace metadata={span.metadata} />
                )}

                {span.model_calls.length > 0 && (
                  <div className="model-calls">
                    {span.model_calls.map((modelCall, index) => (
                      <div
                        key={modelCall.id}
                        className={`model-call model-call-${modelCall.status}`}
                      >
                        <span>请求：{index + 1}</span>
                        <span>状态：{statusLabel(modelCall.status)}</span>
                        <span>尝试：{modelCall.attempt}</span>
                        <span>{modelCall.provider}</span>
                        <span>{modelCall.model}</span>
                        <span>{taskTypeLabel(modelCall.task_type)}</span>
                        <span>熔断器：{statusLabel(modelCall.circuit_state)}</span>
                        <span>
                          Token：{modelCall.input_tokens}/
                          {modelCall.output_tokens}
                        </span>
                        <span>费用：${formatCost(modelCall.cost_usd)}</span>
                        {modelCall.error_type && (
                          <span>错误类型：{modelCall.error_type}</span>
                        )}
                        {modelCall.status === 'failed' && (
                          <span>
                            可重试：{formatBoolean(modelCall.retryable)}
                          </span>
                        )}
                        {modelCall.error && (
                          <span>错误：{modelCall.error}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {span.tool_calls?.length > 0 && (
                  <div className="tool-calls">
                    <div className="tool-calls-label">工具执行</div>

                    {span.tool_calls.map((toolCall) => (
                      <div
                        key={toolCall.tool_call_id}
                        className={`tool-call tool-call-${toolCall.status}`}
                      >
                        <div className="tool-call-header">
                          <strong>{toolCall.tool_name}</strong>
                          <span>{statusLabel(toolCall.status)}</span>
                          <span>{toolCall.latency_ms}ms</span>
                        </div>

                        <div className="tool-call-payloads">
                          <div>
                            <span className="tool-payload-label">参数</span>
                            <pre>{formatJson(toolCall.arguments)}</pre>
                          </div>

                          <div>
                            <span className="tool-payload-label">
                              {toolCall.error ? '错误' : '结果'}
                            </span>
                            <pre>
                              {formatJson(toolCall.error || toolCall.output)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CitationGuardrailTrace({ metadata }) {
  return (
    <div
      className={`guardrail-trace guardrail-trace-${metadata.citation_guardrail_status}`}
    >
      <div className="guardrail-trace-label">引用检查</div>

      <div className="guardrail-trace-facts">
        <span>状态：{statusLabel(metadata.citation_guardrail_status)}</span>
        <span>必须引用：{formatBoolean(metadata.citation_required)}</span>
        <span>
          可用来源：{formatList(metadata.available_source_indices)}
        </span>
        <span>已引用：{formatList(metadata.cited_source_indices)}</span>
        <span>
          无效引用：{formatList(metadata.invalid_source_indices)}
        </span>
        <span>
          缺少引用：{formatBoolean(metadata.missing_required_citation)}
        </span>
      </div>
    </div>
  )
}

function PromptTrace({ metadata }) {
  return (
    <div className="prompt-trace">
      <div className="prompt-trace-label">提示词</div>

      <div className="prompt-trace-facts">
        <span>{metadata.prompt_name}</span>
        <span>版本：{metadata.prompt_version}</span>
        <span>策略：{metadata.prompt_policy}</span>
        <span>来源数：{metadata.context_source_count}</span>
        <span>哈希：{metadata.prompt_template_hash}</span>
      </div>
    </div>
  )
}

function RetrievalTrace({ metadata }) {
  const results = metadata.retrieval_results ?? []

  return (
    <div className="retrieval-trace">
      <div className="retrieval-summary">
        <span>返回数量（top_k）：{metadata.requested_top_k}</span>
        <span>候选数：{metadata.candidate_k}</span>
        <span>结果数：{metadata.result_count}</span>
        <span>重排器：{formatBoolean(metadata.reranker_enabled)}</span>
      </div>

      {results.length > 0 && (
        <div className="retrieval-results">
          {results.map((result) => (
            <div key={result.chunk_id} className="retrieval-result">
              <div className="retrieval-result-header">
                <strong>
                  #{result.rank} {result.document_title}
                </strong>
                <span>{result.retrieval_sources.map(retrievalSourceLabel).join(' + ')}</span>
              </div>

              <div className="retrieval-scores">
                <span>综合分：{formatScore(result.score)}</span>
                <span>关键词：{formatScore(result.lexical_score)}</span>
                <span>向量：{formatScore(result.vector_score)}</span>
                <span>重排：{formatScore(result.reranker_score)}</span>
              </div>

              <span className="retrieval-chunk">
                文本块：{result.chunk_id}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function hasModelMetadata(step) {
  return Boolean(step.metadata?.model)
}

function hasRetrievalMetadata(span) {
  return Array.isArray(span.metadata?.retrieval_results)
}

function hasPromptMetadata(span) {
  return Boolean(span.metadata?.prompt_version)
}

function hasCitationGuardrailMetadata(span) {
  return Boolean(span.metadata?.citation_guardrail_status)
}

function formatCost(cost) {
  return Number(cost).toFixed(6)
}

function formatScore(score) {
  return Number(score ?? 0).toFixed(4)
}

function formatBoolean(value) {
  return value ? '是' : '否'
}

function formatList(value) {
  return Array.isArray(value) && value.length > 0 ? value.join(', ') : '-'
}

function formatJson(value) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }

  try {
    const parsedValue = typeof value === 'string' ? JSON.parse(value) : value
    return JSON.stringify(parsedValue, null, 2)
  } catch {
    return String(value)
  }
}

export default RunStatusPanel
