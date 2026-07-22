const STATUS_LABELS = {
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  paused: '已暂停',
  healthy: '健康',
  open: '已熔断',
  closed: '正常',
  half_open: '半开',
  skipped: '已跳过',
  passed: '已通过',
  pending: '等待中',
  retrying: '重试中',
  cancelled: '已停止',
}

const WORKFLOW_LABELS = {
  default_chat_workflow: '默认聊天',
  task_planning_workflow: '任务规划',
  rag_workflow: '知识库问答',
}

const STEP_LABELS = {
  select_workflow: '选择工作流',
  receive_user_input: '接收用户输入',
  generate_ai_reply: '生成 AI 回复',
  create_task_plan: '创建任务计划',
  summarize_plan: '总结计划',
  validate_input: '输入校验',
  model_call: '模型调用',
  generate_response: '生成回答',
  generate_grounded_answer: '生成有依据的回答',
  retrieve_knowledge: '知识检索',
  citation_guardrail: '引用检查',
  task_plan: '任务规划',
  plan_summary: '计划总结',
}

const TASK_TYPE_LABELS = {
  chat: '对话',
  task_plan: '任务规划',
  plan_summary: '计划总结',
}

const RETRIEVAL_SOURCE_LABELS = {
  lexical: '关键词检索',
  vector: '向量检索',
  reranker: '重排',
}

export function statusLabel(value) {
  return STATUS_LABELS[value] ?? value
}

export function workflowLabel(value) {
  return WORKFLOW_LABELS[value] ?? value
}

export function stepLabel(value) {
  return STEP_LABELS[value] ?? value
}

export function taskTypeLabel(value) {
  return TASK_TYPE_LABELS[value] ?? value
}

export function retrievalSourceLabel(value) {
  return RETRIEVAL_SOURCE_LABELS[value] ?? value
}
