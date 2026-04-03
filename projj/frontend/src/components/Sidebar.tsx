import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, User, Filter, MessageCircle, Settings,
  ClipboardList, Bot, Zap,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/jobs',        icon: Zap,             label: 'Job Feed' },
  { to: '/applications',icon: ClipboardList,   label: 'Applications' },
  { to: '/profile',     icon: User,            label: 'My Profile' },
  { to: '/filters',     icon: Filter,          label: 'Filters' },
  { to: '/telegram',    icon: MessageCircle,   label: 'Telegram' },
  { to: '/settings',    icon: Settings,        label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      <div className="px-4 py-5 border-b border-gray-800 flex items-center gap-2">
        <Bot className="text-violet-400" size={22} />
        <span className="font-bold text-lg tracking-tight text-white">JobBot</span>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-violet-600/20 text-violet-300'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200',
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        v1.0.0 — Local LLM
      </div>
    </aside>
  )
}
