import api from './client'

export interface FilterConfig {
  id?: number
  name: string
  is_active?: boolean
  locations?: string[]
  min_years_exp: number
  max_years_exp: number
  job_types?: string[]
  domains?: string[]
  required_skills?: string[]
  excluded_keywords?: string[]
  work_auth_required?: string[]
  visa_sponsorship_filter: string
  salary_min?: number
  salary_max?: number
  portals?: string[]
}

export const filtersApi = {
  get: () => api.get<FilterConfig>('/filters'),
  save: (data: FilterConfig) => api.post<FilterConfig>('/filters', data),
  update: (data: Partial<FilterConfig>) => api.patch<FilterConfig>('/filters', data),
  test: (data: FilterConfig) => api.post('/filters/test', data),
}

export const ollamaApi = {
  status: () => api.get('/ollama/status'),
  models: () => api.get('/ollama/models'),
  setModel: (model_name: string) => api.patch('/ollama/models/active', { model_name }),
}

export const telegramApi = {
  config: () => api.get('/telegram/config'),
  save: (bot_token: string, chat_id: string) => api.post('/telegram/config', { bot_token, chat_id }),
  test: () => api.post('/telegram/test'),
  status: () => api.get('/telegram/status'),
}

export const schedulerApi = {
  status: () => api.get('/scheduler/status'),
  triggerScrape: () => api.post('/scheduler/scrape/trigger'),
  triggerApply: () => api.post('/scheduler/apply/trigger'),
  updateConfig: (data: { scrape_interval_minutes?: number; auto_apply?: boolean }) =>
    api.patch('/scheduler/config', data),
  logs: () => api.get('/scheduler/logs'),
}
