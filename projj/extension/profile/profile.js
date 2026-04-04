'use strict';

const BACKEND = 'http://localhost:8000';

// ── Tag input state ───────────────────────────────────────────────────────────
const tagFields = ['skills', 'target_roles', 'target_domains'];
const tagState = { skills: [], target_roles: [], target_domains: [] };

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  setupTagInputs();
  setupResumeUpload();
  setupNavigation();
  await loadProfile();
  setupSave();
}

// ── Load profile from backend ─────────────────────────────────────────────────
async function loadProfile() {
  try {
    const resp = await fetch(`${BACKEND}/api/v1/profile`);
    if (!resp.ok) throw new Error('Backend offline');
    const data = await resp.json();
    populateForm(data);
    updateCompletion();
  } catch (err) {
    showSaveMsg('Could not load profile — is the backend running?', false);
  }
}

function populateForm(data) {
  const textFields = [
    'full_name','email','phone','location','address','city','state','zip_code',
    'linkedin_url','github_url','portfolio_url','summary',
    'school_name','degree','graduation_year','highest_education',
    'desired_salary_min','desired_salary_max','work_auth',
    'gender','ethnicity','veteran_status','disability_status','salary_currency','country',
    'years_of_exp',
  ];
  for (const f of textFields) {
    const el = document.getElementById(f);
    if (el && data[f] != null) el.value = data[f];
  }

  const checkbox = document.getElementById('visa_sponsorship_needed');
  if (checkbox) checkbox.checked = !!data.visa_sponsorship_needed;

  // Tag fields
  for (const f of tagFields) {
    const arr = Array.isArray(data[f]) ? data[f] : [];
    tagState[f] = arr;
    renderTags(f);
  }

  // Resume
  if (data.resume_path) {
    const name = data.resume_path.split(/[\\/]/).pop();
    showResumeUploaded(name, 'Saved on server');
  }
}

// ── Save profile ──────────────────────────────────────────────────────────────
function setupSave() {
  document.getElementById('save-btn').addEventListener('click', saveProfile);

  // Auto-save on field blur
  document.querySelectorAll('input:not([type="file"]):not([type="checkbox"]):not(.tag-input), select, textarea').forEach(el => {
    el.addEventListener('change', updateCompletion);
  });
}

async function saveProfile() {
  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  const payload = gatherPayload();

  try {
    const resp = await fetch(`${BACKEND}/api/v1/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showSaveMsg('✓ Profile saved!', true);
    updateCompletion();
  } catch (err) {
    showSaveMsg(`Error: ${err.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Profile';
  }
}

function gatherPayload() {
  const get = id => {
    const el = document.getElementById(id);
    if (!el) return null;
    if (el.type === 'checkbox') return el.checked;
    if (el.type === 'number') return el.value === '' ? null : Number(el.value);
    return el.value || null;
  };

  return {
    full_name:              get('full_name')              || '',
    email:                  get('email')                  || '',
    phone:                  get('phone'),
    location:               get('location'),
    address:                get('address'),
    city:                   get('city'),
    state:                  get('state'),
    zip_code:               get('zip_code'),
    country:                get('country')                || 'United States',
    linkedin_url:           get('linkedin_url'),
    github_url:             get('github_url'),
    portfolio_url:          get('portfolio_url'),
    years_of_exp:           get('years_of_exp')           ?? 0,
    work_auth:              get('work_auth')               || 'citizen',
    visa_sponsorship_needed: get('visa_sponsorship_needed'),
    summary:                get('summary'),
    school_name:            get('school_name'),
    degree:                 get('degree'),
    graduation_year:        get('graduation_year'),
    highest_education:      get('highest_education'),
    desired_salary_min:     get('desired_salary_min'),
    desired_salary_max:     get('desired_salary_max'),
    salary_currency:        get('salary_currency')        || 'USD',
    gender:                 get('gender'),
    ethnicity:              get('ethnicity'),
    veteran_status:         get('veteran_status')         || 'I am not a veteran',
    disability_status:      get('disability_status')      || "I don't wish to answer",
    skills:                 [...tagState.skills],
    target_roles:           [...tagState.target_roles],
    target_domains:         [...tagState.target_domains],
  };
}

// ── Resume upload ─────────────────────────────────────────────────────────────
function setupResumeUpload() {
  const zone     = document.getElementById('resume-zone');
  const fileInput = document.getElementById('resume-file');
  const removeBtn = document.getElementById('resume-remove');

  zone.addEventListener('click', () => fileInput.click());

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) uploadResume(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) uploadResume(fileInput.files[0]);
  });

  removeBtn.addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('resume-uploaded').style.display = 'none';
    zone.style.display = '';
    fileInput.value = '';
  });
}

async function uploadResume(file) {
  const allowed = ['.pdf', '.docx', '.doc'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!allowed.includes('.' + ext)) {
    alert('Only PDF and DOCX files are allowed.');
    return;
  }

  const uploading = document.getElementById('resume-uploading');
  uploading.style.display = 'block';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const resp = await fetch(`${BACKEND}/api/v1/profile/resume`, {
      method: 'POST',
      body: fd,
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    showResumeUploaded(file.name, data.text_extracted ? 'Text extracted ✓' : 'Uploaded (no text extracted)');
    showSaveMsg('✓ Resume uploaded!', true);
  } catch (err) {
    alert('Upload failed: ' + err.message);
  } finally {
    uploading.style.display = 'none';
  }
}

function showResumeUploaded(name, sub) {
  document.getElementById('resume-zone').style.display = 'none';
  document.getElementById('resume-uploaded').style.display = 'flex';
  document.getElementById('resume-name').textContent = name;
  document.getElementById('resume-sub').textContent = sub;
}

// ── Tag inputs ────────────────────────────────────────────────────────────────
function setupTagInputs() {
  for (const field of tagFields) {
    const input = document.getElementById(`${field}-input`);
    const container = document.getElementById(`${field}-container`);

    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        addTag(field, input.value.trim());
        input.value = '';
      } else if (e.key === 'Backspace' && input.value === '' && tagState[field].length > 0) {
        removeTag(field, tagState[field].length - 1);
      }
    });

    input.addEventListener('blur', () => {
      if (input.value.trim()) {
        addTag(field, input.value.trim());
        input.value = '';
      }
    });

    container.addEventListener('click', () => input.focus());
  }
}

function addTag(field, value) {
  if (!value || tagState[field].includes(value)) return;
  tagState[field].push(value);
  renderTags(field);
  updateCompletion();
}

function removeTag(field, index) {
  tagState[field].splice(index, 1);
  renderTags(field);
  updateCompletion();
}

function renderTags(field) {
  const container = document.getElementById(`${field}-container`);
  const input = document.getElementById(`${field}-input`);

  // Remove existing tags
  container.querySelectorAll('.tag').forEach(t => t.remove());

  // Insert tags before the input
  for (let i = 0; i < tagState[field].length; i++) {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.innerHTML = `${escHtml(tagState[field][i])}<button class="tag-remove" data-i="${i}" title="Remove">×</button>`;
    tag.querySelector('.tag-remove').addEventListener('click', e => {
      e.stopPropagation();
      removeTag(field, parseInt(e.target.dataset.i));
    });
    container.insertBefore(tag, input);
  }
}

// ── Sidebar navigation ────────────────────────────────────────────────────────
function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const section = document.getElementById(`section-${btn.dataset.section}`);
      if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // Highlight active nav on scroll
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const id = e.target.id.replace('section-', '');
        document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.section === id));
      }
    });
  }, { rootMargin: '-20% 0px -60% 0px' });

  document.querySelectorAll('[id^="section-"]').forEach(el => observer.observe(el));
}

// ── Completion progress ───────────────────────────────────────────────────────
function updateCompletion() {
  const required = ['full_name', 'email', 'location', 'years_of_exp', 'work_auth'];
  const optional = [
    'phone', 'address', 'city', 'state', 'zip_code', 'linkedin_url', 'github_url',
    'portfolio_url', 'summary', 'school_name', 'degree', 'graduation_year',
    'highest_education', 'desired_salary_min', 'desired_salary_max',
    'gender', 'ethnicity',
  ];

  let filled = 0;
  const total = required.length + optional.length + 3; // +3 for tag fields

  for (const id of [...required, ...optional]) {
    const el = document.getElementById(id);
    if (el && el.value && el.value.trim()) filled++;
  }

  for (const f of tagFields) {
    if (tagState[f].length > 0) filled++;
  }

  const pct = Math.round((filled / total) * 100);
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function showSaveMsg(msg, ok) {
  const el = document.getElementById('save-msg');
  el.textContent = msg;
  el.className = `save-msg visible ${ok ? 'ok' : 'err'}`;
  if (ok) setTimeout(() => el.classList.remove('visible'), 3000);
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Start ─────────────────────────────────────────────────────────────────────
init();
