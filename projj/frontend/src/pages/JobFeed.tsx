import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../api/jobs'
import { useWebSocket } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import { ExternalLink, Zap, Send, Trash2, ArrowUp } from 'lucide-react'

const SOURCES = ['all', 'linkedin', 'indeed', 'glassdoor', 'ziprecruiter', 'dice', 'monster', 'telegram', 'manual']
const STATUSES = ['all', 'new', 'queued', 'applying', 'applied', 'skipped', 'failed']

export default function JobFeed() {
  const qc = useQueryClient()
  const [source, setSource] = useState('all')
  const [status, setStatus] = useState('all')
  const [minScore, setMinScore] = useState(0)
  const [manualUrl, setManualUrl] = useState('')
  const [page, setPage] = useState(1)

  const params: Record<string, any> = { page, limit: 30, sort_by: 'scraped_at' }
  if (source !== 'all') params.source = source
  if (status !== 'all') params.status = status
  if (minScore > 0) params.min_score = minScore

  const { data, isLoading } = useQuery({
    queryKey: ['jobs', params],
    queryFn: () => jobsApi.list(params).then(r => r.data),
    refetchInterval: 15000,
  })

  const handleWsMsg = useCallback((msg: any) => {
    if (msg.type === 'new_job') qc.invalidateQueries({ queryKey: ['jobs'] })
  }, [qc])
  useWebSocket(handleWsMsg)

  const submitMutation = useMutation({
    mutationFn: () => jobsApi.submitManual(manualUrl),
    onSuccess: () => {
      setManualUrl('')
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => jobsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const prioritizeMutation = useMutation({
    mutationFn: (id: number) => jobsApi.prioritize(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Zap className="text-violet-400" size={22} /> Job Feed
        </h1>
        <span className="text-gray-500 text-sm">{data?.total ?? 0} jobs</span>
      </div>

      {/* Manual URL submit */}
      <div className="card">
        <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">Submit a Job URL</p>
        <div className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="https://linkedin.com/jobs/view/... or any job URL"
            value={manualUrl}
            onChange={e => setManualUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && manualUrl && submitMutation.mutate()}
          />
          <button
            className="btn-primary flex items-center gap-2"
            disabled={!manualUrl || submitMutation.isPending}
            onClick={() => submitMutation.mutate()}
          >
            <Send size={14} />
            {submitMutation.isPending ? 'Adding...' : 'Apply'}
          </button>
        </div>
        {submitMutation.isSuccess && (
          <p className="text-emerald-400 text-xs mt-2">Job added to priority queue!</p>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div>
          <label className="label">Source</label>
          <select className="input w-40" value={source} onChange={e => { setSource(e.target.value); setPage(1) }}>
            {SOURCES.map(s => <option key={s} value={s}>{s === 'all' ? 'All Sources' : s}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Status</label>
          <select className="input w-36" value={status} onChange={e => { setStatus(e.target.value); setPage(1) }}>
            {STATUSES.map(s => <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Min Score</label>
          <select className="input w-32" value={minScore} onChange={e => { setMinScore(Number(e.target.value)); setPage(1) }}>
            {[0, 30, 50, 70, 90].map(v => <option key={v} value={v}>{v === 0 ? 'Any' : `${v}%+`}</option>)}
          </select>
        </div>
      </div>

      {/* Job list */}
      <div className="space-y-2">
        {isLoading && (
          <div className="text-center py-12 text-gray-500">Loading jobs...</div>
        )}
        {!isLoading && data?.jobs?.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No jobs found. Adjust filters or trigger a scrape.
          </div>
        )}
        {data?.jobs?.map((job: any) => (
          <div key={job.id} className="card hover:border-gray-700 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-white text-sm">{job.title}</span>
                  {job.remote && <span className="badge-green text-[10px]">Remote</span>}
                  {job.priority === 1 && <span className="badge-purple text-[10px]">Priority</span>}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {job.company && <span>{job.company} · </span>}
                  {job.location && <span>{job.location} · </span>}
                  <span className="uppercase tracking-wide">{job.source}</span>
                  {(job.salary_min || job.salary_max) && (
                    <span> · ${job.salary_min ? (job.salary_min / 1000).toFixed(0) + 'k' : '?'} – ${job.salary_max ? (job.salary_max / 1000).toFixed(0) + 'k' : '?'}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs font-mono text-violet-400">{Math.round(job.filter_score)}%</span>
                <StatusBadge status={job.status} />
                <button
                  className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-violet-400 transition-colors"
                  title="Prioritize"
                  onClick={() => prioritizeMutation.mutate(job.id)}
                >
                  <ArrowUp size={14} />
                </button>
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-blue-400 transition-colors"
                >
                  <ExternalLink size={14} />
                </a>
                <button
                  className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-red-400 transition-colors"
                  onClick={() => deleteMutation.mutate(job.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            {job.skills_required?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {job.skills_required.slice(0, 6).map((s: string) => (
                  <span key={s} className="badge-gray text-[10px]">{s}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {data && data.total > 30 && (
        <div className="flex justify-center gap-3 pt-2">
          <button className="btn-secondary" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span className="text-gray-500 text-sm py-2">Page {page} / {Math.ceil(data.total / 30)}</span>
          <button className="btn-secondary" disabled={page * 30 >= data.total} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}
    </div>
  )
}
