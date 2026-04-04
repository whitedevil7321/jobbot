/**
 * JobBot Autofill Content Script
 * Injected into job application pages by the background service worker.
 * Handles: field detection, form filling, resume upload, multi-step navigation,
 * success detection, and stuck reporting.
 */

(function JobBotAutofill() {
  'use strict';

  // Prevent double-injection
  if (window.__jobbot_injected) return;
  window.__jobbot_injected = true;

  let _profile = null;
  let _jobId = null;
  let _step = 0;
  let _screeningAnswers = {};
  let _isRunning = false;

  // ── Message listener ─────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'START_APPLY') {
      _profile = msg.profile;
      _jobId = msg.jobId;
      _step = msg.step || 0;
      sendResponse({ ok: true });
      if (!_isRunning) runApplyLoop();
    }
    if (msg.type === 'GET_STATUS') {
      sendResponse({ step: _step, running: _isRunning, url: location.href });
    }
  });

  // Signal ready to background
  chrome.runtime.sendMessage({ type: 'CONTENT_READY', url: location.href });

  // ── Main apply loop ──────────────────────────────────────────────────────
  async function runApplyLoop() {
    _isRunning = true;
    progress('Analyzing page...');

    await sleep(1000);

    // Handle login prompts (prefer guest/no-account path)
    await handleLoginPrompt();

    // Click Apply button if on a listing page
    const clickedApply = await clickApplyButton();
    if (clickedApply) {
      progress('Clicked Apply button, waiting...');
      await sleep(2000);
    }

    // If there are no form inputs yet, try one more apply click
    if (!hasFormInputs()) {
      const secondClick = await clickApplyButton();
      if (secondClick) await sleep(2000);
    }

    // Check for immediate success (already applied)
    if (isSuccess()) {
      return reportResult('submitted', 'Already applied or immediate success');
    }

    // Multi-step form loop
    let prevUrl = location.href;
    const MAX_STEPS = 15;

    for (let i = 0; i < MAX_STEPS; i++) {
      progress(`Step ${i + 1}: filling form...`);

      if (isSuccess()) return reportResult('submitted');

      // Fill all visible form fields
      await fillAllFields();

      // Handle file/resume inputs
      await handleResumeUpload();

      await sleep(500);

      if (isSuccess()) return reportResult('submitted');

      // Try to click Next / Submit
      const proceeded = await clickNextOrSubmit();
      if (!proceeded) {
        // Check for unfilled required fields
        const unfilled = findUnfilledRequired();
        if (unfilled.length > 0) {
          progress(`Trying to fill ${unfilled.length} required fields...`);
          for (const el of unfilled) await fillElement(el, await getLabel(el));
          await sleep(500);
          const retried = await clickNextOrSubmit();
          if (!retried) {
            return reportResult('stuck', `Cannot fill required fields: ${unfilled.slice(0, 3).map(e => getLabel(e)).join(', ')}`);
          }
        } else {
          return reportResult('stuck', 'Cannot find Next or Submit button');
        }
      }

      progress('Waiting for page response...');
      await sleep(2500);
      await dismissPopups();

      if (isSuccess()) return reportResult('submitted');

      // If URL didn't change (dynamic SPA), check if form changed
      if (location.href === prevUrl) {
        await sleep(1500);
        if (isSuccess()) return reportResult('submitted');
        // If still same page & same form, we're stuck
        if (!hasFormInputs()) {
          return reportResult('stuck', 'Page did not advance after submit');
        }
      }

      prevUrl = location.href;
    }

    return reportResult('stuck', 'Maximum form steps (15) reached');
  }

  // ── Field filling ────────────────────────────────────────────────────────
  async function fillAllFields() {
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="file"]):not([type="reset"]):not([type="image"]):not([type="checkbox"]):not([type="radio"]),' +
      'textarea,' +
      'select'
    );

    for (const el of inputs) {
      if (!isVisible(el)) continue;
      if (el.value && el.value.trim() && el.type !== 'select-one') continue; // skip filled
      const label = await getLabel(el);
      if (!label) continue;
      await fillElement(el, label);
      await sleep(80);
    }

    // Handle checkboxes and radios
    await handleCheckboxesAndRadios();
  }

  async function fillElement(el, label) {
    const tag = el.tagName.toLowerCase();
    const type = (el.type || '').toLowerCase();
    const labelLower = label.toLowerCase();

    // Map label to profile value
    const value = mapLabelToValue(labelLower, el);

    if (value === null || value === undefined) {
      // Unknown field — ask LLM
      const llmAnswer = await askLLMWithContext(label, el);
      if (llmAnswer) {
        await setFieldValue(el, llmAnswer);
        _screeningAnswers[label] = llmAnswer;
      }
      return;
    }

    if (value === '__SKIP__') return;

    if (tag === 'select') {
      await selectOption(el, value);
    } else {
      await setFieldValue(el, value);
    }
  }

  function mapLabelToValue(label, el) {
    const p = _profile;
    if (!p) return null;

    // ── Personal ─────────────────────────────────────────────────────────
    if (matches(label, ['first name', 'firstname', 'given name'])) {
      return p.full_name?.split(' ')[0] || p.full_name;
    }
    if (matches(label, ['last name', 'lastname', 'surname', 'family name'])) {
      const parts = (p.full_name || '').split(' ');
      return parts.slice(1).join(' ') || parts[0];
    }
    if (matches(label, ['full name', 'name', 'your name', 'legal name'])) return p.full_name;
    if (matches(label, ['email', 'e-mail', 'email address'])) return p.email;
    if (matches(label, ['phone', 'mobile', 'telephone', 'cell', 'phone number'])) return p.phone;

    // ── Location ─────────────────────────────────────────────────────────
    if (matches(label, ['address', 'street', 'street address', 'address line 1'])) return p.address;
    if (matches(label, ['city', 'city / town'])) return p.city;
    if (matches(label, ['state', 'state / province', 'province'])) return p.state;
    if (matches(label, ['zip', 'zip code', 'postal', 'postal code'])) return p.zip_code;
    if (matches(label, ['country'])) return p.country || 'United States';
    if (matches(label, ['location', 'current location', 'where are you located'])) return p.location;

    // ── Professional ─────────────────────────────────────────────────────
    if (matches(label, ['linkedin', 'linkedin url', 'linkedin profile'])) return p.linkedin_url;
    if (matches(label, ['github', 'github url', 'github profile'])) return p.github_url;
    if (matches(label, ['portfolio', 'website', 'personal website', 'portfolio url'])) return p.portfolio_url;
    if (matches(label, ['years of experience', 'years experience', 'experience', 'total experience'])) {
      return String(p.years_of_exp || 0);
    }
    if (matches(label, ['summary', 'professional summary', 'about you', 'cover letter', 'tell us about yourself'])) {
      return p.summary || '';
    }

    // ── Education ────────────────────────────────────────────────────────
    if (matches(label, ['school', 'university', 'college', 'institution', 'school name'])) return p.school_name;
    if (matches(label, ['degree', 'degree level', 'degree type'])) return p.degree;
    if (matches(label, ['major', 'field of study', 'area of study'])) return p.degree;
    if (matches(label, ['graduation year', 'year of graduation', 'graduation date'])) {
      return p.graduation_year ? String(p.graduation_year) : null;
    }
    if (matches(label, ['highest education', 'highest level of education', 'education level'])) {
      return p.highest_education;
    }

    // ── Salary ───────────────────────────────────────────────────────────
    if (matches(label, ['salary', 'salary expectation', 'expected salary', 'desired salary'])) {
      const mid = p.desired_salary_min && p.desired_salary_max
        ? Math.round((p.desired_salary_min + p.desired_salary_max) / 2)
        : p.desired_salary_min || p.desired_salary_max;
      return mid ? String(mid) : null;
    }
    if (matches(label, ['minimum salary', 'salary minimum', 'min salary'])) {
      return p.desired_salary_min ? String(p.desired_salary_min) : null;
    }
    if (matches(label, ['maximum salary', 'salary maximum', 'max salary'])) {
      return p.desired_salary_max ? String(p.desired_salary_max) : null;
    }

    // ── Work auth ────────────────────────────────────────────────────────
    if (matches(label, ['work authorization', 'work auth', 'authorized to work', 'eligible to work'])) {
      const authMap = {
        citizen: 'US Citizen',
        greencard: 'Green Card',
        h1b: 'H-1B',
        opt: 'OPT',
        tn: 'TN Visa',
      };
      return authMap[p.work_auth] || p.work_auth;
    }
    if (matches(label, ['sponsorship', 'visa sponsorship', 'require sponsorship', 'need sponsorship'])) {
      return p.visa_sponsorship_needed ? 'Yes' : 'No';
    }

    // ── EEO ─────────────────────────────────────────────────────────────
    if (matches(label, ['gender', 'sex'])) return p.gender || 'Prefer not to say';
    if (matches(label, ['ethnicity', 'race', 'ethnic background'])) return p.ethnicity || 'Prefer not to say';
    if (matches(label, ['veteran', 'veteran status', 'military'])) return p.veteran_status || 'I am not a veteran';
    if (matches(label, ['disability', 'disability status'])) return p.disability_status || "I don't wish to answer";

    // ── Yes/No questions ─────────────────────────────────────────────────
    if (matches(label, ['are you 18', 'at least 18', 'legal age'])) return 'Yes';
    if (matches(label, ['felony', 'convicted'])) return 'No';
    if (matches(label, ['background check', 'drug test'])) return 'Yes';
    if (matches(label, ['remote', 'work remote', 'open to remote'])) return 'Yes';
    if (matches(label, ['relocate', 'willing to relocate', 'open to relocation'])) return 'Yes';

    return null; // Unknown — will trigger LLM
  }

  function matches(label, keywords) {
    return keywords.some(k => label.includes(k));
  }

  // ── Select handling ──────────────────────────────────────────────────────
  async function selectOption(el, value) {
    const options = Array.from(el.options);
    const valueLower = (value || '').toLowerCase();

    // Exact match first
    let opt = options.find(o => o.value.toLowerCase() === valueLower || o.text.toLowerCase() === valueLower);

    // Partial match
    if (!opt) opt = options.find(o => o.text.toLowerCase().includes(valueLower) || valueLower.includes(o.text.toLowerCase().trim()));

    // For yes/no
    if (!opt && ['yes', 'true', '1'].includes(valueLower)) {
      opt = options.find(o => ['yes', 'true', '1', 'agree'].includes(o.text.toLowerCase().trim()));
    }
    if (!opt && ['no', 'false', '0'].includes(valueLower)) {
      opt = options.find(o => ['no', 'false', '0', 'disagree'].includes(o.text.toLowerCase().trim()));
    }

    if (opt) {
      el.value = opt.value;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  // ── Checkboxes & Radios ──────────────────────────────────────────────────
  async function handleCheckboxesAndRadios() {
    const groups = new Map();

    // Group radios by name
    document.querySelectorAll('input[type="radio"]').forEach(el => {
      if (!isVisible(el)) return;
      const name = el.name || el.id;
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(el);
    });

    for (const [name, radios] of groups) {
      if (radios.some(r => r.checked)) continue; // already selected
      const label = await getGroupLabel(radios[0]);
      const labelLower = (label || '').toLowerCase();

      // Find the best option
      let selected = null;

      if (labelLower.includes('sponsorship') || labelLower.includes('visa')) {
        const target = _profile?.visa_sponsorship_needed ? 'yes' : 'no';
        selected = radios.find(r => getRadioText(r).toLowerCase().includes(target));
      } else if (labelLower.includes('authorized') || labelLower.includes('eligible')) {
        selected = radios.find(r => getRadioText(r).toLowerCase().includes('yes'));
      } else if (labelLower.includes('veteran')) {
        const v = (_profile?.veteran_status || '').toLowerCase();
        selected = radios.find(r => {
          const t = getRadioText(r).toLowerCase();
          if (v.includes('not a veteran')) return t.includes('not') || t.includes('no');
          return t.includes('yes') || t.includes('veteran');
        });
      } else if (labelLower.includes('disability')) {
        selected = radios.find(r => {
          const t = getRadioText(r).toLowerCase();
          return t.includes('not') || t.includes("don't") || t.includes('prefer not') || t.includes('decline');
        });
      } else {
        // Ask LLM for radio groups
        const optionTexts = radios.map(r => getRadioText(r)).join(', ');
        const answer = await askLLM(`Question: ${label}\nOptions: ${optionTexts}`, 'radio');
        if (answer) {
          const answerLower = answer.toLowerCase();
          selected = radios.find(r => {
            const t = getRadioText(r).toLowerCase();
            return t.includes(answerLower) || answerLower.includes(t);
          });
        }
        if (!selected) selected = radios[0]; // fallback to first option
      }

      if (selected && !selected.disabled) {
        selected.checked = true;
        selected.dispatchEvent(new Event('change', { bubbles: true }));
        selected.dispatchEvent(new Event('click', { bubbles: true }));
        await sleep(100);
      }
    }

    // Checkboxes (agreement, terms, etc.)
    document.querySelectorAll('input[type="checkbox"]').forEach(el => {
      if (!isVisible(el) || el.checked) return;
      const label = (el.labels?.[0]?.textContent || el.getAttribute('aria-label') || '').toLowerCase();
      if (label.includes('terms') || label.includes('agree') || label.includes('accept') || label.includes('policy')) {
        el.checked = true;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }

  function getRadioText(el) {
    return el.labels?.[0]?.textContent?.trim()
      || el.parentElement?.textContent?.trim()
      || el.value
      || '';
  }

  // ── Resume upload ────────────────────────────────────────────────────────
  async function handleResumeUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    for (const input of fileInputs) {
      if (!isVisible(input)) continue;
      const label = (input.labels?.[0]?.textContent || input.getAttribute('aria-label') || '').toLowerCase();
      const isResumeInput = label.includes('resume') || label.includes('cv') || label.includes('document') || !label;
      if (!isResumeInput) continue;
      if (input.files?.length > 0) continue; // already has a file

      progress('Uploading resume...');

      const resumeData = await chrome.runtime.sendMessage({ type: 'GET_RESUME' });
      if (!resumeData || resumeData.error) {
        progress('No resume file found — skipping upload');
        continue;
      }

      try {
        const uint8 = new Uint8Array(resumeData.bytes);
        const blob = new Blob([uint8], { type: resumeData.mimeType });
        const file = new File([blob], resumeData.filename, { type: resumeData.mimeType });
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('input', { bubbles: true }));
        progress('Resume uploaded');
        await sleep(1000);
      } catch (err) {
        console.warn('[JobBot] Resume upload error:', err.message);
      }
    }
  }

  // ── Button clicking ──────────────────────────────────────────────────────
  async function clickApplyButton() {
    const selectors = [
      'button[data-qa="btn-apply"]',
      'a[data-qa="btn-apply"]',
      'button:not([type="submit"]):is([id*="apply"],[class*="apply"])',
      'a:is([id*="apply"],[class*="apply"])',
    ];
    const texts = ['apply now', 'apply for this job', 'apply for job', 'apply to job', 'apply here', 'start application', 'begin application', 'apply online', 'easy apply', '1-click apply'];

    // Try selector-based
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && isVisible(el) && !el.disabled) {
        await clickElement(el);
        return true;
      }
    }

    // Try text-based
    const allButtons = [...document.querySelectorAll('a, button')];
    for (const el of allButtons) {
      if (!isVisible(el)) continue;
      const text = (el.textContent || '').trim().toLowerCase();
      if (texts.some(t => text === t || text.includes(t))) {
        await clickElement(el);
        return true;
      }
    }

    return false;
  }

  async function clickNextOrSubmit() {
    const submitTexts = ['submit', 'submit application', 'submit my application', 'complete application', 'send application'];
    const nextTexts = ['next', 'next step', 'continue', 'proceed', 'save and continue', 'save & continue'];

    const allButtons = [...document.querySelectorAll('button, input[type="submit"], [role="button"]')];

    // Prefer submit over next
    for (const text of submitTexts) {
      const btn = allButtons.find(b => isVisible(b) && !b.disabled && (b.textContent || b.value || '').trim().toLowerCase().includes(text));
      if (btn) { await clickElement(btn); return true; }
    }

    for (const text of nextTexts) {
      const btn = allButtons.find(b => isVisible(b) && !b.disabled && (b.textContent || b.value || '').trim().toLowerCase().includes(text));
      if (btn) { await clickElement(btn); return true; }
    }

    // Try submit type
    const submitBtn = document.querySelector('button[type="submit"], input[type="submit"]');
    if (submitBtn && isVisible(submitBtn) && !submitBtn.disabled) {
      await clickElement(submitBtn);
      return true;
    }

    return false;
  }

  async function handleLoginPrompt() {
    const guestTexts = [
      'apply without signing in',
      'continue as guest',
      'apply as guest',
      'apply without account',
      'skip sign in',
      'continue without',
      'apply without creating',
    ];
    const all = [...document.querySelectorAll('a, button')];
    for (const el of all) {
      const text = (el.textContent || '').trim().toLowerCase();
      if (guestTexts.some(t => text.includes(t))) {
        await clickElement(el);
        await sleep(1500);
        return;
      }
    }
  }

  async function dismissPopups() {
    // Close modal dialogs, cookie banners, etc.
    const closeSelectors = [
      '[aria-label="Close"]', '[aria-label="close"]', '[aria-label="Dismiss"]',
      'button.close', '.modal-close', '.dialog-close',
      'button[data-dismiss]',
    ];
    for (const sel of closeSelectors) {
      const el = document.querySelector(sel);
      if (el && isVisible(el)) { await clickElement(el); await sleep(300); }
    }
  }

  // ── Success detection ────────────────────────────────────────────────────
  function isSuccess() {
    const bodyText = document.body?.innerText?.toLowerCase() || '';
    const successPatterns = [
      'application submitted', 'application received', 'application complete',
      'thank you for applying', 'thank you for your application',
      'we have received your application', 'successfully applied',
      'application was submitted', 'you have applied', 'already applied',
      'your application has been', 'submission confirmed',
    ];
    return successPatterns.some(p => bodyText.includes(p));
  }

  function hasFormInputs() {
    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]), textarea, select');
    return [...inputs].some(el => isVisible(el));
  }

  function findUnfilledRequired() {
    return [...document.querySelectorAll(
      'input[required]:not([type="hidden"]):not([type="submit"]):not([type="file"]),' +
      'textarea[required], select[required], [aria-required="true"]'
    )].filter(el => isVisible(el) && !(el.value || '').trim());
  }

  // ── Label extraction ─────────────────────────────────────────────────────
  async function getLabel(el) {
    // Direct label element
    if (el.labels?.length) return el.labels[0].textContent.trim();

    // aria-label
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel.trim();

    // aria-labelledby
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const labelEl = document.getElementById(labelledBy);
      if (labelEl) return labelEl.textContent.trim();
    }

    // for= attribute
    const id = el.id;
    if (id) {
      const labelEl = document.querySelector(`label[for="${id}"]`);
      if (labelEl) return labelEl.textContent.trim();
    }

    // Placeholder
    if (el.placeholder) return el.placeholder.trim();

    // name attribute
    return (el.name || el.getAttribute('data-field') || '').replace(/[-_]/g, ' ');
  }

  async function getGroupLabel(el) {
    // For radio/checkbox groups, get the fieldset legend or parent label
    const fieldset = el.closest('fieldset');
    if (fieldset) {
      const legend = fieldset.querySelector('legend');
      if (legend) return legend.textContent.trim();
    }

    const parent = el.closest('[role="group"]') || el.parentElement?.parentElement;
    if (parent) {
      const label = parent.querySelector('label, .label, [class*="label"], p, span');
      if (label) return label.textContent.trim();
    }

    return await getLabel(el);
  }

  // ── LLM integration ──────────────────────────────────────────────────────
  async function askLLMWithContext(label, el) {
    const typeHint = el.tagName === 'TEXTAREA' ? 'text' : 'short';
    const context = buildLLMContext();
    return await askLLM(label, typeHint, context);
  }

  async function askLLM(question, typeHint, context) {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'ASK_LLM',
        question,
        type_hint: typeHint || 'text',
        context: context || buildLLMContext(),
      });
      return response?.answer || '';
    } catch {
      return '';
    }
  }

  function buildLLMContext() {
    if (!_profile) return '';
    return `
Name: ${_profile.full_name}
Email: ${_profile.email}
Phone: ${_profile.phone || ''}
Location: ${_profile.location || ''}
Years of experience: ${_profile.years_of_exp || 0}
Skills: ${(_profile.skills || []).join(', ')}
Target roles: ${(_profile.target_roles || []).join(', ')}
Education: ${_profile.degree || ''} from ${_profile.school_name || ''}
Work auth: ${_profile.work_auth || 'citizen'}
Summary: ${_profile.summary || ''}
`.trim();
  }

  // ── DOM helpers ──────────────────────────────────────────────────────────
  async function setFieldValue(el, value) {
    if (!el || value === null || value === undefined) return;
    const strVal = String(value);

    // React-style value setter (works with controlled inputs)
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
      || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;

    if (nativeInputValueSetter && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      nativeInputValueSetter.call(el, strVal);
    } else {
      el.value = strVal;
    }

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  }

  async function clickElement(el) {
    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await sleep(200);
      el.click();
      el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    } catch (err) {
      console.warn('[JobBot] Click error:', err.message);
    }
  }

  function isVisible(el) {
    if (!el || !el.offsetParent && el.tagName !== 'INPUT') return false;
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  // ── Reporting ────────────────────────────────────────────────────────────
  function progress(message) {
    console.log(`[JobBot] ${message}`);
    chrome.runtime.sendMessage({
      type: 'APPLY_PROGRESS',
      message,
      step: _step,
      jobId: _jobId,
    }).catch(() => {});
    showOverlay(message);
  }

  function reportResult(status, reason) {
    _isRunning = false;
    const msg = { type: 'APPLY_RESULT', status, reason: reason || null, jobId: _jobId, screeningAnswers: _screeningAnswers };
    console.log('[JobBot] Result:', status, reason || '');
    chrome.runtime.sendMessage(msg).catch(() => {});
    if (status === 'submitted') showOverlay('✅ Application submitted!', 'success');
    else if (status === 'stuck') showOverlay(`⚠️ Stuck: ${reason}`, 'warning');
    else showOverlay(`❌ Failed: ${reason}`, 'error');
  }

  // ── Visual overlay ───────────────────────────────────────────────────────
  function showOverlay(message, type = 'info') {
    let overlay = document.getElementById('__jobbot_overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = '__jobbot_overlay';
      overlay.style.cssText = `
        position: fixed; top: 16px; right: 16px; z-index: 2147483647;
        background: #111827; border: 1px solid #374151;
        border-radius: 10px; padding: 12px 16px; font-family: system-ui, sans-serif;
        font-size: 13px; color: #e5e7eb; box-shadow: 0 4px 24px rgba(0,0,0,0.5);
        max-width: 320px; word-wrap: break-word; transition: opacity 0.3s;
        display: flex; align-items: center; gap: 8px;
      `;
      document.body.appendChild(overlay);
    }

    const colors = { success: '#10b981', warning: '#f59e0b', error: '#ef4444', info: '#8b5cf6' };
    const icons = { success: '✅', warning: '⚠️', error: '❌', info: '⚡' };

    overlay.style.borderColor = colors[type] || colors.info;
    overlay.innerHTML = `
      <span style="font-size:16px">${icons[type] || icons.info}</span>
      <div>
        <div style="font-weight:600;color:#fff;margin-bottom:2px">JobBot</div>
        <div style="color:#9ca3af">${escapeHtml(message)}</div>
      </div>
    `;
    overlay.style.opacity = '1';

    // Auto-hide after 4s for info messages
    if (type === 'info') {
      setTimeout(() => { if (overlay) overlay.style.opacity = '0.4'; }, 4000);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }
})();
