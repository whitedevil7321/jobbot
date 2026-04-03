import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { applicationsApi, jobsApi } from '../api/jobs'
import { schedulerApi } from '../api/filters'
import { useWebSocket } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import { Zap, CheckCircle2, Clock, AlertTriangle, XCircle, RefreshCw, MessageCircle } from 'lucide-react'

export default function Dashboard() {
  const qc = useQueryClient()

  const { data: stats } = useQuery({
    queryKey: ['app-stats'],
    queryFn: () => applicationsApi.stats().then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: recentJobs } = useQuery({
    queryKey: ['recent-jobs'],
    queryFn: () => jobsApi.list({ limit: 10, sort_by: 'scraped_at' }).then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: schedulerStatus } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => schedulerApi.status().then(r => r.data),
    refetchInterval: 5000,
  })

  const { data: schedulerLogs } = useQuery({
    queryKey: ['scheduler-logs-dash'],
    queryFn: () => schedulerApi.logs().then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: telegramStatus } = useQuery({
    queryKey: ['telegram-status-dash'],
    queryFn: async () => {
      try { return (await import('../api/filters')).telegramApi.status().then((r: any) => r.data) }
      catch { return { running: false } }
    },
    refetchInterval: 10000,
  })

  const handleWsMessage = useCallback((msg: any) => {
    if (msg.type === 'new_job') {
      qc.invalidateQueries({ queryKey: ['recent-jobs'] })
      qc.invalidateQueries({ queryKey: ['app-stats'] })
    }
  }, [qc])

  useWebSocket(handleWsMessage)

  const triggerScrape = async () => {
    await schedulerApi.triggerScrape()
    setTimeout(() => qc.invalidateQueries({ queryKey: ['recent-jobs'] }), 3000)
  }

  const STAT_CARDS = [
    { label: 'Applied',     value: stats?.submitted ?? 0, icon: CheckCircle2, color: 'text-emerald-400' },
    { label: 'In Queue',    value: (stats?.pending ?? 0) + (stats?.in_progress ?? 0), icon: Clock, color: 'text-blue-400' },
    { label: 'Stuck',       value: stats?.stuck ?? 0,     icon: AlertTriangle, color: 'text-amber-400' },
    { label: 'Failed',      value: stats?.failed ?? 0,    icon: XCircle,       color: 'text-red-400' },
  ]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-0.5">Real-time job application status</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border ${schedulerStatus?.running ? 'border-emerald-800 bg-emerald-950 text-emerald-400' : 'border-gray-700 bg-gray-900 text-gray-500'}`}>
            <span className={`w-2 h-2 rounded-full ${schedulerStatus?.running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
            {schedulerStatus?.running ? 'Scraper Active' : 'Scraper Stopped'}
          </div>
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border ${telegramStatus?.running ? 'border-blue-800 bg-blue-950 text-blue-400' : 'border-gray-700 bg-gray-900 text-gray-500'}`}>
            <MessageCircle size={12} />
            {telegramStatus?.running ? 'Telegram Connected' : 'Telegram Offline'}
          </div>
          <button onClick={triggerScrape} className="btn-secondary flex items-center gap-2">
            <RefreshCw size={14} /> Scrape Now
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className={`p-2.5 rounded-lg bg-gray-800 ${color}`}>
              <Icon size={20} />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{value}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Jobs */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Zap size={16} className="text-violet-400" /> Recently Scraped Jobs
          </h2>
          <span className="text-xs text-gray-500">{recentJobs?.total ?? 0} total in DB</span>
        </div>
        <div className="space-y-2">
          {recentJobs?.jobs?.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">
              No jobs yet. Click "Scrape Now" or wait for the scheduler to run.
            </p>
          )}
          {recentJobs?.jobs?.map((job: any) => (
            <div key={job.id} className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 transition-colors">
              <div className="min-w-0">
                <div className="font-medium text-sm text-white truncate">{job.title}</div>
                <div className="text-xs text-gray-500 truncate">{job.company} · {job.location || 'Location unknown'}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0 ml-4">
                <span className="text-xs text-gray-600 uppercase tracking-wide">{job.source}</span>
                <span className="text-xs text-violet-400 font-mono">{Math.round(job.filter_score)}%</span>
                <StatusBadge status={job.status} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Scrape run log */}
      {schedulerLogs?.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-white mb-3">Recent Scrape Runs</h2>
          <div className="space-y-1">
            {schedulerLogs.slice(0, 5).map((log: any) => (
              <div key={log.id} className="flex items-center justify-between text-xs py-1.5 px-2 rounded bg-gray-800/50">
                <span className="text-gray-500 font-mono">{log.started_at?.split('T')[1]?.split('.')[0]}</span>
                <span className={log.status === 'completed' ? 'text-emerald-400' : log.status === 'failed' ? 'text-red-400' : 'text-blue-400 animate-pulse'}>
                  {log.status}
                </span>
                <span className="text-gray-400">{log.jobs_found} found</span>
                <span className="text-violet-400">+{log.jobs_new} new</span>
                {log.error && <span className="text-red-400 truncate max-w-[160px]" title={log.error}>⚠ {log.error.slice(0,40)}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
