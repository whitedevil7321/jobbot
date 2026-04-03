import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { filtersApi, FilterConfig } from '../api/filters'
import { Filter, X } from 'lucide-react'

const PORTALS = ['linkedin', 'indeed', 'remoteok', 'remotive', 'arbeitnow', 'themuse']
const JOB_TYPES = ['full-time', 'part-time', 'contract', 'internship', 'temporary']
const VISA_OPTIONS = [
  { value: 'any', label: 'Any (don\'t filter by sponsorship)' },
  { value: 'required', label: 'Must offer visa sponsorship' },
  { value: 'not_required', label: 'Does not need sponsorship' },
]

function TagInput({ label, value, onChange, placeholder }: { label: string; value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState('')
  const add = () => {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) onChange([...value, trimmed])
    setInput('')
  }
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex flex-wrap gap-1.5 p-2 bg-gray-800 border border-gray-700 rounded-lg min-h-[40px]">
        {value.map(v => (
          <span key={v} className="badge-blue flex items-center gap-1 text-xs">
            {v} <button onClick={() => onChange(value.filter(x => x !== v))}><X size={10} /></button>
          </span>
        ))}
        <input
          className="flex-1 min-w-[120px] bg-transparent text-sm text-gray-100 outline-none placeholder-gray-600"
          placeholder={placeholder || `Add...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() } }}
        />
      </div>
    </div>
  )
}

const EMPTY: FilterConfig = {
  name: 'default', is_active: true, locations: [], min_years_exp: 0, max_years_exp: 15,
  job_types: ['full-time'], domains: [], required_skills: [], excluded_keywords: [],
  work_auth_required: [], visa_sponsorship_filter: 'any', salary_min: undefined, salary_max: undefined,
  portals: [...PORTALS],
}

export default function Filters() {
  const qc = useQueryClient()
  const [form, setForm] = useState<FilterConfig>(EMPTY)
  const [saved, setSaved] = useState(false)
  const [testResult, setTestResult] = useState<any>(null)

  const { data } = useQuery({
    queryKey: ['filters'],
    queryFn: () => filtersApi.get().then(r => r.data).catch(() => EMPTY),
  })

  useEffect(() => { if (data) setForm({ ...EMPTY, ...data }) }, [data])

  const saveMutation = useMutation({
    mutationFn: () => filtersApi.save(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['filters'] }); setSaved(true); setTimeout(() => setSaved(false), 2000) },
  })

  const testMutation = useMutation({
    mutationFn: () => filtersApi.test(form),
    onSuccess: (r) => setTestResult(r.data),
  })

  const set = (k: keyof FilterConfig, v: any) => setForm(f => ({ ...f, [k]: v }))
  const togglePortal = (p: string) => set('portals', (form.portals || []).includes(p) ? (form.portals || []).filter(x => x !== p) : [...(form.portals || []), p])
  const toggleJobType = (t: string) => set('job_types', (form.job_types || []).includes(t) ? (form.job_types || []).filter(x => x !== t) : [...(form.job_types || []), t])

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <Filter className="text-violet-400" size={22} /> Job Filters
      </h1>
      <p className="text-gray-500 text-sm">These filters are applied when scraping and scoring jobs. Jobs that don't match will not be auto-applied.</p>

      {/* Job Portals */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">Job Portals</h2>
        <div className="flex flex-wrap gap-2">
          {PORTALS.map(p => (
            <button
              key={p}
              onClick={() => togglePortal(p)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize ${(form.portals || []).includes(p) ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Locations */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">Locations</h2>
        <TagInput label="Target Locations" value={form.locations || []} onChange={v => set('locations', v)} placeholder="e.g. Remote, New York, NY, San Francisco..." />
        <p className="text-xs text-gray-600">Add 'Remote' to include remote jobs</p>
      </div>

      {/* Experience */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">Experience</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Min Years of Experience</label>
            <input className="input" type="number" min={0} value={form.min_years_exp} onChange={e => set('min_years_exp', Number(e.target.value))} />
          </div>
          <div>
            <label className="label">Max Years of Experience</label>
            <input className="input" type="number" min={0} value={form.max_years_exp} onChange={e => set('max_years_exp', Number(e.target.value))} />
          </div>
        </div>
      </div>

      {/* Job Types */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">Job Types</h2>
        <div className="flex flex-wrap gap-2">
          {JOB_TYPES.map(t => (
            <button key={t} onClick={() => toggleJobType(t)} className={`px-3 py-1.5 rounded-lg text-sm capitalize transition-colors ${(form.job_types || []).includes(t) ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>{t}</button>
          ))}
        </div>
      </div>

      {/* Domain / Keywords */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Keywords & Skills</h2>
        <TagInput label="Domains / Fields" value={form.domains || []} onChange={v => set('domains', v)} placeholder="Backend, ML, DevOps, Data..." />
        <TagInput label="Required Skills (must have ALL)" value={form.required_skills || []} onChange={v => set('required_skills', v)} placeholder="Python, React, AWS..." />
        <TagInput label="Exclude Keywords (in title)" value={form.excluded_keywords || []} onChange={v => set('excluded_keywords', v)} placeholder="Senior, Director, Principal..." />
      </div>

      {/* Work Authorization */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Work Authorization</h2>
        <div>
          <label className="label">Visa Sponsorship Filter</label>
          <select className="input" value={form.visa_sponsorship_filter} onChange={e => set('visa_sponsorship_filter', e.target.value)}>
            {VISA_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Salary */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Salary Range (optional)</h2>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Minimum ($)</label><input className="input" type="number" value={form.salary_min || ''} onChange={e => set('salary_min', e.target.value ? Number(e.target.value) : undefined)} /></div>
          <div><label className="label">Maximum ($)</label><input className="input" type="number" value={form.salary_max || ''} onChange={e => set('salary_max', e.target.value ? Number(e.target.value) : undefined)} /></div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button className="btn-primary flex-1 py-3" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? 'Saving...' : saved ? '✓ Saved!' : 'Save Filters'}
        </button>
        <button className="btn-secondary px-6" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
          {testMutation.isPending ? 'Testing...' : 'Test Filter'}
        </button>
      </div>

      {testResult && (
        <div className="card border-violet-800/50 bg-violet-950/20">
          <p className="text-sm text-gray-300">
            With these filters: <span className="font-bold text-violet-300">{testResult.would_pass}</span> of <span className="text-gray-400">{testResult.jobs_in_db}</span> existing jobs would pass.
          </p>
        </div>
      )}
    </div>
  )
}
