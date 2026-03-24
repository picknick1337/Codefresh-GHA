const sourceInput = document.getElementById('source-yaml');
const workflowNameInput = document.getElementById('workflow-name');
const workflowOutput = document.getElementById('workflow-output');
const warningsList = document.getElementById('warnings-list');
const checklistList = document.getElementById('checklist-list');
const stepList = document.getElementById('step-list');
const fileInput = document.getElementById('file-input');
const statusLine = document.getElementById('status-line');

let debounceTimer = null;
let state = { latest: null, overrides: {} };

function scheduleTranslate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runTranslate, 250);
}

async function runTranslate() {
  const payload = {
    source_yaml: sourceInput.value,
    workflow_name: workflowNameInput.value || 'Converted from Codefresh',
    step_overrides: state.overrides,
  };

  if (!payload.source_yaml.trim()) {
    workflowOutput.textContent = '';
    warningsList.innerHTML = '';
    checklistList.innerHTML = '';
    stepList.innerHTML = '';
    statusLine.textContent = 'Paste Codefresh YAML to start.';
    return;
  }

  statusLine.textContent = 'Translating…';
  const response = await fetch('/api/translate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    workflowOutput.textContent = '';
    stepList.innerHTML = '';
    warningsList.innerHTML = '';
    checklistList.innerHTML = '';
    statusLine.textContent = data.error || 'Translation failed.';
    return;
  }

  state.latest = data;
  workflowOutput.textContent = data.workflow_yaml;
  renderWarnings(data.warnings);
  renderChecklist(data.checklist);
  renderSteps(data.steps);
  statusLine.textContent = `Translated ${data.source_summary.step_count} step(s).`;
}

function renderWarnings(warnings) {
  warningsList.innerHTML = '';
  if (!warnings.length) {
    warningsList.innerHTML = '<li>No pipeline-level warnings.</li>';
    return;
  }
  for (const warning of warnings) {
    const li = document.createElement('li');
    li.className = 'warning';
    li.textContent = warning.step ? `[${warning.code}] ${warning.step}: ${warning.message}` : `[${warning.code}] ${warning.message}`;
    warningsList.appendChild(li);
  }
}

function renderChecklist(items) {
  checklistList.innerHTML = '';
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    checklistList.appendChild(li);
  }
}

function renderSteps(steps) {
  stepList.innerHTML = '';
  for (const step of steps) {
    const card = document.createElement('article');
    card.className = 'step-card';
    card.innerHTML = `
      <header>
        <div>
          <h3>${escapeHtml(step.source_name)}</h3>
          <div class="step-meta">type=${escapeHtml(step.step_type)}${step.stage ? ` · stage=${escapeHtml(step.stage)}` : ''}${step.source_image ? ` · image=${escapeHtml(step.source_image)}` : ''}</div>
        </div>
        <div>${(step.detected_tools || []).map(tool => `<span class="badge">${escapeHtml(tool)}</span>`).join('')}</div>
      </header>
      <div class="step-grid">
        <label>Generated step name<input data-step="${escapeAttr(step.source_name)}" data-field="name" value="${escapeAttr(step.gha_step.name || '')}"></label>
        <label>uses<input data-step="${escapeAttr(step.source_name)}" data-field="uses" value="${escapeAttr(step.gha_step.uses || '')}"></label>
        <label style="grid-column: 1 / -1;">run<textarea data-step="${escapeAttr(step.source_name)}" data-field="run">${escapeHtml(step.gha_step.run || '')}</textarea></label>
      </div>
    `;

    card.appendChild(renderList('Rationale', step.rationale));
    card.appendChild(renderList('Step checklist', step.checklist));
    if (step.translation_hints?.length) {
      card.appendChild(renderList('Translation hints', step.translation_hints));
    }
    if (step.warnings?.length) {
      card.appendChild(renderList('Step warnings', step.warnings.map(w => w.suggestion ? `${w.message} — ${w.suggestion}` : w.message)));
    }
    stepList.appendChild(card);
  }

  stepList.querySelectorAll('input[data-step], textarea[data-step]').forEach((element) => {
    element.addEventListener('input', event => {
      const target = event.target;
      const stepName = target.dataset.step;
      const field = target.dataset.field;
      state.overrides[stepName] = state.overrides[stepName] || {};
      state.overrides[stepName][field] = target.value;
      scheduleTranslate();
    });
  });
}

function renderList(title, items) {
  const wrapper = document.createElement('section');
  const heading = document.createElement('div');
  heading.className = 'list-title';
  heading.textContent = title;
  wrapper.appendChild(heading);
  const list = document.createElement('ul');
  list.className = 'plain-list';
  for (const item of items || []) {
    const li = document.createElement('li');
    li.textContent = item;
    list.appendChild(li);
  }
  wrapper.appendChild(list);
  return wrapper;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('\n', '&#10;');
}

document.getElementById('load-sample').addEventListener('click', () => {
  sourceInput.value = window.CF2GHA_SAMPLE;
  state.overrides = {};
  scheduleTranslate();
});
workflowNameInput.addEventListener('input', scheduleTranslate);
sourceInput.addEventListener('input', () => {
  state.overrides = {};
  scheduleTranslate();
});
fileInput.addEventListener('change', async () => {
  const [file] = fileInput.files;
  if (!file) return;
  sourceInput.value = await file.text();
  state.overrides = {};
  scheduleTranslate();
});
document.getElementById('copy-output').addEventListener('click', async () => {
  await navigator.clipboard.writeText(workflowOutput.textContent || '');
  statusLine.textContent = 'Copied workflow YAML.';
});

sourceInput.value = window.CF2GHA_SAMPLE;
scheduleTranslate();
