'use strict';

const BACKEND = 'http://localhost:8000';

// ── DOM refs ──────────────────────────────────────────────────────────────────
const connBadge      = document.getElementById('conn-badge');
const statusBar      = document.getElementById('status-bar');
const statusIcon     = document.getElementById('status-icon');
const statusText     = document.getElementById('status-text');
const autoToggle     = document.getElementById('auto-apply-toggle');
const urlInput       = document.getElementById('url-input');
const applyBtn       = document.getElementById('apply-btn');
const urlFeedback    = document.getElementById('url-feedback');
const statApplied    = document.getElementById('stat-applied');
const statQueued     = document.getElementById('stat-queued');
const statFailed     = document.getElementById('stat-failed');
const statStuck      = document.getElementById('stat-stuck');
const activeJob      = document.getElementById('active-job');
const activeTitle    = document.getElementById('active-title');
const activeProgress = document.getElementById('active-progress');
const btnProfile     = document.getElementById('btn-profile');
const btnDashboard   = document.getElementById('btn-dashboard');
const btnTelegram    = document.getElementById('btn-telegram');

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  // Load saved toggle state
  const { autoApply } = await chrome.storage.local.get('autoApply');
  autoToggle.checked = autoApply !== false;

  // Check backend + load stats
  await checkBackend();
  await loadStats();

  // Get current apply status from bg
  chrome.runtime.sendMessage({ type: 'GET_STATUS' }, (resp) => {
    if (!resp) return;
    if (resp.isProcessing && resp.activeJob) {
      showActiveJob(resp.activeJob.title, resp.activeJob.company, 'Working...');
    }
  });

  // Poll stats every 5s while popup is open
  setInterval(loadStats, 5000);
}

// ── Backend health ────────────────────────────────────────────────────────────
async function checkBackend() {
  try {
    const resp = await fetch(`${BACKEND}/api/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      setConnected(true);
      statusBar.classList.remove('hidden');
      setStatus('info', '⚡', 'Ready — backend connected');
    } else {
      setConnected(false);
    }
  } catch {
    setConnected(false);
    setStatus('error', '❌', 'Backend offline — start start.bat');
  }
}

function setConnected(ok) {
  connBadge.className = `badge ${ok ? 'badge-green' : 'badge-red'}`;
  connBadge.textContent = ok ? 'Connected' : 'Offline';
}

function setStatus(type, icon, text) {
  statusBar.className = `status-bar ${type}`;
  statusBar.classList.remove('hidden');
  statusIcon.textContent = icon;
  statusText.textContent = text;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const [statsResp, queueResp] = await Promise.all([
      fetch(`${BACKEND}/api/v1/applications/stats`),
      fetch(`${BACKEND}/api/v1/jobs?status=queued&limit=1`),
    ]);

    if (statsResp.ok) {
      const s = await statsResp.json();
      statApplied.textContent = s.submitted ?? 0;
      statFailed.textContent  = s.failed ?? 0;
      statStuck.textContent   = s.stuck ?? 0;
    }

    if (queueResp.ok) {
      const q = await queueResp.json();
      statQueued.textContent = q.total ?? 0;
    }
  } catch {
    // Backend offline — already handled by checkBackend
  }
}

// ── Apply URL ────────────────────────────────────────────────────────────────
applyBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) return;

  try { new URL(url); } catch {
    showFeedback('Invalid URL', false);
    return;
  }

  applyBtn.disabled = true;
  applyBtn.textContent = '...';
  hideFeedback();

  chrome.runtime.sendMessage({ type: 'SUBMIT_URL', url }, (resp) => {
    applyBtn.disabled = false;
    applyBtn.textContent = 'Apply';
    if (resp?.ok) {
      showFeedback('✓ Queued with priority!', true);
      urlInput.value = '';
      setTimeout(loadStats, 1000);
    } else {
      showFeedback(resp?.error || 'Failed to queue job', false);
    }
  });
});

urlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') applyBtn.click();
});

function showFeedback(msg, ok) {
  urlFeedback.textContent = msg;
  urlFeedback.className = `feedback ${ok ? 'ok' : 'err'}`;
  urlFeedback.classList.remove('hidden');
  if (ok) setTimeout(hideFeedback, 3000);
}

function hideFeedback() {
  urlFeedback.classList.add('hidden');
}

// ── Toggle ────────────────────────────────────────────────────────────────────
autoToggle.addEventListener('change', () => {
  chrome.runtime.sendMessage({ type: 'TOGGLE_AUTO_APPLY', enabled: autoToggle.checked });
});

// ── Active job display ────────────────────────────────────────────────────────
function showActiveJob(title, company, progressMsg) {
  activeTitle.textContent = `${title || 'Job'} @ ${company || '?'}`;
  activeProgress.textContent = progressMsg || '';
  activeJob.classList.remove('hidden');
  setStatus('applying', '⚡', 'Applying now...');
}

function hideActiveJob() {
  activeJob.classList.add('hidden');
}

// ── Background messages (live updates while popup open) ──────────────────────
chrome.runtime.onMessage.addListener((msg) => {
  switch (msg.type) {
    case 'progress':
      activeProgress.textContent = msg.message;
      break;
    case 'job_finished':
      hideActiveJob();
      if (msg.status === 'applied') {
        setStatus('success', '✅', 'Application submitted!');
      } else if (msg.status === 'stuck') {
        setStatus('error', '⚠️', `Stuck: ${msg.reason || 'Unknown'}`);
      } else {
        setStatus('error', '❌', `Failed: ${msg.reason || 'Unknown'}`);
      }
      setTimeout(loadStats, 1500);
      break;
  }
});

// ── Footer buttons ────────────────────────────────────────────────────────────
btnProfile.addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
  window.close();
});

btnDashboard.addEventListener('click', () => {
  chrome.tabs.create({ url: `${BACKEND}` });
  window.close();
});

btnTelegram.addEventListener('click', () => {
  chrome.tabs.create({ url: `${BACKEND}/#/telegram` });
  window.close();
});

// ── Start ─────────────────────────────────────────────────────────────────────
init();
