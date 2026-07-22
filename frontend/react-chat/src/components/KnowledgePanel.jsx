import { useEffect, useState } from 'react'
import {
  createKnowledgeDocument,
  listKnowledgeDocuments,
  reindexKnowledge,
  searchKnowledge,
} from '../api/chatApi.js'

function KnowledgePanel() {
  const [documents, setDocuments] = useState([])
  const [searchResults, setSearchResults] = useState([])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [query, setQuery] = useState('')
  const [statusText, setStatusText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [isReindexing, setIsReindexing] = useState(false)

  useEffect(() => {
    refreshDocuments()
  }, [])

  function refreshDocuments() {
    setIsLoading(true)

    return listKnowledgeDocuments()
      .then((items) => {
        setDocuments(items)
      })
      .catch(() => {
        setDocuments([])
        setStatusText('知识库文档加载失败。')
      })
      .finally(() => {
        setIsLoading(false)
      })
  }

  function handleCreateDocument(event) {
    event.preventDefault()

    const trimmedTitle = title.trim()
    const trimmedContent = content.trim()

    if (!trimmedTitle || !trimmedContent || isSaving) {
      return
    }

    setIsSaving(true)
    setStatusText('')

    createKnowledgeDocument({
      title: trimmedTitle,
      content: trimmedContent,
    })
      .then(() => {
        setTitle('')
        setContent('')
        setStatusText('文档已建立索引。')
        return refreshDocuments()
      })
      .catch(() => {
        setStatusText('文档索引失败。')
      })
      .finally(() => {
        setIsSaving(false)
      })
  }

  function handleSearch(event) {
    event.preventDefault()

    const trimmedQuery = query.trim()

    if (!trimmedQuery || isSearching) {
      return
    }

    setIsSearching(true)
    setStatusText('')

    searchKnowledge(trimmedQuery, 5)
      .then((results) => {
        setSearchResults(results)
      })
      .catch(() => {
        setSearchResults([])
        setStatusText('知识库检索失败。')
      })
      .finally(() => {
        setIsSearching(false)
      })
  }

  function handleReindex() {
    if (isReindexing) {
      return
    }

    setIsReindexing(true)
    setStatusText('')

    reindexKnowledge()
      .then((result) => {
        setStatusText(`已重新索引 ${result.updated_chunk_count} 个文本块。`)
        return refreshDocuments()
      })
      .catch(() => {
        setStatusText('重新索引失败。')
      })
      .finally(() => {
        setIsReindexing(false)
      })
  }

  return (
    <section className="knowledge-panel">
      <div className="knowledge-header">
        <div>
          <h3>知识库</h3>
          <p>已索引 {documents.length} 篇文档</p>
        </div>

        <div className="knowledge-actions">
          <button type="button" onClick={refreshDocuments} disabled={isLoading}>
            {isLoading ? '刷新中' : '刷新'}
          </button>
          <button
            type="button"
            onClick={handleReindex}
            disabled={isReindexing || documents.length === 0}
          >
            {isReindexing ? '重新索引中' : '重新索引'}
          </button>
        </div>
      </div>

      <div className="knowledge-grid">
        <form className="knowledge-form" onSubmit={handleCreateDocument}>
          <label>
            标题
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例如：Atlas 项目发布规范"
            />
          </label>

          <label>
            内容
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="粘贴内部制度、操作手册、标准流程或常见问题。"
              rows="7"
            />
          </label>

          <button
            type="submit"
            disabled={!title.trim() || !content.trim() || isSaving}
          >
            {isSaving ? '索引中' : '索引文档'}
          </button>
        </form>

        <div className="knowledge-search">
          <form onSubmit={handleSearch}>
            <label>
              检索
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="在向智能体提问前测试检索效果"
              />
            </label>

            <button type="submit" disabled={!query.trim() || isSearching}>
              {isSearching ? '检索中' : '检索'}
            </button>
          </form>

          {searchResults.length > 0 ? (
            <div className="knowledge-results">
              {searchResults.map((result) => (
                <div key={result.chunk_id} className="knowledge-result">
                  <div className="knowledge-result-header">
                    <strong>{result.document_title}</strong>
                    <span>{formatScore(result.score)}</span>
                  </div>

                  <p>{result.content}</p>

                  <div className="knowledge-result-meta">
                    <span>关键词：{formatScore(result.lexical_score)}</span>
                    <span>向量：{formatScore(result.vector_score)}</span>
                    <span>重排：{formatScore(result.reranker_score)}</span>
                    <span>{result.retrieval_sources.join(' + ')}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="knowledge-empty">暂无检索结果。</p>
          )}
        </div>
      </div>

      {statusText && <p className="knowledge-status">{statusText}</p>}

      {documents.length > 0 && (
        <div className="knowledge-documents">
          {documents.map((document) => (
            <div key={document.id} className="knowledge-document">
              <strong>{document.title}</strong>
              <span>{document.chunk_count} 个文本块</span>
              <p>{document.content}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function formatScore(score) {
  return Number(score ?? 0).toFixed(4)
}

export default KnowledgePanel
