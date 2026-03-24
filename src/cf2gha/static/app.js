const sourceInput = document.getElementById('source-yaml');
const workflowNameInput = document.getElementById('workflow-name');
const workflowOutput = document.getElementById('workflow-output');
const warningsList = document.getElementById('warnings-list');
const checklistList = document.getElementById('checklist-list');
const stepList = document.getElementById('step-list');
const fileInput = document.getElementById('file-input');
const statusLine = document.getElementById('status-line');
const statusTitle = document.getElementById('status-title');
const statusBanner = document.getElementById('status-banner');
const statusPill = document.getElementById('status-pill');
const summaryStatus = document.getElementById('summary-status');
const summarySubstatus = document.getElementById('summary-substatus');
const summaryStepCount = document.getElementById('summary-step-count');
const summaryWarningCount = document.getElementById('summary-warning-count');
const summaryChecklistCount = document.getElementById('summary-checklist-count');
const warningsBadge = document.getElementById('warnings-badge');
const checklistBadge = document.getElementById('checklist-badge');

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
    setStatus('idle', 'Ready', 'Paste Codefresh YAML to start.');
    updateSummary({ stepCount: 0, warningCount: 0, checklistCount: 0, summaryText: 'Paste Codefresh YAML to start.' });
    return;
  }

  setStatus('working', 'Translating', 'Refreshing GitHub Actions output from the current source and step overrides…');

  let response;
  try {
    response = await fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    workflowOutput.textContent = '';
    stepList.innerHTML = '';
    warningsList.innerHTML = '';
    checklistList.innerHTML = '';
    setStatus('error', 'Request failed', 'Could not reach the local translation endpoint.');
    updateSummary({ stepCount: 0, warningCount: 0, checklistCount: 0, summaryText: 'Local translation request failed.' });
    return;
  }

  const data = await response.json();
  if (!response.ok) {
    workflowOutput.textContent = '';
    stepList.innerHTML = '';
    warningsList.innerHTML = '';
    checklistList.innerHTML = '';
    setStatus('error', 'Translation failed', data.error || 'Translation failed.');
    updateSummary({ stepCount: 0, warningCount: 0, checklistCount: 0, summaryText: 'Source YAML needs attention before translation can continue.' });
    return;
  }

  state.latest = data;
  workflowOutput.textContent = data.workflow_yaml;
  renderWarnings(data.warnings);
  renderChecklist(data.checklist);
  renderSteps(data.steps);

  const stepCount = Number(data.source_summary?.step_count || data.steps?.length || 0);
  const warningCount = data.warnings?.length || 0;
  const checklistCount = data.checklist?.length || 0;
  const summaryText = warningCount
    ? `Translated ${stepCount} step(s) with ${warningCount} pipeline warning${warningCount === 1 ? '' : 's'} to review.`
    : `Translated ${stepCount} step(s). No pipeline-level warnings right now.`;

  setStatus(warningCount ? 'warning' : 'success', warningCount ? 'Review needed' : 'Translation ready', summaryText);
  updateSummary({ stepCount, warningCount, checklistCount, summaryText });
}

function setStatus(kind, title, message) {
  statusBanner.dataset.state = kind;
  statusTitle.textContent = title;
  statusLine.textContent = message;

  const pillText = {
    idle: 'Idle',
    working: 'Working',
    success: 'Ready',
    warning: 'Review',
    error: 'Error',
  };

  statusPill.textContent = pillText[kind] || 'Status';
  summaryStatus.textContent = title;
  summarySubstatus.textContent = message;
}

function updateSummary({ stepCount, warningCount, checklistCount, summaryText }) {
  summaryStepCount.textContent = String(stepCount);
  summaryWarningCount.textContent = String(warningCount);
  summaryChecklistCount.textContent = String(checklistCount);
  warningsBadge.textContent = String(warningCount);
  checklistBadge.textContent = String(checklistCount);
  summarySubstatus.textContent = summaryText;
}

function renderWarnings(warnings) {
  warningsList.innerHTML = '';
  if (!warnings.length) {
    warningsList.appendChild(renderSignalItem('clean', 'No pipeline-level warnings.', 'The conversion is still conservative, but there are no top-level warning records right now.'));
    return;
  }

  for (const warning of warnings) {
    const title = warning.step ? `[${warning.code}] ${warning.step}` : `[${warning.code}]`;
    warningsList.appendChild(renderSignalItem('warning', title, warning.suggestion ? `${warning.message} ${warning.suggestion}` : warning.message));
  }
}

function renderChecklist(items) {
  checklistList.innerHTML = '';
  if (!items.length) {
    checklistList.appendChild(renderSignalItem('neutral', 'No checklist items.', 'Nothing extra was surfaced at the pipeline level.'));
    return;
  }

  for (const item of items) {
    checklistList.appendChild(renderSignalItem('neutral', 'Follow-up', item));
  }
}

function renderSignalItem(kind, title, body) {
  const li = document.createElement('li');
  li.className = `signal-item signal-${kind}`;
  li.innerHTML = `
    <div class="signal-title">${escapeHtml(title)}</div>
    <div class="signal-body">${escapeHtml(body)}</div>
  `;
  return li;
}

function renderSteps(steps) {
  stepList.innerHTML = '';

  for (const [index, step] of steps.entries()) {
    const card = document.createElement('article');
    card.className = 'step-card';

    const warningCount = step.warnings?.length || 0;
    const detectedTools = (step.detected_tools || []).map(tool => `<span class="badge">${escapeHtml(tool)}</span>`).join('');
    const stageChip = step.stage ? `<span class="meta-chip">stage: ${escapeHtml(step.stage)}</span>` : '';
    const imageChip = step.source_image ? `<span class="meta-chip subtle">image: ${escapeHtml(step.source_image)}</span>` : '';
    const warningChip = warningCount ? `<span class="meta-chip warning">${warningCount} warning${warningCount === 1 ? '' : 's'}</span>` : '<span class="meta-chip success">clean</span>';

    card.innerHTML = `
      <header class="step-card-header">
        <div class="step-title-block">
          <div class="step-order">Step ${index + 1}</div>
          <div>
            <h3>${escapeHtml(step.source_name)}</h3>
            <div class="step-meta-row">
              <span class="meta-chip type">${escapeHtml(step.step_type)}</span>
              ${stageChip}
              ${imageChip}
              ${warningChip}
            </div>
          </div>
        </div>
        <div class="step-badges">${detectedTools}</div>
      </header>

      <div class="step-editor-grid">
        <label class="field-group">
          <span class="field-label">Generated step name</span>
          <input data-step="${escapeAttr(step.source_name)}" data-field="name" value="${escapeAttr(step.gha_step.name || '')}">
        </label>
        <label class="field-group">
          <span class="field-label">uses</span>
          <input data-step="${escapeAttr(step.source_name)}" data-field="uses" value="${escapeAttr(step.gha_step.uses || '')}" placeholder="actions/checkout@v4">
        </label>
        <label class="field-group field-full">
          <span class="field-label">run</span>
          <textarea data-step="${escapeAttr(step.source_name)}" data-field="run" placeholder="Shell commands for the translated step">${escapeHtml(step.gha_step.run || '')}</textarea>
        </label>
      </div>

      <div class="step-detail-grid"></div>
    `;

    const detailGrid = card.querySelector('.step-detail-grid');
    detailGrid.appendChild(renderDetailSection('Rationale', step.rationale, 'Why the translator made this choice.'));
    detailGrid.appendChild(renderDetailSection('Step checklist', step.checklist, 'Manual follow-up specific to this step.'));

    if (step.translation_hints?.length) {
      detailGrid.appendChild(renderDetailSection('Translation hints', step.translation_hints, 'Useful nudges surfaced during translation.'));
    }

    if (step.special_handling?.length) {
      detailGrid.appendChild(renderDetailSection('Special handling', step.special_handling, 'Image or tool-specific caveats that deserve review.'));
    }

    if (step.warnings?.length) {
      detailGrid.appendChild(
        renderDetailSection(
          'Step warnings',
          step.warnings.map(w => w.suggestion ? `[${w.code}] ${w.message} — ${w.suggestion}` : `[${w.code}] ${w.message}`),
          'Warnings attached directly to this translated step.',
          'warning'
        )
      );
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

function renderDetailSection(title, items, description, tone = 'neutral') {
  const wrapper = document.createElement('section');
  wrapper.className = `detail-card tone-${tone}`;

  const heading = document.createElement('div');
  heading.className = 'detail-card-header';
  heading.innerHTML = `
    <div>
      <h4>${escapeHtml(title)}</h4>
      <p>${escapeHtml(description)}</p>
    </div>
    <span class="count-badge ${tone === 'warning' ? '' : 'neutral'}">${(items || []).length}</span>
  `;
  wrapper.appendChild(heading);

  const list = document.createElement('ul');
  list.className = 'plain-list';

  if (!(items || []).length) {
    const empty = document.createElement('li');
    empty.className = 'empty-list-item';
    empty.textContent = 'Nothing surfaced here.';
    list.appendChild(empty);
  } else {
    for (const item of items || []) {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    }
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
  setStatus('success', 'Copied output', 'GitHub Actions YAML copied to the clipboard.');
});

sourceInput.value = window.CF2GHA_SAMPLE;
scheduleTranslate();
