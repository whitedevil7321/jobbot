'use strict';

const API_BASE = 'http://localhost:8000/api/v1';

async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const init = { method: options.method || 'GET', headers: { 'Content-Type': 'application/json' } };
  if (options.body) init.body = JSON.stringify(options.body);
  const resp = await fetch(url, init);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} — ${path}`);
  return resp.json();
}

const api = {
  getProfile:    ()       => apiFetch('/profile'),
  saveProfile:   (data)   => apiFetch('/profile', { method: 'POST', body: data }),
  getStats:      ()       => apiFetch('/applications/stats'),
  getQueue:      ()       => apiFetch('/jobs?status=queued&sort_by=priority&limit=1'),
  submitUrl:     (url)    => apiFetch('/jobs/manual', { method: 'POST', body: { url } }),
  reportResult:  (data)   => apiFetch('/extension/result', { method: 'POST', body: data }),
  askLLM:        (q, ctx, hint) => apiFetch('/ollama/answer', { method: 'POST', body: { question: q, context: ctx, type_hint: hint } }),
};

if (typeof module !== 'undefined') module.exports = api;
