import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../api/jobs'
import { useWebSocket } from '../hooks/useWebSocket'
import api from '../api/client'
import {
  Zap, MapPin, Building2, DollarSign, Clock, CheckCircle2,
  XCircle, AlertTriangle, Play, SkipForward, ExternalLink,
  ChevronDown, ChevronUp, Briefcase, Star, Wifi, Search,
  Filter, SlidersHorizontal, RefreshCw, ArrowRight,
} from 'lucide-react'
import { clsx } from 'clsx'

/* ─── Types ─── */
interface Job {
  id: number; source: string; url: string; title: string
  company?: string; location?: string; remote: boolean
  salary_min?: number; salary_max?: number; currency: string
  description?: string; required_exp?: number
  skills_required?: string[]; domain?: string
  visa_sponsorship: string; easy_apply: boolean
  filter_score: number; priority: number; status: string
  scraped_at?: string
}

/* ─── Status config ─── */
const STATUS_CFG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  new:         { label: 'New',        color: 'text-gray-400',    bg: 'bg-gray-800',         icon: Clock },
  queued:      { label: 'In Queue',   color: 'text-blue-400',    bg: 'bg-blue-950/60',      icon: Clock },
  applying:    { label: 'Applying…',  color: 'text-violet-400',  bg: 'bg-violet-950/60',    icon: RefreshCw },
  applied:     { label: 'Applied',    color: 'text-emerald-400', bg: 'bg-emerald-950/60',   icon: CheckCircle2 },
  submitted:   { label: 'Submitted',  color: 'text-emerald-400', bg: 'bg-emerald-950/60',   icon: CheckCircle2 },
  stuck:       { label: 'Stuck',      color: 'text-amber-400',   bg: 'bg-amber-950/60',     icon: AlertTriangle },
  skipped:     { label: 'Skipped',    color: 'text-gray-500',    bg: 'bg-gray-800',         icon: SkipForward },
  failed:      { label: 'Failed',     color: 'text-red-400',     bg: 'bg-red-950/60',       icon: XCircle },
}

/* ─── Score ring ─── */
function ScoreRing({ score }: { score: number }) {
  const r = 18, c = 2 * Math.PI * r
  const fill = (score / 100) * c
  const color = score >= 70 ? '#34d399' : score >= 40 ? '#a78bfa' : '#f59e0b'
  return (
    <div className="relative w-12 h-12 shrink-0">
      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={r} fill="none" stroke="#1f2937" strokeWidth="4" />
        <circle cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${fill} ${c}`} strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease' }} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-xs font-bold" style={{ color }}>
        {Math.round(score)}
      </span>
    </div>
  )
}

/* ─── Company avatar ─── */
function CompanyAvatar({ name, source }: { name?: string; source: string }) {
  const initials = name ? name.slice(0, 2).toUpperCase() : source.slice(0, 2).toUpperCase()
  const colors = [
    'from-violet-600 to-indigo-600', 'from-blue-600 to-cyan-600',
    'from-emerald-600 to-teal-600',  'from-orange-600 to-red-600',
    'from-pink-600 to-rose-600',     'from-amber-600 to-yellow-600',
  ]
  const idx = (name || source).charCodeAt(0) % colors.length
  return (
    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colors[idx]} flex items-center justify-center text-white text-sm font-bold shrink-0`}>
      {initials}
    </div>
  )
}

/* ─── Single Job Card ─── */
function JobCard({ job, onApply, onSkip, applying }: {
  job: Job
  onApply: (id: number) => void
  onSkip: (id: number) => void
  applying: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CFG[job.status] ?? STATUS_CFG.new
  const StatusIcon = cfg.icon
  const isApplied  = ['applied', 'submitted'].includes(job.status)
  const isApplying = job.status === 'applying' || applying
  const isSkipped  = ['skipped', 'failed'].includes(job.status)

  return (
    <div className={clsx(
      'group relative rounded-2xl border transition-all duration-200',
      'bg-gradient-to-br from-gray-900 to-gray-900/80',
      isApplied  ? 'border-emerald-800/60 shadow-emerald-900/20 shadow-lg' :
      isApplying ? 'border-violet-700/60 shadow-violet-900/20 shadow-lg animate-pulse-border' :
      job.status === 'stuck' ? 'border-amber-700/60' :
      'border-gray-800 hover:border-gray-700',
    )}>
      {/* Priority ribbon */}
      {job.priority === 1 && (
        <div className="absolute -top-px left-4 right-4 h-0.5 bg-gradient-to-r from-violet-500 to-blue-500 rounded-full" />
      )}

      <div className="p-4">
        {/* Top row */}
        <div className="flex items-start gap-3">
          <CompanyAvatar name={job.company} source={job.source} />

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="font-semibold text-white text-sm leading-tight truncate pr-2">
                  {job.title}
                </h3>
                <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                  {job.company && (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Building2 size={10} /> {job.company}
                    </span>
                  )}
                  {job.location && (
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <MapPin size={10} /> {job.location}
                    </span>
                  )}
                  {job.remote && (
                    <span className="flex items-center gap-1 text-xs text-emerald-500">
                      <Wifi size={10} /> Remote
                    </span>
                  )}
                </div>
              </div>
              <ScoreRing score={job.filter_score} />
            </div>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          {/* Salary */}
          {(job.salary_min || job.salary_max) && (
            <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded-lg">
              <DollarSign size={10} />
              {job.salary_min ? `$${(job.salary_min / 1000).toFixed(0)}k` : '?'}
              {' – '}
              {job.salary_max ? `$${(job.salary_max / 1000).toFixed(0)}k` : '?'}
            </span>
          )}
          {/* Source badge */}
          <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600 bg-gray-800/50 px-2 py-1 rounded-lg">
            {job.source}
          </span>
          {/* Priority */}
          {job.priority === 1 && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-violet-400 bg-violet-950/60 px-2 py-1 rounded-lg">
              <Star size={9} /> Priority
            </span>
          )}
          {/* Status pill */}
          <span className={clsx('flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg ml-auto', cfg.bg, cfg.color)}>
            <StatusIcon size={11} className={isApplying ? 'animate-spin' : ''} />
            {cfg.label}
          </span>
        </div>

        {/* Skills */}
        {job.skills_required && job.skills_required.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2.5">
            {job.skills_required.slice(0, 5).map((s: string) => (
              <span key={s} className="text-[10px] px-2 py-0.5 rounded-md bg-gray-800 text-gray-400 border border-gray-700/50">
                {s}
              </span>
            ))}
            {job.skills_required.length > 5 && (
              <span className="text-[10px] px-2 py-0.5 rounded-md bg-gray-800 text-gray-500">
                +{job.skills_required.length - 5}
              </span>
            )}
          </div>
        )}

        {/* Description expand */}
        {job.description && (
          <div className="mt-2.5">
            <button
              onClick={() => setExpanded(e => !e)}
              className="flex items-center gap-1 text-[11px] text-gray-600 hover:text-gray-400 transition-colors"
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {expanded ? 'Hide description' : 'View description'}
            </button>
            {expanded && (
              <p className="mt-2 text-xs text-gray-500 leading-relaxed line-clamp-6 bg-gray-800/40 rounded-lg p-3">
                {job.description?.replace(/<[^>]*>/g, '').slice(0, 600)}…
              </p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-800/80">
          {!isApplied && !isSkipped && (
            <>
              <button
                onClick={() => onApply(job.id)}
                disabled={isApplying}
                className={clsx(
                  'flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium transition-all duration-150',
                  isApplying
                    ? 'bg-violet-900/40 text-violet-400 cursor-wait'
                    : 'bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-900/30 hover:shadow-violet-900/50 active:scale-95',
                )}
              >
                {isApplying ? (
                  <><RefreshCw size={14} className="animate-spin" /> Applying…</>
                ) : (
                  <><Zap size={14} /> Apply Now</>
                )}
              </button>
              <button
                onClick={() => onSkip(job.id)}
                disabled={isApplying}
                className="p-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-colors"
                title="Skip this job"
              >
                <SkipForward size={14} />
              </button>
            </>
          )}

          {isApplied && (
            <div className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl bg-emerald-950/40 text-emerald-400 text-sm font-medium border border-emerald-800/40">
              <CheckCircle2 size={14} /> Application Submitted
            </div>
          )}

          {isSkipped && (
            <div className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl bg-gray-800/60 text-gray-500 text-sm">
              <SkipForward size={14} /> Skipped
            </div>
          )}

          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-blue-400 transition-colors"
            title="View job"
          >
            <ExternalLink size={14} />
          </a>
        </div>
      </div>
    </div>
  )
}

/* ─── Stats bar ─── */
function StatsBar({ jobs }: { jobs: Job[] }) {
  const counts = jobs.reduce((acc, j) => {
    acc[j.status] = (acc[j.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const total    = jobs.length
  const applied  = (counts.applied || 0) + (counts.submitted || 0)
  const pending  = (counts.queued || 0) + (counts.applying || 0)
  const remaining = (counts.new || 0)
  const pct      = total ? Math.round((applied / total) * 100) : 0

  return (
    <div className="card mb-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-white">
          Application Progress
        </span>
        <span className="text-sm font-bold text-white">{pct}%</span>
      </div>
      {/* Progress bar */}
      <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden mb-4">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-emerald-500 rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total',    value: total,     color: 'text-white' },
          { label: 'Applied',  value: applied,   color: 'text-emerald-400' },
          { label: 'Pending',  value: pending,   color: 'text-blue-400' },
          { label: 'Remaining',value: remaining, color: 'text-gray-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="text-center py-2 rounded-xl bg-gray-800/60">
            <div className={`text-xl font-bold ${color}`}>{value}</div>
            <div className="text-[10px] text-gray-600 mt-0.5 uppercase tracking-wide">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── Main page ─── */
export default function ApplyQueue() {
  const qc = useQueryClient()
  const [search, setSearch]   = useState('')
  const [filter, setFilter]   = useState('all') // all | new | applied | stuck
  const [applying, setApplying] = useState<Set<number>>(new Set())
  const [applyingAll, setApplyingAll] = useState(false)
  const stopRef = useRef(false)

  const { data, isLoading } = useQuery({
    queryKey: ['apply-queue-jobs'],
    queryFn: () => jobsApi.list({ limit: 200, sort_by: 'filter_score' }).then(r => r.data),
    refetchInterval: 5000,
  })

  // Live updates via WebSocket
  useWebSocket(useCallback((msg: any) => {
    if (['new_job', 'job_updated', 'app_status'].includes(msg.type)) {
      qc.invalidateQueries({ queryKey: ['apply-queue-jobs'] })
    }
  }, [qc]))

  const applyOne = async (jobId: number) => {
    setApplying(s => new Set(s).add(jobId))
    try {
      await api.post(`/jobs/${jobId}/apply`)
      qc.invalidateQueries({ queryKey: ['apply-queue-jobs'] })
    } catch (e) {
      console.error(e)
    } finally {
      setApplying(s => { const n = new Set(s); n.delete(jobId); return n })
    }
  }

  const skipOne = async (jobId: number) => {
    await api.delete(`/jobs/${jobId}`)
    qc.invalidateQueries({ queryKey: ['apply-queue-jobs'] })
  }

  const applyAll = async () => {
    stopRef.current = false
    setApplyingAll(true)
    try {
      await api.post('/jobs/apply-all')
      qc.invalidateQueries({ queryKey: ['apply-queue-jobs'] })
    } catch (e) {
      console.error(e)
    } finally {
      setApplyingAll(false)
    }
  }

  const stopAll = () => { stopRef.current = true; setApplyingAll(false) }

  const allJobs: Job[] = data?.jobs ?? []

  const filtered = allJobs.filter(j => {
    const matchSearch = !search || [j.title, j.company, j.location].some(
      f => f?.toLowerCase().includes(search.toLowerCase())
    )
    const matchFilter =
      filter === 'all'     ? true :
      filter === 'new'     ? j.status === 'new' :
      filter === 'applied' ? ['applied', 'submitted'].includes(j.status) :
      filter === 'stuck'   ? j.status === 'stuck' :
      filter === 'pending' ? ['queued', 'applying'].includes(j.status) : true
    return matchSearch && matchFilter
  })

  const tabs = [
    { key: 'all',     label: 'All',      count: allJobs.length },
    { key: 'new',     label: 'New',      count: allJobs.filter(j => j.status === 'new').length },
    { key: 'pending', label: 'Applying', count: allJobs.filter(j => ['queued','applying'].includes(j.status)).length },
    { key: 'applied', label: 'Applied',  count: allJobs.filter(j => ['applied','submitted'].includes(j.status)).length },
    { key: 'stuck',   label: 'Stuck',    count: allJobs.filter(j => j.status === 'stuck').length },
  ]

  return (
    <div className="min-h-screen bg-gray-950">
      {/* ── Header ── */}
      <div className="sticky top-0 z-20 bg-gray-950/95 backdrop-blur-sm border-b border-gray-800/80 px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <div className="w-7 h-7 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <Zap size={14} className="text-white" />
              </div>
              Apply Queue
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              AI fills all forms using your profile + generates answers for unknown fields
            </p>
          </div>

          <div className="flex items-center gap-3">
            {applyingAll ? (
              <button
                onClick={stopAll}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-900/40 hover:bg-red-900/60 text-red-400 text-sm font-medium border border-red-800/40 transition-colors"
              >
                <XCircle size={14} /> Stop
              </button>
            ) : (
              <button
                onClick={applyAll}
                disabled={filtered.filter(j => j.status === 'new').length === 0}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold shadow-lg shadow-violet-900/30 transition-all active:scale-95"
              >
                <Play size={14} />
                Apply All
                <span className="bg-white/20 px-1.5 py-0.5 rounded-md text-xs font-bold">
                  {filtered.filter(j => j.status === 'new').length}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Search + tabs */}
        <div className="flex items-center gap-3 mt-4">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              className="w-full bg-gray-800/80 border border-gray-700 rounded-xl pl-9 pr-4 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition"
              placeholder="Search jobs, companies…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1">
            {tabs.map(({ key, label, count }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                  filter === key
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800',
                )}
              >
                {label}
                {count > 0 && (
                  <span className={clsx(
                    'px-1.5 py-0.5 rounded-md text-[10px] font-bold',
                    filter === key ? 'bg-white/20 text-white' : 'bg-gray-800 text-gray-500',
                  )}>
                    {count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="px-6 py-5">
        {/* Stats */}
        {allJobs.length > 0 && <StatsBar jobs={allJobs} />}

        {/* Apply-all progress banner */}
        {applyingAll && (
          <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-xl bg-violet-950/60 border border-violet-800/60">
            <RefreshCw size={16} className="text-violet-400 animate-spin shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-violet-300">Auto-applying to all jobs…</p>
              <p className="text-xs text-violet-500">AI is filling forms and submitting applications in the background</p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 bg-gray-900 rounded-2xl flex items-center justify-center mb-4 border border-gray-800">
              <Briefcase size={28} className="text-gray-600" />
            </div>
            <h3 className="text-white font-semibold mb-1">No jobs found</h3>
            <p className="text-gray-500 text-sm max-w-xs">
              {search ? 'Try a different search term.' : 'Jobs will appear here once scraped. Check Settings to trigger a scrape.'}
            </p>
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-2xl border border-gray-800 bg-gray-900 p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gray-800" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-gray-800 rounded-full w-3/4" />
                    <div className="h-2.5 bg-gray-800 rounded-full w-1/2" />
                  </div>
                </div>
                <div className="mt-3 h-2 bg-gray-800 rounded-full w-full" />
                <div className="mt-2 h-2 bg-gray-800 rounded-full w-2/3" />
                <div className="mt-4 h-9 bg-gray-800 rounded-xl w-full" />
              </div>
            ))}
          </div>
        )}

        {/* Job grid */}
        {!isLoading && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map(job => (
              <JobCard
                key={job.id}
                job={job}
                onApply={applyOne}
                onSkip={skipOne}
                applying={applying.has(job.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
