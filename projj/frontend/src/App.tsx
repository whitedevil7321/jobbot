import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import JobFeed from './pages/JobFeed'
import Applications from './pages/Applications'
import Profile from './pages/Profile'
import Filters from './pages/Filters'
import TelegramSetup from './pages/TelegramSetup'
import SettingsPage from './pages/Settings'
import ApplyQueue from './pages/ApplyQueue'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/apply-queue"  element={<ApplyQueue />} />
          <Route path="/jobs"         element={<JobFeed />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/profile"      element={<Profile />} />
          <Route path="/filters"      element={<Filters />} />
          <Route path="/telegram"     element={<TelegramSetup />} />
          <Route path="/settings"     element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
