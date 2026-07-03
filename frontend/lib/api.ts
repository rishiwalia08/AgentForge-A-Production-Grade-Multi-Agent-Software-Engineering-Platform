// API Client for the Agent Platform backend
export const API_BASE_URL = typeof window !== 'undefined' 
  ? (window.location.origin.includes('localhost') ? 'http://localhost:8000' : '') 
  : 'http://localhost:8000';

export const WS_BASE_URL = typeof window !== 'undefined'
  ? (window.location.origin.includes('localhost') ? 'ws://localhost:8000' : '')
  : 'ws://localhost:8000';

function getHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('agent_jwt') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
}

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...getHeaders(),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = 'API Request Failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

// Authentication
export interface LoginResponse {
  access_token: string;
}

export async function loginWithGoogle(idToken: string): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/google-login', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  });
}

// Projects
export interface Project {
  id: string;
  name: string;
  description: string;
  repo_path?: string;
  created_at: string;
}

export async function getProjects(): Promise<Project[]> {
  return request<Project[]>('/projects');
}

export async function createProject(name: string, description: string, repoPath?: string): Promise<Project> {
  return request<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description, repo_path: repoPath }),
  });
}

export async function deleteProject(id: string): Promise<void> {
  await request<void>(`/projects/${id}`, {
    method: 'DELETE',
  });
}

// Runs
export interface RunCreateResponse {
  run_id: string;
  thread_id: string;
}

export interface RunDetails {
  status: string;
  current_agent: string;
  timeline: TimelineStep[];
  trace: TraceRecord[];
}

export interface TimelineStep {
  agent: string;
  decision?: string;
  tool?: string;
  timestamp: string;
  details?: string;
}

export interface TraceRecord {
  id: string;
  agent: string;
  parent_trace_id: string | null;
  tool_called: string | null;
  status: string;
  latency: number;
  timestamp: string;
}

export async function createRun(projectId: string, task: string): Promise<RunCreateResponse> {
  return request<RunCreateResponse>('/runs/create', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, task }),
  });
}

export async function getRunDetails(runId: string): Promise<RunDetails> {
  return request<RunDetails>(`/runs/${runId}`);
}

export async function resumeRun(runId: string, approved: boolean, feedback?: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/runs/${runId}/resume`, {
    method: 'POST',
    body: JSON.stringify({ approved, feedback }),
  });
}

// Observability
export interface MetricSummary {
  run_id: string;
  total_steps: number;
  avg_latency: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  total_tokens: number;
  errors_detected: string[];
  human_checks: number;
}

export async function getRunMetrics(runId: string): Promise<MetricSummary> {
  return request<MetricSummary>(`/observability/metrics/${runId}`);
}

export async function getRunReflections(runId: string): Promise<any[]> {
  return request<any[]>(`/observability/reflection/${runId}`);
}

// Memories
export interface MemoryItem {
  id: string;
  kind: string;
  content: string;
  created_at: string;
  metadata_json?: any;
}

export async function getMemoryItems(): Promise<MemoryItem[]> {
  return request<MemoryItem[]>('/observability/memory');
}
