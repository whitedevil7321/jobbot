import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ollamaApi, schedulerApi } from '../api/filters'
import { Settings, Brain, Clock, Play, Square, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const qc = useQueryClient()
  const [interval, setInterval] = useState(1)
  const [autoApply, setAutoApply] = useState(true)
  const [pullModel, setPullModel] = useState('')
  const [pullProgress, setPullProgress] = useState('')

  const { data: ollamaStatus } = useQuery({
    queryKey: ['ollama-status'],
    queryFn: () => ollamaApi.status().then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: models } = useQuery({
    queryKey: ['ollama-models'],
    queryFn: () => ollamaApi.models().then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: schedulerStatus } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => schedulerApi.status().then(r => r.data),
    refetchInterval: 5000,
  })

  const { data: logs } = useQuery({
    queryKey: ['scheduler-logs'],
    queryFn: () => schedulerApi.logs().then(r => r.data),
    refetchInterval: 15000,
  })

  const setModelMutation = useMutation({
    mutationFn: (m: string) => ollamaApi.setModel(m),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ollama-status'] }),
  })

  const updateSchedulerMutation = useMutation({
    mutationFn: () => schedulerApi.updateConfig({ scrape_interval_minutes: interval, auto_apply: autoApply }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler-status'] }),
  })

  const triggerScrapeMutation = useMutation({
    mutationFn: () => schedulerApi.triggerScrape(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scheduler-logs'] }); qc.invalidateQueries({ queryKey: ['jobs'] }) },
  })

  const triggerApplyMutation = useMutation({
    mutationFn: () => schedulerApi.triggerApply(),
  })

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <Settings className="text-violet-400" size={22} /> Settings
      </h1>

      {/* Ollama / LLM */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <Brain size={16} className="text-violet-400" /> Local LLM (Ollama)
        </h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${ollamaStatus?.running ? 'bg-emerald-400' : 'bg-red-400'}`} />
          <span className="text-sm text-gray-300">
            {ollamaStatus?.running ? `Ollama running` : 'Ollama not running'}
          </span>
          {ollamaStatus?.active_model && (
            <span className="badge-purple ml-auto">Active: {ollamaStatus.active_model}</span>
          )}
        </div>

        {!ollamaStatus?.running && (
          <div className="bg-amber-950/30 border border-amber-800/50 rounded-lg p-3 text-xs text-amber-300">
            Ollama is not running. Install from <strong>ollama.ai</strong> and run <code className="bg-gray-800 px-1 rounded">ollama serve</code>
          </div>
        )}

        {models?.models?.length > 0 && (
          <div>
            <label className="label">Active Model</label>
            <div className="flex flex-wrap gap-2">
              {models.models.map((m: string) => (
                <button
                  key={m}
                  onClick={() => setModelMutation.mutate(m)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-mono transition-colors ${models.active === m ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <label className="label">Pull a New Model</label>
          <div className="flex gap-2">
            <input
              className="input flex-1 font-mono text-xs"
              placeholder="llama3, mistral, phi3, gemma..."
              value={pullModel}
              onChange={e => setPullModel(e.target.value)}
            />
            <button
              className="btn-secondary"
              disabled={!pullModel}
              onClick={async () => {
                // Use fetch for streaming
                setPullProgress('Starting...')
                try {
                  const resp = await fetch('/api/v1/ollama/models/pull', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_name: pullModel }),
                  })
                  const reader = resp.body?.getReader()
                  if (reader) {
                    while (true) {
                      const { done, value } = await reader.read()
                      if (done) break
                      const text = new TextDecoder().decode(value)
                      const lines = text.split('\n').filter(Boolean)
                      for (const line of lines) {
                        try { const d = JSON.parse(line); setPullProgress(d.status || d.error || '') } catch {}
                      }
                    }
                  }
                  setPullProgress('Done!')
                  qc.invalidateQueries({ queryKey: ['ollama-models'] })
                } catch {
                  setPullProgress('Error pulling model')
                }
              }}
            >
              Pull
            </button>
          </div>
          {pullProgress && <p className="text-xs text-gray-500 mt-1 font-mono">{pullProgress}</p>}
          <p className="text-xs text-gray-600 mt-1">Recommended: llama3 (8B), mistral (7B), phi3 (3.8B)</p>
        </div>
      </div>

      {/* Scheduler Settings */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <Clock size={16} className="text-violet-400" /> Scheduler
        </h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${schedulerStatus?.running ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <span className="text-sm text-gray-300">{schedulerStatus?.running ? 'Scheduler active' : 'Scheduler stopped'}</span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Scrape Interval (minutes)</label>
            <input className="input" type="number" min={1} max={60} value={interval} onChange={e => setInterval(Number(e.target.value))} />
          </div>
          <div className="flex items-center gap-3 pt-5">
            <input type="checkbox" id="autoapply" className="w-4 h-4 accent-violet-500" checked={autoApply} onChange={e => setAutoApply(e.target.checked)} />
            <label htmlFor="autoapply" className="text-sm text-gray-300">Auto-apply to matching jobs</label>
          </div>
        </div>
        <button className="btn-primary" onClick={() => updateSchedulerMutation.mutate()} disabled={updateSchedulerMutation.isPending}>
          Save Scheduler Config
        </button>

        <div className="flex gap-3 pt-2">
          <button className="btn-secondary flex items-center gap-2" onClick={() => triggerScrapeMutation.mutate()} disabled={triggerScrapeMutation.isPending}>
            <RefreshCw size={14} className={triggerScrapeMutation.isPending ? 'animate-spin' : ''} /> Scrape Now
          </button>
          <button className="btn-secondary flex items-center gap-2" onClick={() => triggerApplyMutation.mutate()} disabled={triggerApplyMutation.isPending}>
            <Play size={14} /> Process Apply Queue
          </button>
        </div>
      </div>

      {/* Scheduler Logs */}
      {logs?.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-white mb-3">Recent Runs</h2>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {logs.slice(0, 20).map((log: any) => (
              <div key={log.id} className="flex items-center justify-between text-xs py-1.5 px-2 rounded bg-gray-800/50">
                <span className="text-gray-500">{log.started_at?.split('T')[1]?.split('.')[0]}</span>
                <span className="text-gray-400 capitalize">{log.task}</span>
                <span className={log.status === 'completed' ? 'text-emerald-400' : log.status === 'failed' ? 'text-red-400' : 'text-blue-400'}>{log.status}</span>
                <span className="text-gray-500">+{log.jobs_new} new</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
