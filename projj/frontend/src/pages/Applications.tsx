import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationsApi } from '../api/jobs'
import StatusBadge from '../components/StatusBadge'
import { ClipboardList, SkipForward, RefreshCw, Hand } from 'lucide-react'

const STATUSES = ['all', 'pending', 'in_progress', 'submitted', 'stuck', 'skipped', 'failed']

export default function Applications() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)

  const params: Record<string, any> = { page, limit: 30 }
  if (status !== 'all') params.status = status

  const { data, isLoading } = useQuery({
    queryKey: ['applications', params],
    queryFn: () => applicationsApi.list(params).then(r => r.data),
    refetchInterval: 8000,
  })

  const { data: stats } = useQuery({
    queryKey: ['app-stats'],
    queryFn: () => applicationsApi.stats().then(r => r.data),
    refetchInterval: 10000,
  })

  const decideMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'skip' | 'retry' | 'manual' }) =>
      applicationsApi.decide(id, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['app-stats'] })
    },
  })

  const statCards = [
    { label: 'Total',       value: stats?.total ?? 0,       color: 'text-white' },
    { label: 'Submitted',   value: stats?.submitted ?? 0,   color: 'text-emerald-400' },
    { label: 'Stuck',       value: stats?.stuck ?? 0,       color: 'text-amber-400' },
    { label: 'Failed',      value: stats?.failed ?? 0,      color: 'text-red-400' },
    { label: 'Skipped',     value: stats?.skipped ?? 0,     color: 'text-gray-400' },
  ]

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <ClipboardList className="text-violet-400" size={22} /> Applications
      </h1>

      <div className="grid grid-cols-5 gap-3">
        {statCards.map(({ label, value, color }) => (
          <div key={label} className="card text-center">
            <div className={`text-xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      <div>
        <label className="label">Filter by Status</label>
        <div className="flex flex-wrap gap-2">
          {STATUSES.map(s => (
            <button
              key={s}
              onClick={() => { setStatus(s); setPage(1) }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${status === s ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
            >
              {s === 'all' ? 'All' : s}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {isLoading && <div className="text-center py-12 text-gray-500">Loading...</div>}
        {!isLoading && data?.applications?.length === 0 && (
          <div className="text-center py-12 text-gray-500">No applications found.</div>
        )}
        {data?.applications?.map((app: any) => (
          <div key={app.id} className={`card ${app.status === 'stuck' ? 'border-amber-800/50' : ''}`}>
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">Application #{app.id}</span>
                  <span className="text-xs text-gray-600">Job #{app.job_id}</span>
                  <span className="text-xs text-gray-600">Attempt #{app.attempt_number}</span>
                </div>
                {app.stuck_reason && (
                  <p className="text-xs text-amber-400 mt-0.5">⚠ {app.stuck_reason}</p>
                )}
                {app.error_message && (
                  <p className="text-xs text-red-400 mt-0.5">✕ {app.error_message}</p>
                )}
                <div className="text-xs text-gray-600 mt-0.5">
                  {app.started_at && <span>Started: {new Date(app.started_at).toLocaleString()}</span>}
                  {app.completed_at && <span> · Done: {new Date(app.completed_at).toLocaleString()}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <StatusBadge status={app.status} />
                {app.status === 'stuck' && (
                  <>
                    <button
                      className="btn-danger flex items-center gap-1 text-xs py-1"
                      onClick={() => decideMutation.mutate({ id: app.id, action: 'skip' })}
                    >
                      <SkipForward size={12} /> Skip
                    </button>
                    <button
                      className="btn-secondary flex items-center gap-1 text-xs py-1"
                      onClick={() => decideMutation.mutate({ id: app.id, action: 'retry' })}
                    >
                      <RefreshCw size={12} /> Retry
                    </button>
                    <button
                      className="btn-secondary flex items-center gap-1 text-xs py-1"
                      onClick={() => decideMutation.mutate({ id: app.id, action: 'manual' })}
                    >
                      <Hand size={12} /> Manual
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {data && data.total > 30 && (
        <div className="flex justify-center gap-3 pt-2">
          <button className="btn-secondary" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span className="text-gray-500 text-sm py-2">Page {page}</span>
          <button className="btn-secondary" disabled={page * 30 >= data.total} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}
    </div>
  )
}
