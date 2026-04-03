import api from './client'

export interface UserProfile {
  id?: number
  full_name: string
  email: string
  phone?: string
  location?: string
  linkedin_url?: string
  github_url?: string
  portfolio_url?: string
  years_of_exp: number
  work_auth: string
  visa_sponsorship_needed: boolean
  target_roles?: string[]
  target_domains?: string[]
  skills?: string[]
  summary?: string
  address?: string
  city?: string
  state?: string
  zip_code?: string
  country?: string
  highest_education?: string
  school_name?: string
  graduation_year?: number
  degree?: string
  gender?: string
  ethnicity?: string
  veteran_status?: string
  disability_status?: string
  desired_salary_min?: number
  desired_salary_max?: number
  salary_currency?: string
  resume_path?: string
}

export const profileApi = {
  get: () => api.get<UserProfile>('/profile'),
  save: (data: UserProfile) => api.post<UserProfile>('/profile', data),
  uploadResume: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/profile/resume', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
