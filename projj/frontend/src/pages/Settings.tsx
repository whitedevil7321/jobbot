import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ollamaApi, schedulerApi } from '../api/filters'
import { Settings, Brain, Clock, Play, RefreshCw, Mail, CheckCircle, XCircle, Eye, EyeOff } from 'lucide-react'
import axios from 'axios'

export default function SettingsPage() {
  const qc = useQueryClient()
  const [interval, setInterval] = useState(1)
  const [autoApply, setAutoApply] = useState(true)
  const [pullModel, setPullModel] = useState('')
  const [pullProgress, setPullProgress] = useState('')

  // Email OTP state
  const [emailHost, setEmailHost] = useState('imap.gmail.com')
  const [emailPort, setEmailPort] = useState(993)
  const [emailAddr, setEmailAddr] = useState('')
  const [emailPass, setEmailPass] = useState('')
  const [emailWait, setEmailWait] = useState(60)
  const [showPass, setShowPass] = useState(false)
  const [emailTestMsg, setEmailTestMsg] = useState<{ ok: boolean; msg: string } | null>(null)
  const [otpTestMsg, setOtpTestMsg] = useState<{ found: boolean; msg: string } | null>(null)

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

  // Load email config on mount
  const { data: emailConfig } = useQuery({
    queryKey: ['email-config'],
    queryFn: () => axios.get('/api/v1/email-config').then(r => r.data),
  })

  useEffect(() => {
    if (emailConfig) {
      if (emailConfig.imap_host) setEmailHost(emailConfig.imap_host)
      if (emailConfig.imap_port) setEmailPort(emailConfig.imap_port)
      if (emailConfig.email_address) setEmailAddr(emailConfig.email_address)
      if (emailConfig.otp_wait_seconds) setEmailWait(emailConfig.otp_wait_seconds)
    }
  }, [emailConfig])

  const testEmailMutation = useMutation({
    mutationFn: () => axios.post('/api/v1/email-config/test', {
      imap_host: emailHost, imap_port: emailPort,
      email_address: emailAddr, email_password: emailPass,
      otp_wait_seconds: emailWait,
    }),
    onSuccess: (r) => setEmailTestMsg({ ok: r.data.success, msg: r.data.message }),
    onError: (e: any) => setEmailTestMsg({ ok: false, msg: e.response?.data?.detail || 'Connection failed' }),
  })

  const testOtpMutation = useMutation({
    mutationFn: () => axios.post('/api/v1/email-config/test-otp'),
    onSuccess: (r) => setOtpTestMsg({ found: r.data.found, msg: r.data.message }),
    onError: (e: any) => setOtpTestMsg({ found: false, msg: e.response?.data?.detail || 'Error' }),
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
                    const decoder = new TextDecoder()
                    while (true) {
                      const { done, value } = await reader.read()
                      if (done) break
                      if (!value) continue
                      const text = decoder.decode(value, { stream: true })
                      const lines = text.split('\n').filter(l => l.trim())
                      for (const line of lines) {
                        try {
                          const d = JSON.parse(line)
                          if (d.status) setPullProgress(d.status)
                          else if (d.error) setPullProgress(`Error: ${d.error}`)
                        } catch { /* ignore partial JSON lines */ }
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

      {/* Email OTP Auto-Reader */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Mail size={16} className="text-violet-400" /> Email OTP Auto-Reader
          </h2>
          {emailConfig?.configured && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle size={12} /> Configured
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">
          When job applications require email verification codes (OTP), the bot reads your inbox automatically and fills in the code.
          For Gmail, use an <strong className="text-gray-400">App Password</strong> (not your regular password) — enable 2FA first, then visit <code className="text-violet-300">myaccount.google.com/apppasswords</code>.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">IMAP Host</label>
            <select className="input" value={emailHost} onChange={e => setEmailHost(e.target.value)}>
              <option value="imap.gmail.com">Gmail (imap.gmail.com)</option>
              <option value="imap-mail.outlook.com">Outlook / Hotmail</option>
              <option value="imap.mail.yahoo.com">Yahoo Mail</option>
              <option value="imap.zoho.com">Zoho Mail</option>
              <option value="custom">Custom...</option>
            </select>
            {emailHost === 'custom' && (
              <input className="input mt-1" placeholder="mail.example.com" onChange={e => setEmailHost(e.target.value)} />
            )}
          </div>
          <div>
            <label className="label">IMAP Port</label>
            <input className="input" type="number" value={emailPort} onChange={e => setEmailPort(Number(e.target.value))} />
          </div>
        </div>

        <div>
          <label className="label">Email Address</label>
          <input
            className="input"
            type="email"
            placeholder="yourname@gmail.com"
            value={emailAddr}
            onChange={e => setEmailAddr(e.target.value)}
          />
        </div>

        <div>
          <label className="label">Password / App Password</label>
          <div className="relative">
            <input
              className="input pr-10"
              type={showPass ? 'text' : 'password'}
              placeholder="Gmail: use App Password, not your main password"
              value={emailPass}
              onChange={e => setEmailPass(e.target.value)}
            />
            <button
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              onClick={() => setShowPass(s => !s)}
              type="button"
            >
              {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Your password is stored only in the local <code>.env</code> file and never sent anywhere.
          </p>
        </div>

        <div>
          <label className="label">OTP Wait Timeout (seconds)</label>
          <input className="input" type="number" min={10} max={300} value={emailWait} onChange={e => setEmailWait(Number(e.target.value))} />
          <p className="text-xs text-gray-600 mt-1">How long to wait for the verification email before giving up.</p>
        </div>

        <div className="flex gap-3 flex-wrap">
          <button
            className="btn-primary flex items-center gap-2"
            onClick={() => testEmailMutation.mutate()}
            disabled={!emailAddr || !emailPass || testEmailMutation.isPending}
          >
            {testEmailMutation.isPending ? (
              <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Testing...</>
            ) : 'Test Connection'}
          </button>
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => testOtpMutation.mutate()}
            disabled={testOtpMutation.isPending}
          >
            {testOtpMutation.isPending ? (
              <><span className="w-3 h-3 border-2 border-gray-400/30 border-t-gray-400 rounded-full animate-spin" /> Scanning...</>
            ) : 'Scan for Recent OTP'}
          </button>
        </div>

        {emailTestMsg && (
          <div className={`flex items-start gap-2 p-3 rounded-lg text-sm ${emailTestMsg.ok ? 'bg-emerald-950/40 border border-emerald-800/50 text-emerald-300' : 'bg-red-950/40 border border-red-800/50 text-red-300'}`}>
            {emailTestMsg.ok ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <XCircle size={14} className="mt-0.5 shrink-0" />}
            {emailTestMsg.msg}
          </div>
        )}

        {otpTestMsg && (
          <div className={`flex items-start gap-2 p-3 rounded-lg text-sm ${otpTestMsg.found ? 'bg-emerald-950/40 border border-emerald-800/50 text-emerald-300' : 'bg-gray-800/50 border border-gray-700 text-gray-300'}`}>
            {otpTestMsg.found ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <Mail size={14} className="mt-0.5 shrink-0" />}
            {otpTestMsg.msg}
          </div>
        )}

        <div className="bg-blue-950/30 border border-blue-800/40 rounded-lg p-3 text-xs text-blue-300 space-y-1">
          <p className="font-semibold">How to set up Gmail App Password:</p>
          <p>1. Go to <strong>myaccount.google.com/security</strong> → enable 2-Step Verification</p>
          <p>2. Go to <strong>myaccount.google.com/apppasswords</strong></p>
          <p>3. Select "Mail" and "Windows Computer" → Generate</p>
          <p>4. Copy the 16-character password and paste it above</p>
          <p>5. Also add these to your <code>.env</code> file: <code>EMAIL_ADDRESS</code> and <code>EMAIL_PASSWORD</code></p>
        </div>
      </div>
    </div>
  )
}
