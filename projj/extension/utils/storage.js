'use strict';

const storage = {
  get: (keys) => chrome.storage.local.get(keys),
  set: (data) => chrome.storage.local.set(data),
  getAutoApply: async () => { const { autoApply } = await chrome.storage.local.get('autoApply'); return autoApply !== false; },
  setAutoApply: (val) => chrome.storage.local.set({ autoApply: val }),
};
