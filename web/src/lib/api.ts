import type { Project, RunStatus, Edit, EditResponse } from '../types'

class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  return res.json()
}

export const api = {
  // Health
  healthCheck: () => request<{ status: string }>('/health'),

  // Browse filesystem
  browse: (path?: string) =>
    request<{ current: string; parent: string | null; entries: { name: string; path: string; is_dir: boolean; has_children: boolean }[] }>(
      `/browse${path ? `?path=${encodeURIComponent(path)}` : ''}`
    ),

  // Projects
  getProjects: () => request<Project[]>('/projects'),
  createProject: (name: string, path: string) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, path }),
    }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  updateProject: (id: string, updates: Partial<Project>) =>
    request<Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  // Instructions
  submitInstruction: (
    instruction: string,
    workingDirectory: string,
    context?: object,
    projectId?: string,
  ) =>
    request<{ run_id: string; status: string }>('/instruction', {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        working_directory: workingDirectory,
        context: context || {},
        project_id: projectId,
      }),
    }),
  resumeRun: (runId: string, instruction: string, workingDirectory: string) =>
    request<{ run_id: string; status: string }>(`/instruction/${runId}`, {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        working_directory: workingDirectory,
      }),
    }),
  getStatus: (runId: string) => request<RunStatus>(`/status/${runId}`),

  // Edits
  getEdits: (runId: string, status?: string) => {
    const params = status ? `?status=${status}` : ''
    return request<Edit[]>(`/runs/${runId}/edits${params}`)
  },
  patchEdit: (runId: string, editId: string, action: 'approve' | 'reject', opId: string) =>
    request<EditResponse>(`/runs/${runId}/edits/${editId}`, {
      method: 'PATCH',
      body: JSON.stringify({ action, op_id: opId }),
    }),

  // Git
  gitCommit: (runId: string, message?: string) =>
    request<{ sha: string; message: string }>(`/runs/${runId}/git/commit`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  gitPush: (runId: string) =>
    request<{ branch: string; status: string }>(`/runs/${runId}/git/push`, {
      method: 'POST',
    }),
  gitCreatePR: (runId: string, title?: string, body?: string, draft?: boolean) =>
    request<{ number: number; html_url: string }>(`/runs/${runId}/git/pr`, {
      method: 'POST',
      body: JSON.stringify({ title, body, draft }),
    }),
  gitMerge: (runId: string, prNumber: number, method?: string) =>
    request<{ merged: boolean; sha: string }>(`/runs/${runId}/git/merge`, {
      method: 'POST',
      body: JSON.stringify({ pr_number: prNumber, method: method || 'squash' }),
    }),
}
