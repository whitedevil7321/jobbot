/**
 * JobBot Background Service Worker
 * - Polls backend for queued jobs every 5 seconds
 * - Opens tabs and injects autofill scripts
 * - Handles multi-step navigation within apply flows
 * - Reports results back to backend
 * - Polls Telegram queue for priority URLs
 */

const BACKEND = 'http://localhost:8000';
const POLL_INTERVAL_MS = 5000;
const MAX_APPLY_STEPS = 15;
const APPLY_TIMEOUT_MS = 300_000; // 5 minutes

// ── State ─────────────────────────────────────────────────────────────────────
let activeJob = null; // { jobId, tabId, step, startedAt, status }
let isProcessing = false;
let autoApplyEnabled = true;

// ── Alarms ────────────────────────────────────────────────────────────────────
chrome.alarms.create('pollQueue', { periodInMinutes: 0.083 }); // ~5 sec

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'pollQueue') {
    await pollAndProcess();
  }
});

// ── Startup ───────────────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ autoApply: true, backendUrl: BACKEND });
  console.log('[JobBot] Extension installed. Backend:', BACKEND);
});

chrome.runtime.onStartup.addListener(async () => {
  const { autoApply } = await chrome.storage.local.get('autoApply');
  autoApplyEnabled = autoApply !== false;
});

// ── Tab navigation tracking ───────────────────────────────────────────────────
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!activeJob || activeJob.tabId !== tabId) return;
  if (changeInfo.status !== 'complete') return;
  if (!tab.url || tab.url.startsWith('chrome://')) return;

  // Page fully loaded in our active apply tab — re-inject autofill
  console.log(`[JobBot] Tab ${tabId} loaded: ${tab.url} (step ${activeJob.step})`);
  await injectAndContinue(tabId, tab.url);
});

// ── Message handler (from content scripts + popup) ────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.type) {
    case 'CONTENT_READY':
      handleContentReady(sender.tab?.id, msg.url).then(r => sendResponse(r));
      return true;

    case 'APPLY_PROGRESS':
      handleProgress(msg);
      sendResponse({ ok: true });
      return false;

    case 'APPLY_RESULT':
      handleResult(msg, sender.tab?.id).then(r => sendResponse(r));
      return true;

    case 'ASK_LLM':
      askLLM(msg.question, msg.context, msg.type_hint).then(answer => sendResponse({ answer }));
      return true;

    case 'GET_RESUME':
      fetchResumeData().then(data => sendResponse(data));
      return true;

    case 'SUBMIT_URL':
      submitUrl(msg.url).then(r => sendResponse(r));
      return true;

    case 'GET_STATUS':
      sendResponse({
        connected: true,
        isProcessing,
        activeJob,
        autoApplyEnabled,
      });
      return false;

    case 'TOGGLE_AUTO_APPLY':
      autoApplyEnabled = msg.enabled;
      chrome.storage.local.set({ autoApply: msg.enabled });
      sendResponse({ ok: true });
      return false;

    case 'OPEN_PROFILE':
      chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
      sendResponse({ ok: true });
      return false;
  }
});

// ── Core: Poll + Process ──────────────────────────────────────────────────────
async function pollAndProcess() {
  if (isProcessing) return;

  const { autoApply } = await chrome.storage.local.get('autoApply');
  if (autoApply === false) return;

  try {
    // Check backend health first
    const health = await fetchJSON('/api/health').catch(() => null);
    if (!health) return;

    // Get next queued job (priority 0 = telegram, 1 = scraped)
    const data = await fetchJSON('/api/v1/jobs?status=queued&sort_by=priority&limit=1').catch(() => null);
    if (!data?.jobs?.length) return;

    const job = data.jobs[0];
    await startApplyJob(job);
  } catch (err) {
    console.error('[JobBot] Poll error:', err);
  }
}

async function startApplyJob(job) {
  if (isProcessing) return;
  isProcessing = true;

  const applyUrl = job.apply_url || job.url;
  if (!applyUrl) {
    await markJobFailed(job.id, 'No URL for job');
    isProcessing = false;
    return;
  }

  console.log(`[JobBot] Starting apply: job ${job.id} — ${job.title} @ ${job.company}`);
  console.log(`[JobBot] URL: ${applyUrl}`);

  // Mark as applying on backend
  await fetchJSON(`/api/v1/jobs/${job.id}/apply`, { method: 'POST' }).catch(() => {});

  // Create a new tab for this job
  const tab = await chrome.tabs.create({ url: applyUrl, active: true });

  activeJob = {
    jobId: job.id,
    tabId: tab.id,
    step: 0,
    startedAt: Date.now(),
    status: 'opening',
    title: job.title,
    company: job.company,
    url: applyUrl,
  };

  // Set a hard timeout
  setTimeout(() => {
    if (activeJob && activeJob.jobId === job.id && activeJob.status !== 'done') {
      console.warn(`[JobBot] Job ${job.id} timed out`);
      finishJob('stuck', 'Application timed out after 5 minutes');
    }
  }, APPLY_TIMEOUT_MS);
}

// ── Content Script Injection ──────────────────────────────────────────────────
async function injectAndContinue(tabId, url) {
  if (!activeJob || activeJob.tabId !== tabId) return;
  if (activeJob.step >= MAX_APPLY_STEPS) {
    await finishJob('stuck', 'Maximum form steps reached');
    return;
  }

  try {
    // Fetch profile fresh each session
    const profile = await fetchJSON('/api/v1/profile').catch(() => null);
    if (!profile || !profile.email) {
      await finishJob('failed', 'No profile configured — please fill in Profile first');
      return;
    }

    // Inject the autofill content script
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content/autofill.js'],
    });

    // Small delay then send START_APPLY
    await sleep(800);

    await chrome.tabs.sendMessage(tabId, {
      type: 'START_APPLY',
      profile,
      jobId: activeJob.jobId,
      step: activeJob.step,
      url,
    });

    activeJob.step++;
  } catch (err) {
    console.error('[JobBot] Inject error:', err.message);
    // Tab may have closed or navigated — handled by onUpdated
  }
}

async function handleContentReady(tabId, url) {
  if (!activeJob || activeJob.tabId !== tabId) return { skip: true };
  activeJob.status = 'filling';
  return { ok: true, jobId: activeJob.jobId, step: activeJob.step };
}

function handleProgress(msg) {
  console.log(`[JobBot] Step ${msg.step || '?'}: ${msg.message}`);
  broadcastToPopup({ type: 'progress', message: msg.message, step: msg.step });
}

async function handleResult(msg, tabId) {
  if (!activeJob || activeJob.tabId !== tabId) return { ok: false };

  switch (msg.status) {
    case 'submitted':
      await finishJob('applied', null, msg.coverLetter, msg.screeningAnswers);
      break;
    case 'stuck':
      // If not last step, keep going on next navigation
      if (msg.canContinue) {
        activeJob.status = 'waiting_nav';
      } else {
        await finishJob('stuck', msg.reason);
      }
      break;
    case 'failed':
      await finishJob('failed', msg.reason);
      break;
    case 'needs_navigation':
      // Content script clicked Next/Submit — wait for tab navigation
      activeJob.status = 'waiting_nav';
      break;
  }
  return { ok: true };
}

// ── Finish a job ──────────────────────────────────────────────────────────────
async function finishJob(status, reason, coverLetter, screeningAnswers) {
  if (!activeJob) return;

  const { jobId, tabId, title, company } = activeJob;
  activeJob.status = 'done';

  console.log(`[JobBot] Job ${jobId} finished: ${status}${reason ? ' — ' + reason : ''}`);

  // Update backend
  try {
    if (status === 'applied') {
      await fetchJSON(`/api/v1/jobs/${jobId}/apply`, { method: 'POST' });
    }
    // Report result via manual endpoint
    await fetchJSON('/api/v1/extension/result', {
      method: 'POST',
      body: { jobId, status, reason, coverLetter, screeningAnswers },
    }).catch(() => {});
  } catch (err) {
    console.error('[JobBot] Failed to update backend:', err);
  }

  // Show notification
  chrome.notifications.create(`job_${jobId}`, {
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: status === 'applied' ? '✅ Applied!' : status === 'stuck' ? '⚠️ Stuck' : '❌ Failed',
    message: `${title} @ ${company}${reason ? '\n' + reason : ''}`,
  });

  broadcastToPopup({ type: 'job_finished', jobId, status, reason });

  // Close the tab after a brief delay
  setTimeout(() => {
    if (tabId) chrome.tabs.remove(tabId).catch(() => {});
  }, 2000);

  activeJob = null;
  isProcessing = false;
}

async function markJobFailed(jobId, reason) {
  await fetchJSON('/api/v1/extension/result', {
    method: 'POST',
    body: { jobId, status: 'failed', reason },
  }).catch(() => {});
  isProcessing = false;
}

// ── LLM via backend ───────────────────────────────────────────────────────────
async function askLLM(question, context, typeHint) {
  try {
    const data = await fetchJSON('/api/v1/ollama/answer', {
      method: 'POST',
      body: { question, context, type_hint: typeHint || 'text' },
    });
    return data?.answer || '';
  } catch {
    return '';
  }
}

// ── Resume data ───────────────────────────────────────────────────────────────
async function fetchResumeData() {
  try {
    const resp = await fetch(`${BACKEND}/api/v1/profile/resume-download`);
    if (!resp.ok) return { error: 'No resume' };
    const blob = await resp.blob();
    const arrayBuffer = await blob.arrayBuffer();
    const bytes = Array.from(new Uint8Array(arrayBuffer));
    const filename = resp.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1] || 'resume.pdf';
    const mimeType = blob.type || 'application/pdf';
    return { bytes, filename, mimeType };
  } catch (err) {
    return { error: err.message };
  }
}

// ── Manual URL submission ─────────────────────────────────────────────────────
async function submitUrl(url) {
  try {
    const data = await fetchJSON('/api/v1/jobs/manual', {
      method: 'POST',
      body: { url, title: '', company: '' },
    });
    return { ok: true, jobId: data.job_id };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ── Popup broadcast ───────────────────────────────────────────────────────────
function broadcastToPopup(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {}); // ignore if popup closed
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────
async function fetchJSON(path, options = {}) {
  const url = `${BACKEND}${path}`;
  const init = {
    method: options.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
  };
  if (options.body) init.body = JSON.stringify(options.body);

  const resp = await fetch(url, init);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} ${path}`);
  return resp.json();
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
