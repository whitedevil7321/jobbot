import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { profileApi, UserProfile } from '../api/profile'
import { User, Upload, Plus, X } from 'lucide-react'

const WORK_AUTH_OPTIONS = [
  { value: 'citizen', label: 'US Citizen' },
  { value: 'greencard', label: 'Green Card' },
  { value: 'h1b', label: 'H-1B Visa' },
  { value: 'opt', label: 'OPT / STEM OPT' },
  { value: 'tn', label: 'TN Visa' },
  { value: 'other', label: 'Other' },
]

function TagInput({ label, value, onChange }: { label: string; value: string[]; onChange: (v: string[]) => void }) {
  const [input, setInput] = useState('')
  const add = () => {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setInput('')
  }
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex flex-wrap gap-1.5 p-2 bg-gray-800 border border-gray-700 rounded-lg min-h-[40px]">
        {value.map(v => (
          <span key={v} className="badge-purple flex items-center gap-1">
            {v}
            <button onClick={() => onChange(value.filter(x => x !== v))} className="hover:text-white"><X size={10} /></button>
          </span>
        ))}
        <input
          className="flex-1 min-w-[120px] bg-transparent text-sm text-gray-100 outline-none placeholder-gray-600"
          placeholder={`Add ${label.toLowerCase()}...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() } }}
        />
      </div>
    </div>
  )
}

const EMPTY: UserProfile = {
  full_name: '', email: '', phone: '', location: '', linkedin_url: '', github_url: '',
  portfolio_url: '', years_of_exp: 0, work_auth: 'citizen', visa_sponsorship_needed: false,
  target_roles: [], target_domains: [], skills: [], summary: '', address: '', city: '', state: '',
  zip_code: '', country: 'United States', highest_education: '', school_name: '', graduation_year: undefined,
  degree: '', desired_salary_min: undefined, desired_salary_max: undefined, salary_currency: 'USD',
}

export default function Profile() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<UserProfile>(EMPTY)
  const [saved, setSaved] = useState(false)

  const { data } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.get().then(r => r.data),
  })

  useEffect(() => {
    if (data) setForm({ ...EMPTY, ...data })
  }, [data])

  const saveMutation = useMutation({
    mutationFn: () => profileApi.save(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => profileApi.uploadResume(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })

  const set = (k: keyof UserProfile, v: any) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <User className="text-violet-400" size={22} /> My Profile
      </h1>

      {/* Resume Upload */}
      <div className="card">
        <h2 className="font-semibold text-white mb-3">Resume</h2>
        <div className="flex items-center gap-4">
          <button onClick={() => fileRef.current?.click()} className="btn-secondary flex items-center gap-2">
            <Upload size={14} /> Upload Resume (PDF/DOCX)
          </button>
          {form.resume_path && (
            <span className="text-xs text-emerald-400">✓ {form.resume_path.split('/').pop()}</span>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.doc"
            className="hidden"
            onChange={e => { if (e.target.files?.[0]) uploadMutation.mutate(e.target.files[0]) }}
          />
        </div>
        {uploadMutation.isPending && <p className="text-xs text-gray-500 mt-2">Uploading & extracting text...</p>}
        {uploadMutation.isSuccess && <p className="text-xs text-emerald-400 mt-2">Resume uploaded!</p>}
      </div>

      {/* Personal Info */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Personal Information</h2>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Full Name</label><input className="input" value={form.full_name} onChange={e => set('full_name', e.target.value)} /></div>
          <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={e => set('email', e.target.value)} /></div>
          <div><label className="label">Phone</label><input className="input" value={form.phone || ''} onChange={e => set('phone', e.target.value)} /></div>
          <div><label className="label">Location (City, State)</label><input className="input" value={form.location || ''} onChange={e => set('location', e.target.value)} /></div>
          <div><label className="label">Address</label><input className="input" value={form.address || ''} onChange={e => set('address', e.target.value)} /></div>
          <div><label className="label">City</label><input className="input" value={form.city || ''} onChange={e => set('city', e.target.value)} /></div>
          <div><label className="label">State</label><input className="input" value={form.state || ''} onChange={e => set('state', e.target.value)} /></div>
          <div><label className="label">ZIP Code</label><input className="input" value={form.zip_code || ''} onChange={e => set('zip_code', e.target.value)} /></div>
        </div>
      </div>

      {/* Professional */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Professional Details</h2>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">LinkedIn URL</label><input className="input" value={form.linkedin_url || ''} onChange={e => set('linkedin_url', e.target.value)} /></div>
          <div><label className="label">GitHub URL</label><input className="input" value={form.github_url || ''} onChange={e => set('github_url', e.target.value)} /></div>
          <div><label className="label">Portfolio / Website</label><input className="input" value={form.portfolio_url || ''} onChange={e => set('portfolio_url', e.target.value)} /></div>
          <div><label className="label">Years of Experience</label><input className="input" type="number" min={0} value={form.years_of_exp} onChange={e => set('years_of_exp', Number(e.target.value))} /></div>
          <div>
            <label className="label">Work Authorization</label>
            <select className="input" value={form.work_auth} onChange={e => set('work_auth', e.target.value)}>
              {WORK_AUTH_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-3 pt-5">
            <input type="checkbox" id="visa" className="w-4 h-4 accent-violet-500" checked={form.visa_sponsorship_needed} onChange={e => set('visa_sponsorship_needed', e.target.checked)} />
            <label htmlFor="visa" className="text-sm text-gray-300">Require visa sponsorship</label>
          </div>
        </div>
        <div>
          <label className="label">Professional Summary</label>
          <textarea className="input h-24 resize-none" value={form.summary || ''} onChange={e => set('summary', e.target.value)} placeholder="Brief professional summary used in cover letters..." />
        </div>
        <TagInput label="Skills" value={form.skills || []} onChange={v => set('skills', v)} />
        <TagInput label="Target Roles" value={form.target_roles || []} onChange={v => set('target_roles', v)} />
        <TagInput label="Target Domains" value={form.target_domains || []} onChange={v => set('target_domains', v)} />
      </div>

      {/* Education */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Education</h2>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">School / University</label><input className="input" value={form.school_name || ''} onChange={e => set('school_name', e.target.value)} /></div>
          <div><label className="label">Degree</label><input className="input" value={form.degree || ''} onChange={e => set('degree', e.target.value)} /></div>
          <div><label className="label">Graduation Year</label><input className="input" type="number" value={form.graduation_year || ''} onChange={e => set('graduation_year', Number(e.target.value))} /></div>
          <div><label className="label">Highest Education</label><input className="input" value={form.highest_education || ''} onChange={e => set('highest_education', e.target.value)} /></div>
        </div>
      </div>

      {/* Salary */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Salary Expectations</h2>
        <div className="grid grid-cols-3 gap-4">
          <div><label className="label">Minimum ($)</label><input className="input" type="number" value={form.desired_salary_min || ''} onChange={e => set('desired_salary_min', Number(e.target.value))} /></div>
          <div><label className="label">Maximum ($)</label><input className="input" type="number" value={form.desired_salary_max || ''} onChange={e => set('desired_salary_max', Number(e.target.value))} /></div>
          <div><label className="label">Currency</label><input className="input" value={form.salary_currency || 'USD'} onChange={e => set('salary_currency', e.target.value)} /></div>
        </div>
      </div>

      {/* EEO */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">EEO / Demographics <span className="text-xs text-gray-500 font-normal">(optional — used for voluntary disclosure forms)</span></h2>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Gender</label><input className="input" value={form.gender || ''} onChange={e => set('gender', e.target.value)} placeholder="Prefer not to say" /></div>
          <div><label className="label">Ethnicity</label><input className="input" value={form.ethnicity || ''} onChange={e => set('ethnicity', e.target.value)} placeholder="Prefer not to say" /></div>
          <div><label className="label">Veteran Status</label><input className="input" value={form.veteran_status || ''} onChange={e => set('veteran_status', e.target.value)} placeholder="I am not a veteran" /></div>
          <div><label className="label">Disability Status</label><input className="input" value={form.disability_status || ''} onChange={e => set('disability_status', e.target.value)} placeholder="I don't wish to answer" /></div>
        </div>
      </div>

      <button
        className="btn-primary w-full py-3 text-base"
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
      >
        {saveMutation.isPending ? 'Saving...' : saved ? '✓ Saved!' : 'Save Profile'}
      </button>
    </div>
  )
}
