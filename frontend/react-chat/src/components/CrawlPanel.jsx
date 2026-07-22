import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  CloudUpload,
  Database,
  FileArchive,
  FileText,
  Globe2,
  HardDrive,
  Image,
  ListTree,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
} from 'lucide-react'
import {
  createCrawl,
  getCrawlCapabilities,
  listCrawls,
  retryCrawl,
} from '../api/chatApi.js'
import { statusLabel } from '../utils/displayText.js'

const fetchModeLabels = {
  http: 'HTTP 请求',
  dynamic: '动态浏览器',
  stealth: '隐身浏览器',
}

const destinationLabels = {
  local: '本地存储',
  oss: '阿里云 OSS',
  mysql: 'MySQL',
}

const bucketAliasLabels = {
  default: '默认',
  content: '内容',
  review: '审核',
}

const collectionTypes = [
  { value: 'page', label: '网页正文', icon: FileText },
  { value: 'files', label: '网页文件', icon: FileArchive },
  { value: 'images', label: '网页图片', icon: Image },
  { value: 'custom', label: '自定义数据', icon: ListTree },
]

const fileTypeGroups = {
  documents: { label: '文档', extensions: ['pdf', 'doc', 'docx', 'txt'] },
  spreadsheets: { label: '表格', extensions: ['xls', 'xlsx', 'csv'] },
  presentations: { label: '演示文稿', extensions: ['ppt', 'pptx'] },
  archives: { label: '压缩包', extensions: ['zip', 'rar', '7z'] },
}

const autoPaginationSelector = [
  'a[rel="next"]::attr(href)',
  'a.next::attr(href)',
  '.pagination a::attr(href)',
  '.pager a::attr(href)',
].join(', ')

const pagePresetFields = [
  {
    name: 'title',
    selector: 'h1::text, title::text',
    selector_type: 'css',
    multiple: false,
    required: false,
    adaptive: true,
  },
  {
    name: 'content',
    selector: 'article p::text, main p::text, body p::text',
    selector_type: 'css',
    multiple: true,
    required: false,
    adaptive: true,
  },
  {
    name: 'published_at',
    selector: 'time::attr(datetime), time::text',
    selector_type: 'css',
    multiple: false,
    required: false,
    adaptive: true,
  },
]

const defaultField = () => ({
  key: `${Date.now()}-${Math.random()}`,
  name: 'title',
  selector: 'h1::text',
  selector_type: 'css',
  multiple: false,
  required: true,
  adaptive: true,
})

function CrawlPanel() {
  const [capabilities, setCapabilities] = useState(null)
  const [jobs, setJobs] = useState([])
  const [fields, setFields] = useState([defaultField()])
  const [name, setName] = useState('网站数据采集')
  const [startUrls, setStartUrls] = useState('https://example.com')
  const [collectionType, setCollectionType] = useState('page')
  const [collectionDescription, setCollectionDescription] = useState('')
  const [fileTypes, setFileTypes] = useState(Object.keys(fileTypeGroups))
  const [autoPagination, setAutoPagination] = useState(false)
  const [itemSelector, setItemSelector] = useState('')
  const [followSelector, setFollowSelector] = useState('')
  const [fetchMode, setFetchMode] = useState('http')
  const [maxPages, setMaxPages] = useState(100)
  const [concurrency, setConcurrency] = useState(4)
  const [downloadDelay, setDownloadDelay] = useState(0.5)
  const [robotsTxtObey, setRobotsTxtObey] = useState(true)
  const [localEnabled, setLocalEnabled] = useState(true)
  const [localDirectory, setLocalDirectory] = useState('crawls')
  const [ossEnabled, setOssEnabled] = useState(false)
  const [bucketAlias, setBucketAlias] = useState('default')
  const [ossPrefix, setOssPrefix] = useState('ai-enterprise-os/crawls')
  const [mysqlEnabled, setMysqlEnabled] = useState(false)
  const [mysqlTable, setMysqlTable] = useState('ai_crawl_records')
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [retryingJobId, setRetryingJobId] = useState(null)
  const [statusText, setStatusText] = useState('')

  const hasActiveJobs = useMemo(
    () => jobs.some((job) => ['queued', 'running'].includes(job.status)),
    [jobs],
  )
  const collectionReady =
    (collectionType !== 'custom' || fields.length > 0) &&
    (collectionType !== 'files' || fileTypes.length > 0)

  useEffect(() => {
    refreshAll()
  }, [])

  useEffect(() => {
    if (!hasActiveJobs) {
      return undefined
    }
    const timer = window.setInterval(() => refreshJobs(false), 2500)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs])

  function refreshAll() {
    setIsLoading(true)
    setStatusText('')
    return Promise.all([getCrawlCapabilities(), listCrawls()])
      .then(([nextCapabilities, nextJobs]) => {
        setCapabilities(nextCapabilities)
        setJobs(nextJobs)
      })
      .catch((error) => setStatusText(error.message))
      .finally(() => setIsLoading(false))
  }

  function refreshJobs(showLoading = true) {
    if (showLoading) setIsLoading(true)
    return listCrawls()
      .then(setJobs)
      .catch((error) => setStatusText(error.message))
      .finally(() => {
        if (showLoading) setIsLoading(false)
      })
  }

  function updateField(key, property, value) {
    setFields((current) =>
      current.map((field) =>
        field.key === key ? { ...field, [property]: value } : field,
      ),
    )
  }

  function addField() {
    const field = defaultField()
    field.name = `field_${fields.length + 1}`
    field.selector = ''
    field.required = false
    setFields((current) => [...current, field])
  }

  function removeField(key) {
    setFields((current) => current.filter((field) => field.key !== key))
  }

  function toggleFileType(type) {
    setFileTypes((current) =>
      current.includes(type)
        ? current.filter((item) => item !== type)
        : [...current, type],
    )
  }

  function handleCollectionTypeChange(type) {
    setCollectionType(type)
    setCollectionDescription('')
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (
      isSubmitting ||
      (collectionType === 'custom' && fields.length === 0) ||
      (collectionType === 'files' && fileTypes.length === 0) ||
      (!localEnabled && !ossEnabled && !mysqlEnabled)
    ) {
      return
    }
    setIsSubmitting(true)
    setStatusText('')
    const urls = startUrls
      .split(/[,\n]/)
      .map((value) => value.trim())
      .filter(Boolean)
    const assetExtensions = collectionType === 'files'
      ? fileTypes.flatMap((type) => fileTypeGroups[type].extensions)
      : ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp']
    const assetDownloadsEnabled = ['files', 'images'].includes(collectionType)
    const payload = {
      name: name.trim(),
      start_urls: urls,
      item_selector: collectionType === 'custom' ? itemSelector.trim() || null : null,
      fields: collectionType === 'page'
        ? pagePresetFields
        : collectionType === 'custom'
          ? fields.map(({ key: _key, ...field }) => field)
          : [],
      follow_selector: autoPagination
        ? autoPaginationSelector
        : collectionType === 'custom'
          ? followSelector.trim() || null
          : null,
      fetch_mode: fetchMode,
      max_pages: Number(maxPages),
      concurrent_requests: Number(concurrency),
      concurrent_requests_per_domain: Math.min(Number(concurrency), 4),
      download_delay_seconds: Number(downloadDelay),
      robots_txt_obey: robotsTxtObey,
      asset_downloads: {
        enabled: assetDownloadsEnabled,
        selector: collectionType === 'images'
          ? 'img[src], img[data-src]'
          : 'a[href]',
        url_attributes: collectionType === 'images'
          ? ['src', 'data-src']
          : ['href'],
        description: collectionDescription.trim() || null,
        extensions: assetExtensions,
        max_assets: 200,
      },
      destinations: {
        local: {
          enabled: localEnabled,
          directory: localDirectory.trim(),
          save_html: true,
          save_json: true,
        },
        oss: {
          enabled: ossEnabled,
          bucket_alias: bucketAlias,
          prefix: ossPrefix.trim(),
          upload_html: true,
          upload_json: true,
        },
        mysql: {
          enabled: mysqlEnabled,
          table: mysqlTable.trim(),
        },
      },
    }
    createCrawl(payload)
      .then((job) => {
        setJobs((current) => [job, ...current])
        setStatusText(`爬取任务 ${job.id} 已进入队列。`)
      })
      .catch((error) => setStatusText(error.message))
      .finally(() => setIsSubmitting(false))
  }

  function handleRetry(jobId) {
    setRetryingJobId(jobId)
    setStatusText('')
    retryCrawl(jobId)
      .then((job) => {
        setJobs((current) =>
          current.map((item) => (item.id === job.id ? job : item)),
        )
      })
      .catch((error) => setStatusText(error.message))
      .finally(() => setRetryingJobId(null))
  }

  return (
    <section className="crawl-console">
      <div className="crawl-console-header">
        <div>
          <div className="section-kicker"><Globe2 size={15} /> 数据采集</div>
          <h2>Scrapling 爬虫控制台</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={refreshAll}
          disabled={isLoading}
          title="刷新爬取状态"
          aria-label="刷新爬取状态"
        >
          <RefreshCw size={17} className={isLoading ? 'spin' : ''} />
        </button>
      </div>

      <div className="destination-health">
        <Capability
          icon={<Globe2 size={17} />}
          label={`Scrapling ${capabilities?.scrapling_version ?? '...'}`}
          ready={Boolean(capabilities)}
        />
        {(capabilities?.destinations ?? []).map((destination) => (
          <Capability
            key={destination.name}
            icon={destination.name === 'local'
              ? <HardDrive size={17} />
              : destination.name === 'oss'
                ? <CloudUpload size={17} />
                : <Database size={17} />}
            label={destinationLabels[destination.name] ?? destination.name.toUpperCase()}
            ready={destination.configured}
            title={destination.configured ? '已就绪' : '尚未配置'}
          />
        ))}
      </div>

      <form className="crawl-form" onSubmit={handleSubmit}>
        <div className="crawl-form-grid">
          <label>
            任务名称
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label className="span-two">
            起始网址
            <textarea
              value={startUrls}
              onChange={(event) => setStartUrls(event.target.value)}
              rows="3"
              required
            />
          </label>
        </div>

        <div className="collection-preset">
          <div className="collection-preset-header">
            <strong>采集内容</strong>
          </div>
          <div className="collection-type-control" role="group" aria-label="采集内容类型">
            {collectionTypes.map((option) => {
              const Icon = option.icon
              return (
                <button
                  key={option.value}
                  type="button"
                  className={collectionType === option.value ? 'active' : ''}
                  onClick={() => handleCollectionTypeChange(option.value)}
                >
                  <Icon size={17} />
                  {option.label}
                </button>
              )
            })}
          </div>
        </div>

        {collectionType === 'files' && (
          <div className="file-type-filter">
            <strong>文件类型</strong>
            <div className="file-type-options">
              {Object.entries(fileTypeGroups).map(([type, config]) => (
                <label className="toggle-line" key={type}>
                  <input
                    type="checkbox"
                    checked={fileTypes.includes(type)}
                    onChange={() => toggleFileType(type)}
                  />
                  {config.label}
                </label>
              ))}
            </div>
          </div>
        )}

        {['files', 'images'].includes(collectionType) && (
          <label className="collection-description">
            具体采集要求（选填）
            <input
              value={collectionDescription}
              onChange={(event) => setCollectionDescription(event.target.value)}
              maxLength="500"
              placeholder={collectionType === 'files'
                ? '例如：只爬安徽省的试卷'
                : '例如：只爬安徽省学校的校徽图片'}
            />
          </label>
        )}

        <div className="crawl-mode-row">
          <span>网页加载方式</span>
          <div className="segmented-control" role="group" aria-label="抓取方式">
            {['http', 'dynamic', 'stealth'].map((mode) => (
              <button
                key={mode}
                type="button"
                className={fetchMode === mode ? 'active' : ''}
                onClick={() => setFetchMode(mode)}
              >
                {fetchModeLabels[mode]}
              </button>
            ))}
          </div>
        </div>

        {collectionType === 'custom' && (
        <div className="advanced-rules">
        <div className="advanced-rules-header">
          <strong>高级采集规则</strong>
        </div>
        <div className="crawl-form-grid selectors-grid">
          <label>
            数据项选择器
            <input
              value={itemSelector}
              onChange={(event) => setItemSelector(event.target.value)}
              placeholder="article, .product"
            />
          </label>
          <label>
            翻页链接选择器
            <input
              value={followSelector}
              onChange={(event) => setFollowSelector(event.target.value)}
              placeholder="a.next::attr(href)"
            />
          </label>
        </div>

        <div className="field-editor">
          <div className="field-editor-header">
            <strong>提取字段</strong>
            <button type="button" className="text-icon-button" onClick={addField}>
              <Plus size={15} /> 添加字段
            </button>
          </div>
          {fields.map((field) => (
            <div className="field-row" key={field.key}>
              <input
                aria-label="字段名称"
                value={field.name}
                onChange={(event) => updateField(field.key, 'name', event.target.value)}
                placeholder="字段名（英文）"
                required
              />
              <input
                aria-label="字段选择器"
                value={field.selector}
                onChange={(event) => updateField(field.key, 'selector', event.target.value)}
                placeholder="h1::text"
                required
              />
              <select
                aria-label="选择器类型"
                value={field.selector_type}
                onChange={(event) => updateField(field.key, 'selector_type', event.target.value)}
              >
                <option value="css">CSS</option>
                <option value="xpath">XPath</option>
              </select>
              <label className="compact-check">
                <input
                  type="checkbox"
                  checked={field.multiple}
                  onChange={(event) => updateField(field.key, 'multiple', event.target.checked)}
                />
                多值
              </label>
              <label className="compact-check">
                <input
                  type="checkbox"
                  checked={field.adaptive}
                  onChange={(event) => updateField(field.key, 'adaptive', event.target.checked)}
                />
                自适应
              </label>
              <button
                className="icon-button danger"
                type="button"
                onClick={() => removeField(field.key)}
                disabled={fields.length === 1}
                title="删除字段"
                aria-label="删除字段"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
        </div>
        )}

        <div className="crawl-runtime-grid">
          <label>最大页数<input type="number" min="1" max="10000" value={maxPages} onChange={(event) => setMaxPages(event.target.value)} /></label>
          <label>并发数<input type="number" min="1" max="64" value={concurrency} onChange={(event) => setConcurrency(event.target.value)} /></label>
          <label>请求间隔（秒）<input type="number" min="0" max="60" step="0.1" value={downloadDelay} onChange={(event) => setDownloadDelay(event.target.value)} /></label>
          <label className="toggle-line"><input type="checkbox" checked={robotsTxtObey} onChange={(event) => setRobotsTxtObey(event.target.checked)} /> 遵守 robots.txt</label>
          <label className="toggle-line"><input type="checkbox" checked={autoPagination} onChange={(event) => setAutoPagination(event.target.checked)} /> 自动识别翻页</label>
        </div>

        <div className="sink-section-header">
          <strong>存储位置</strong>
          <span>可选择一个或多个输出目标</span>
        </div>
        <div className="sink-grid">
          <fieldset className={localEnabled ? 'sink-enabled' : ''}>
            <legend><HardDrive size={16} /> 本地存储</legend>
            <label className="toggle-line"><input type="checkbox" checked={localEnabled} onChange={(event) => setLocalEnabled(event.target.checked)} /> 启用</label>
            <label>相对目录<input value={localDirectory} onChange={(event) => setLocalDirectory(event.target.value)} disabled={!localEnabled} placeholder="crawls" /></label>
            <span className="sink-hint">文件保存在后端配置的本地存储根目录下。</span>
          </fieldset>
          <fieldset className={ossEnabled ? 'sink-enabled' : ''}>
            <legend><CloudUpload size={16} /> 阿里云 OSS</legend>
            <label className="toggle-line"><input type="checkbox" checked={ossEnabled} onChange={(event) => setOssEnabled(event.target.checked)} /> 启用</label>
            <label>存储桶<select value={bucketAlias} onChange={(event) => setBucketAlias(event.target.value)} disabled={!ossEnabled}>
              {Object.entries(capabilities?.bucket_aliases ?? { default: 'default', content: 'content', review: 'review' }).map(([alias, bucket]) => <option key={alias} value={alias}>{bucketAliasLabels[alias] ?? alias} / {bucket}</option>)}
            </select></label>
            <label>对象前缀<input value={ossPrefix} onChange={(event) => setOssPrefix(event.target.value)} disabled={!ossEnabled} /></label>
          </fieldset>
          <fieldset className={mysqlEnabled ? 'sink-enabled' : ''}>
            <legend><Database size={16} /> MySQL</legend>
            <label className="toggle-line"><input type="checkbox" checked={mysqlEnabled} onChange={(event) => setMysqlEnabled(event.target.checked)} /> 启用</label>
            <label>目标数据表<input value={mysqlTable} onChange={(event) => setMysqlTable(event.target.value)} disabled={!mysqlEnabled} /></label>
          </fieldset>
        </div>

        <div className="crawl-submit-row">
          <span className={statusText ? 'crawl-feedback' : ''}>{statusText}</span>
          <button className="primary-action" type="submit" disabled={isSubmitting || !collectionReady || (!localEnabled && !ossEnabled && !mysqlEnabled)}>
            <Globe2 size={16} /> {isSubmitting ? '提交中' : '创建爬取任务'}
          </button>
        </div>
      </form>

      <div className="crawl-jobs">
        <div className="crawl-jobs-header"><h3>最近任务</h3><span>{jobs.length}</span></div>
        {jobs.length === 0 ? <p className="crawl-empty">暂无爬取任务。</p> : jobs.map((job) => (
          <div className="crawl-job-row" key={job.id}>
            <div className={`crawl-job-status status-${job.status}`}>{job.status === 'completed' ? <CheckCircle2 size={16} /> : job.status === 'failed' ? <AlertCircle size={16} /> : <RefreshCw size={16} className={['queued', 'running'].includes(job.status) ? 'spin' : ''} />}<span>{statusLabel(job.status)}</span></div>
            <div className="crawl-job-main"><strong>{job.name}</strong><code>{job.id}</code>{job.error && <p>{job.error}</p>}</div>
            <div className="crawl-job-metrics"><span>{job.pages_crawled} 个抓取项</span><span>{job.records_written} 条记录</span><span>{job.artifacts_uploaded} 个文件</span></div>
            <time>{formatDate(job.created_at)}</time>
            {['failed', 'paused'].includes(job.status) && <button className="icon-button" type="button" onClick={() => handleRetry(job.id)} disabled={retryingJobId === job.id} title="重试任务" aria-label="重试任务"><RotateCcw size={16} /></button>}
          </div>
        ))}
      </div>
    </section>
  )
}

function Capability({ icon, label, ready, title }) {
  return <div className={ready ? 'capability ready' : 'capability missing'} title={title}>{icon}<span>{label}</span>{ready ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}</div>
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : ''
}

export default CrawlPanel
