import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { telegramApi } from '../api/filters'
import { MessageCircle, CheckCircle2, XCircle, Send } from 'lucide-react'

export default function TelegramSetup() {
  const [token, setToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)

  const { data: config, refetch } = useQuery({
    queryKey: ['telegram-config'],
    queryFn: () => telegramApi.config().then(r => r.data),
  })

  const { data: status } = useQuery({
    queryKey: ['telegram-status'],
    queryFn: () => telegramApi.status().then(r => r.data),
    refetchInterval: 5000,
  })

  const saveMutation = useMutation({
    mutationFn: () => telegramApi.save(token, chatId),
    onSuccess: () => { refetch(); setToken(''); setChatId('') },
  })

  const testMutation = useMutation({
    mutationFn: () => telegramApi.test(),
    onSuccess: () => setTestResult('success'),
    onError: () => setTestResult('error'),
  })

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <MessageCircle className="text-violet-400" size={22} /> Telegram Setup
      </h1>

      {/* Status */}
      <div className="card flex items-center gap-3">
        {status?.running ? (
          <>
            <CheckCircle2 className="text-emerald-400" size={20} />
            <div>
              <p className="text-sm font-medium text-white">Bot is running</p>
              {config?.chat_id && <p className="text-xs text-gray-500">Chat ID: {config.chat_id}</p>}
            </div>
          </>
        ) : (
          <>
            <XCircle className="text-red-400" size={20} />
            <div>
              <p className="text-sm font-medium text-white">Bot not configured</p>
              <p className="text-xs text-gray-500">Follow the steps below to set up your Telegram bot</p>
            </div>
          </>
        )}
      </div>

      {/* Setup Instructions */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Setup Instructions</h2>
        <ol className="space-y-3 text-sm text-gray-300">
          <li className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 bg-violet-600 rounded-full flex items-center justify-center text-xs font-bold">1</span>
            <span>Open Telegram and search for <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">@BotFather</code></span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 bg-violet-600 rounded-full flex items-center justify-center text-xs font-bold">2</span>
            <span>Send <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">/newbot</code> and follow the prompts to create your bot. Copy the <strong>bot token</strong>.</span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 bg-violet-600 rounded-full flex items-center justify-center text-xs font-bold">3</span>
            <span>Message <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">@userinfobot</code> on Telegram to get your <strong>Chat ID</strong>.</span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 bg-violet-600 rounded-full flex items-center justify-center text-xs font-bold">4</span>
            <span>Enter both values below and save. Then send a job link to your bot!</span>
          </li>
        </ol>
      </div>

      {/* Config Form */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Bot Configuration</h2>
        {config?.configured && (
          <p className="text-xs text-emerald-400">Currently configured: token ending in {config.bot_token}</p>
        )}
        <div>
          <label className="label">Bot Token</label>
          <input
            className="input font-mono text-xs"
            type="password"
            placeholder="1234567890:ABCDefgh..."
            value={token}
            onChange={e => setToken(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Your Chat ID</label>
          <input
            className="input"
            placeholder="123456789"
            value={chatId}
            onChange={e => setChatId(e.target.value)}
          />
        </div>
        <div className="flex gap-3">
          <button
            className="btn-primary flex-1"
            disabled={!token || !chatId || saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? 'Connecting...' : 'Save & Connect Bot'}
          </button>
          {config?.configured && (
            <button
              className="btn-secondary flex items-center gap-2"
              disabled={testMutation.isPending}
              onClick={() => testMutation.mutate()}
            >
              <Send size={14} /> Test
            </button>
          )}
        </div>
        {saveMutation.isError && (
          <p className="text-red-400 text-xs">Failed to connect. Check your bot token.</p>
        )}
        {testResult === 'success' && <p className="text-emerald-400 text-xs">Test message sent! Check your Telegram.</p>}
        {testResult === 'error' && <p className="text-red-400 text-xs">Test failed. Check bot configuration.</p>}
      </div>

      {/* Usage Guide */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">How to Use</h2>
        <div className="space-y-2 text-sm text-gray-400">
          <p>• Send any job link to your bot — it will be applied <strong className="text-white">immediately with priority</strong></p>
          <p>• Use <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">/status</code> to see application stats</p>
          <p>• Use <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">/pause</code> and <code className="bg-gray-800 px-1 py-0.5 rounded text-violet-300">/resume</code> to control auto-apply</p>
          <p>• When JobBot gets stuck, it will ask you via Telegram with Skip / Retry / Manual buttons</p>
        </div>
      </div>
    </div>
  )
}
