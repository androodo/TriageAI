const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const API_PREFIX = API_BASE.endsWith("/api") ? API_BASE : `${API_BASE.replace(/\/$/, "")}/api`

export type CIStatus = "passed" | "failed" | "skipped"

export interface CIRun {
  id: string
  repo_name: string
  branch: string
  commit_sha: string
  pipeline_id: string
  environment: string
  status: CIStatus
  test_suite_name: string
  failed_test_names: string[]
  timestamp: string
  created_at: string
  updated_at: string
  failure_log?: {
    id: string
    cleaned_log_text: string
    exception_names: string[]
    failed_tests: string[]
  }
  triage_result?: {
    id: string
    failure_category: string
    confidence_score: number
    summary: string
    root_cause: string
    suggested_steps: string[]
    owner_guess: string | null
    issue_title: string
    issue_body: string
  }
  issue_draft?: {
    id: string
    title: string
    body: string
    labels: string[]
    assignee_guess: string | null
    format: "github" | "jira"
  }
}

export interface CIRunListItem {
  id: string
  repo_name: string
  branch: string
  commit_sha: string
  environment: string
  status: CIStatus
  test_suite_name: string
  timestamp: string
  triage_category?: string
  triage_summary?: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TriageResult {
  id: string
  ci_run_id: string
  failure_category: string
  confidence_score: number
  owner_guess: string | null
  summary: string
  root_cause: string
  suggested_steps: string[]
  issue_title: string
  issue_body: string
  model_used: string
  created_at: string
}

export interface SimilarFailure {
  ci_run_id: string
  repo_name: string
  branch: string
  commit_sha: string
  test_suite_name: string
  timestamp: string
  similarity_score: number
  failure_category: string | null
  summary: string | null
  root_cause: string | null
  suggested_steps: string[]
  failed_test_names: string[]
  exception_names: string[]
}

export interface IssueDraft {
  id: string
  ci_run_id: string
  title: string
  body: string
  labels: string[]
  assignee_guess: string | null
  format: "github" | "jira"
  created_at: string
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_PREFIX}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.text().catch(() => "Unknown error")
    throw new Error(`API request failed: ${response.status} ${error}`)
  }

  return response.json()
}

export const api = {
  // Health check
  health: () => request("/health"),

  // List CI runs
  listRuns: (params?: {
    status?: CIStatus
    repo_name?: string
    environment?: string
    page?: number
    page_size?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set("status", params.status)
    if (params?.repo_name) searchParams.set("repo_name", params.repo_name)
    if (params?.environment) searchParams.set("environment", params.environment)
    if (params?.page) searchParams.set("page", String(params.page))
    if (params?.page_size) searchParams.set("page_size", String(params.page_size))
    const query = searchParams.toString()
    return request<PaginatedResponse<CIRunListItem>>(`/runs${query ? `?${query}` : ""}`)
  },

  // Get single run
  getRun: (id: string) => request<CIRun>(`/runs/${id}`),

  // Triage a run
  triageRun: (id: string, force = false) =>
    request<TriageResult>(`/runs/${id}/triage`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),

  // Find similar failures
  similarFailures: (id: string) =>
    request<{ query_ci_run_id: string; count: number; items: SimilarFailure[] }>(`/runs/${id}/similar`),

  // Generate issue draft
  generateIssueDraft: (id: string, format: "github" | "jira" = "github", force = false) =>
    request<IssueDraft>(`/runs/${id}/issue-draft`, {
      method: "POST",
      body: JSON.stringify({ format, force }),
    }),
}
