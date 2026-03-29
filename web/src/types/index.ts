export interface Project {
  id: string
  name: string
  path: string
  github_repo: string | null
  autonomy_mode: string
  default_model: string
  test_command: string | null
  build_command: string | null
  lint_command: string | null
  created_at: string
  updated_at: string
}

export interface Run {
  id: string
  project_id: string
  instruction: string
  status: 'running' | 'completed' | 'failed' | 'error' | 'waiting_for_human'
  plan: object[]
  branch: string | null
  created_at: string
  completed_at: string | null
}

export interface WSEvent {
  type: string
  run_id: string
  seq: number
  node: string | null
  model: string | null
  data: Record<string, unknown>
  timestamp: number
}

export interface RunSnapshot {
  type: 'snapshot'
  run_id: string
  status: string
  active_node: string | null
  current_step: number
  total_steps: number
  pending_approvals: string[]
  current_branch: string | null
  autonomy_mode: 'supervised' | 'autonomous'
  last_seq: number
}

export interface Edit {
  id: string
  run_id: string
  file_path: string
  step: number
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'committed'
  old_content: string | null
  new_content: string | null
  anchor: string | null
}

export interface ApiError {
  detail: string
}

export interface RunStatus {
  run_id: string
  status: string
  result: Record<string, unknown> | null
}

export interface EditResponse {
  edit_id: string
  run_id: string
  status: string
}

export interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  has_children?: boolean
  size?: number
}

export interface BrowseResponse {
  current: string
  entries: FileEntry[]
}

export interface FileContent {
  content: string | null
  language: string
  size: number
  binary: boolean
  path: string
}

export interface ProgressMetrics {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  runningTasks: number
  coveragePct: number
  ciPassRate: number
}

export interface DecisionTraceData {
  taskId: string
  dagId: string
  errorMessage: string
  errorCategory: 'syntax' | 'test' | 'contract' | 'structural'
  llmPrompt: string | null
  llmResponse: string | null
  filesRead: string[]
  moduleName: string | null
  timestamp: string
}
