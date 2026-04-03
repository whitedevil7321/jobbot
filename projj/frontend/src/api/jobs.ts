import api from './client'

export interface Job {
  id: number
  source: string
  url: string
  title: string
  company?: string
  location?: string
  remote: boolean
  salary_min?: number
  salary_max?: number
  currency: string
  description?: string
  required_exp?: number
  skills_required?: string[]
  domain?: string
  visa_sponsorship: string
  easy_apply: boolean
  filter_score: number
  priority: number
  status: string
  scraped_at?: string
}

export interface Application {
  id: number
  job_id: number
  attempt_number: number
  status: string
  stuck_reason?: string
  cover_letter_text?: string
  error_message?: string
  screenshot_path?: string
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface AppStats {
  total: number
  pending: number
  in_progress: number
  submitted: number
  stuck: number
  skipped: number
  failed: number
}

export const jobsApi = {
  list: (params?: Record<string, any>) => api.get('/jobs', { params }),
  get: (id: number) => api.get(`/jobs/${id}`),
  submitManual: (url: string, title?: string, company?: string) =>
    api.post('/jobs/manual', { url, title, company }),
  delete: (id: number) => api.delete(`/jobs/${id}`),
  prioritize: (id: number) => api.patch(`/jobs/${id}/priority`),
}

export const applicationsApi = {
  list: (params?: Record<string, any>) => api.get('/applications', { params }),
  stats: () => api.get<AppStats>('/applications/stats'),
  get: (id: number) => api.get(`/applications/${id}`),
  decide: (id: number, action: 'skip' | 'retry' | 'manual') =>
    api.patch(`/applications/${id}/decision`, { action }),
}
