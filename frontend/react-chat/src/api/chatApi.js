export async function createRun(userText, workflowName) {
  const response = await fetch('/api/runs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      input: userText,
      workflow_name: workflowName,
    }),
  })

  if (!response.ok) {
    throw new Error('创建运行任务失败')
  }

  const run = await response.json()

  return run
}

export async function getRun(runId) {
  const response = await fetch(`/api/runs/${runId}`)

  if (!response.ok) {
    throw new Error('加载运行任务失败')
  }

  const run = await response.json()

  return run
}

export async function listRuns() {
  const response = await fetch('/api/runs')

  if (!response.ok) {
    throw new Error('加载运行历史失败')
  }

  const runs = await response.json()

  return runs
}

export async function getModelHealth() {
  const response = await fetch('/api/model-health')

  if (!response.ok) {
    throw new Error('加载模型健康状态失败')
  }

  const modelHealth = await response.json()

  return modelHealth
}

export async function createKnowledgeDocument({ title, content }) {
  const response = await fetch('/api/knowledge/documents', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title,
      content,
      metadata: {},
    }),
  })

  if (!response.ok) {
    throw new Error('创建知识库文档失败')
  }

  const document = await response.json()

  return document
}

export async function listKnowledgeDocuments() {
  const response = await fetch('/api/knowledge/documents')

  if (!response.ok) {
    throw new Error('加载知识库文档失败')
  }

  const documents = await response.json()

  return documents
}

export async function searchKnowledge(query, topK = 5) {
  const response = await fetch('/api/knowledge/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      top_k: topK,
    }),
  })

  if (!response.ok) {
    throw new Error('知识库检索失败')
  }

  const results = await response.json()

  return results
}

export async function reindexKnowledge() {
  const response = await fetch('/api/knowledge/reindex', {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error('知识库重新索引失败')
  }

  const result = await response.json()

  return result
}

export async function getCrawlCapabilities() {
  return requestJson('/api/crawls/capabilities', {}, '加载爬虫能力')
}

export async function listCrawls() {
  return requestJson('/api/crawls', {}, '加载爬取任务')
}

export async function createCrawl(config) {
  return requestJson(
    '/api/crawls',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    },
    '创建爬取任务',
  )
}

export async function retryCrawl(jobId) {
  return requestJson(
    `/api/crawls/${jobId}/retry`,
    { method: 'POST' },
    '重试爬取任务',
  )
}

export async function listSiteCrawlers() {
  return requestJson('/api/site-crawlers', {}, '加载站点爬虫')
}

export async function listSiteCrawlerTasks() {
  return requestJson('/api/site-crawler-tasks', {}, '加载爬虫任务')
}

export async function createSiteCrawlerTask(config) {
  return requestJson(
    '/api/site-crawler-tasks',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    },
    '创建站点爬虫任务',
  )
}

export async function listSiteCrawlerLogs(taskId, afterId = 0) {
  return requestJson(
    `/api/site-crawler-tasks/${taskId}/logs?after_id=${afterId}`,
    {},
    '加载爬虫日志',
  )
}

export async function retrySiteCrawlerTask(taskId) {
  return requestJson(
    `/api/site-crawler-tasks/${taskId}/retry`,
    { method: 'POST' },
    '重试站点爬虫任务',
  )
}

export async function cancelSiteCrawlerTask(taskId) {
  return requestJson(
    `/api/site-crawler-tasks/${taskId}/cancel`,
    { method: 'POST' },
    '停止站点爬虫任务',
  )
}

async function requestJson(url, options, action) {
  const response = await fetch(url, options)
  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : ''
    } catch {
      detail = ''
    }
    throw new Error(detail || `${action}失败`)
  }
  return response.json()
}
