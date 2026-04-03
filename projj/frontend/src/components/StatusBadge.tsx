import { clsx } from 'clsx'

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  new:         { label: 'New',        cls: 'badge-gray' },
  queued:      { label: 'Queued',     cls: 'badge-blue' },
  applying:    { label: 'Applying',   cls: 'badge-purple' },
  applied:     { label: 'Applied',    cls: 'badge-green' },
  submitted:   { label: 'Submitted',  cls: 'badge-green' },
  stuck:       { label: 'Stuck',      cls: 'badge-yellow' },
  skipped:     { label: 'Skipped',    cls: 'badge-gray' },
  failed:      { label: 'Failed',     cls: 'badge-red' },
  pending:     { label: 'Pending',    cls: 'badge-blue' },
  in_progress: { label: 'Running',    cls: 'badge-purple' },
}

export default function StatusBadge({ status }: { status: string }) {
  const { label, cls } = STATUS_MAP[status] ?? { label: status, cls: 'badge-gray' }
  return <span className={cls}>{label}</span>
}
