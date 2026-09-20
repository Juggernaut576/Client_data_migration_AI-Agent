// Enterprise AI Data Migration Suite - Web Client
let activeEscalationId = null;
let currentSummary = null;

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initActionButtons();
  initModal();
  fetchStatus();
});

// 1. TABS LOGIC
function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      tab.classList.add('active');
      const targetPane = document.getElementById(tab.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });
}

// 2. ACTION BUTTONS
function initActionButtons() {
  const btnRun = document.getElementById('btn-run-sample');
  const btnReset = document.getElementById('btn-reset');
  const btnPush = document.getElementById('btn-push-target');

  btnRun.addEventListener('click', async () => {
    btnRun.disabled = true;
    btnRun.innerHTML = `<span class="spinner"></span> Processing Multi-File Pipeline...`;
    try {
      const res = await fetch('/api/pipeline/run-sample', { method: 'POST' });
      const data = await res.json();
      currentSummary = data;
      renderDashboard(data);
    } catch (err) {
      alert('Error running sample pipeline: ' + err.message);
    } finally {
      btnRun.disabled = false;
      btnRun.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Run Ingestion Pipeline (3 Files)`;
    }
  });

  const btnUpload = document.getElementById('btn-upload-trigger');
  const fileInput = document.getElementById('file-input-custom');
  if (btnUpload && fileInput) {
    btnUpload.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
      if (!fileInput.files || fileInput.files.length === 0) return;
      btnUpload.disabled = true;
      btnUpload.innerHTML = `Uploading ${fileInput.files.length} files...`;
      
      const formData = new FormData();
      for (const f of fileInput.files) {
        formData.append('files', f);
      }
      try {
        const res = await fetch('/api/pipeline/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        currentSummary = data;
        renderDashboard(data);
        alert(`Successfully ingested ${fileInput.files.length} custom client files!`);
      } catch (err) {
        alert('Error uploading custom files: ' + err.message);
      } finally {
        btnUpload.disabled = false;
        btnUpload.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg> Upload Client Files`;
        fileInput.value = '';
      }
    });
  }

  btnReset.addEventListener('click', async () => {
    if (confirm('Reset state and target database to fresh initial seed?')) {
      await fetch('/api/target/reset', { method: 'POST' });
      await fetchStatus();
    }
  });

  btnPush.addEventListener('click', async () => {
    btnPush.disabled = true;
    btnPush.textContent = 'Pushing to Target API...';
    try {
      const res = await fetch('/api/target/push', { method: 'POST' });
      const result = await res.json();
      renderPushResult(result);
      await fetchStatus();
    } catch (err) {
      alert('Error during target push: ' + err.message);
    } finally {
      btnPush.disabled = false;
      btnPush.textContent = 'Push to Target Platform';
    }
  });
}

// 3. FETCH CURRENT STATUS
async function fetchStatus() {
  try {
    const res = await fetch('/api/pipeline/status');
    const data = await res.json();
    currentSummary = data;
    renderDashboard(data);
  } catch (err) {
    console.error('Error fetching pipeline status:', err);
  }
}

// Safe DOM helper
function setElText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// 4. RENDER DASHBOARD
function renderDashboard(data) {
  if (!data) return;

  // KPI updates
  setElText('kpi-raw', data.raw_records_count || 0);
  setElText('kpi-sources', `${(data.sources || []).length} source files loaded`);
  setElText('kpi-cleaned', data.cleaned_count || 0);
  setElText('kpi-escalations', data.pending_escalations_count || 0);
  setElText('kpi-valid', data.valid_count || 0);
  setElText('kpi-target-db', (data.target_database_preview || []).length);

  // Badges
  setElText('badge-escalation-count', data.pending_escalations_count || 0);
  setElText('badge-delta-count', (data.deltas || []).length);
  setElText('badge-ready-count', data.valid_count || 0);
  setElText('count-all-esc', data.pending_escalations_count || 0);

  // Render sub-views
  renderEscalations(data.pending_escalations || []);
  renderDeltas(data.deltas || [], data.delta_summary || {});
  renderMappings(data.column_mappings || {});
  renderDataset(data.valid_records_preview || []);
  renderAuditTrail(data.audit_trail || []);
  renderTargetDatabase(data.target_database_preview || []);

  if (data.push_result) {
    renderPushResult(data.push_result);
  }
}

// 5. RENDER ESCALATIONS
function renderEscalations(escalations) {
  const container = document.getElementById('escalation-container');
  if (!escalations || escalations.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">✓</div>
        <h3>No Pending Escalations</h3>
        <p>All records conform safely to schema or have been resolved by consultant.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = escalations.map(esc => {
    let tagClass = 'tag-ambiguity';
    if (esc.category === 'DATA_CONFLICT') tagClass = 'tag-conflict';
    if (esc.category === 'VALIDATION_FAILURE') tagClass = 'tag-validation';

    return `
      <div class="escalation-card" id="card-${esc.id}">
        <div>
          <div class="esc-header">
            <span class="esc-tag ${tagClass}">${esc.category.replace('_', ' ')}</span>
            <span class="esc-meta">Confidence: ${(esc.confidence_score * 100).toFixed(0)}%</span>
          </div>
          <h3 class="esc-title">${esc.title}</h3>
          <p class="esc-meta">${esc.source_file ? `Source: ${esc.source_file}` : ''} ${esc.entity_id ? `&bull; Entity: ${esc.entity_id}` : ''}</p>
          
          <div class="esc-context-box">
            <div class="esc-context-row">
              <span class="text-muted">Target Field:</span>
              <strong>${esc.field || 'N/A'}</strong>
            </div>
            <div class="esc-context-row">
              <span class="text-muted">Current Value:</span>
              <code style="color: #fca5a5;">${esc.current_value !== null ? esc.current_value : 'NULL'}</code>
            </div>
            <div class="esc-context-row">
              <span class="text-muted">Suggested Action:</span>
              <span style="color: #6ee7b7;">${esc.suggested_action}</span>
            </div>
          </div>

          <div class="esc-reasoning">
            <strong>Agent Reasoning:</strong> ${esc.agent_reasoning}
          </div>
        </div>

        <div class="esc-actions">
          <button class="btn btn-success btn-sm" onclick="resolveEscalation('${esc.id}', 'APPROVED_SUGGESTION', '${esc.suggested_value || ''}')">
            Approve Suggestion
          </button>
          <button class="btn btn-outline btn-sm" onclick="openManualEdit('${esc.id}', '${esc.field}', '${esc.suggested_value || esc.current_value || ''}')">
            Manual Edit
          </button>
          <button class="btn btn-outline btn-sm" style="color: #fca5a5;" onclick="resolveEscalation('${esc.id}', 'REJECTED')">
            Reject Record
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// 6. RESOLVE ESCALATION HANDLER
window.resolveEscalation = async function(id, resolutionType, resolvedVal) {
  try {
    const payload = {
      escalation_id: id,
      resolution_type: resolutionType,
      resolved_value: resolvedVal || null
    };
    const res = await fetch('/api/escalation/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (result.status === 'success') {
      currentSummary = result.summary;
      renderDashboard(result.summary);
    }
  } catch (err) {
    alert('Error resolving escalation: ' + err.message);
  }
};

// 7. MODAL LOGIC FOR MANUAL EDIT
function initModal() {
  const modal = document.getElementById('modal-edit');
  const btnClose = document.getElementById('modal-close');
  const btnCancel = document.getElementById('modal-btn-cancel');
  const btnSubmit = document.getElementById('modal-btn-submit');

  const hide = () => modal.classList.add('hidden');
  btnClose.addEventListener('click', hide);
  btnCancel.addEventListener('click', hide);

  btnSubmit.addEventListener('click', async () => {
    const val = document.getElementById('modal-input-val').value;
    hide();
    if (activeEscalationId) {
      await resolveEscalation(activeEscalationId, 'MANUAL_OVERRIDE', val);
    }
  });
}

window.openManualEdit = function(id, fieldName, defaultValue) {
  activeEscalationId = id;
  document.getElementById('modal-title').textContent = `Manual Override for '${fieldName}'`;
  document.getElementById('modal-desc').textContent = `Input the verified value for escalation item ${id}:`;
  document.getElementById('modal-field-label').textContent = `Value for ${fieldName}:`;
  document.getElementById('modal-input-val').value = defaultValue;
  document.getElementById('modal-edit').classList.remove('hidden');
};

// 8. RENDER DELTAS
function renderDeltas(deltas, summary) {
  setElText('tally-new', summary.new || 0);
  setElText('tally-update', summary.update || 0);
  setElText('tally-noop', summary.no_change || 0);
  setElText('tally-conflict', summary.conflict || 0);

  const tbody = document.getElementById('delta-table-body');
  if (!deltas || deltas.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No delta analysis available yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = deltas.map(d => {
    let badgePill = '<span class="pill pill-green">NEW</span>';
    if (d.delta_type === 'UPDATE') badgePill = '<span class="pill pill-blue">UPDATE</span>';
    if (d.delta_type === 'NO_CHANGE') badgePill = '<span class="pill pill-gray">NO CHANGE</span>';
    if (d.delta_type === 'CONFLICT') badgePill = '<span class="pill pill-red">CONFLICT</span>';

    const diffEntries = Object.entries(d.field_diffs || {}).map(([f, diff]) => {
      return `<div><strong>${f}:</strong> <span class="diff-badge diff-before">${diff.before}</span> &rarr; <span class="diff-badge diff-after">${diff.after}</span></div>`;
    }).join('') || '<span class="text-muted">None</span>';

    const inc = d.incoming_data || {};
    return `
      <tr>
        <td><code>${d.entity_id}</code></td>
        <td>${badgePill}</td>
        <td>${inc.first_name || ''} ${inc.last_name || ''}</td>
        <td>${inc.department || '-'}</td>
        <td>${diffEntries}</td>
      </tr>
    `;
  }).join('');
}

// 9. RENDER MAPPINGS
function renderMappings(mappingsByFile) {
  const container = document.getElementById('mappings-container');
  if (!mappingsByFile || Object.keys(mappingsByFile).length === 0) {
    container.innerHTML = `<p class="text-muted">No mappings generated yet.</p>`;
    return;
  }

  container.innerHTML = Object.entries(mappingsByFile).map(([filename, maps]) => {
    const rows = Object.entries(maps).map(([col, m]) => {
      return `
        <tr>
          <td><code>${col}</code></td>
          <td>&rarr;</td>
          <td><strong style="color: #6ee7b7;">${m.target_field || 'UNMAPPED'}</strong></td>
          <td><span class="pill ${m.confidence >= 0.8 ? 'pill-green' : 'pill-blue'}">${(m.confidence * 100).toFixed(0)}%</span></td>
          <td class="text-muted" style="font-size: 0.8rem;">${m.reasoning}</td>
        </tr>
      `;
    }).join('');

    return `
      <div class="table-card" style="margin-bottom: 24px;">
        <div style="padding: 14px 18px; font-weight: 700; border-bottom: 1px solid var(--border-color); background: rgba(0,0,0,0.15);">
          Source File: ${filename}
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Source Header</th>
              <th></th>
              <th>Target Schema Field</th>
              <th>Confidence</th>
              <th>Agent Mapping Rationale</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }).join('');
}

// 10. RENDER READY DATASET
function renderDataset(records) {
  const tbody = document.getElementById('dataset-table-body');
  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No records loaded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => `
    <tr>
      <td><code>${r.employee_id || '-'}</code></td>
      <td><strong>${r.first_name || ''} ${r.last_name || ''}</strong></td>
      <td>${r.email || '-'}</td>
      <td>${r.department || '-'}</td>
      <td>${r.job_title || '-'}</td>
      <td><code>${r.hire_date || '-'}</code></td>
      <td>${r.salary ? `$${Number(r.salary).toLocaleString()}` : '-'}</td>
      <td><span class="pill pill-green">${r.status || 'ACTIVE'}</span></td>
      <td>${r.phone_number || '-'}</td>
    </tr>
  `).join('');
}

// 11. RENDER AUDIT TRAIL
function renderAuditTrail(entries) {
  const container = document.getElementById('audit-container');
  if (!entries || entries.length === 0) {
    container.innerHTML = `<p class="text-muted">No audit trail entries recorded yet.</p>`;
    return;
  }

  container.innerHTML = [...entries].reverse().map(e => `
    <div class="audit-item">
      <div>
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
          <span class="audit-actor ${e.actor === 'AGENT' ? 'actor-agent' : 'actor-human'}">${e.actor}</span>
          <strong>${e.action}</strong>
          ${e.entity_id ? `&bull; <code>${e.entity_id}</code>` : ''}
          ${e.field ? `&bull; Field: <strong>${e.field}</strong>` : ''}
        </div>
        <p class="text-muted" style="margin: 0;">${e.reason}</p>
      </div>
      <div style="text-align: right; font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
        ${e.timestamp.split('T')[1]?.slice(0, 8) || ''}
      </div>
    </div>
  `).join('');
}

// 12. RENDER TARGET DB & PUSH
function renderTargetDatabase(dbRecords) {
  setElText('target-db-count', dbRecords.length);
  const tbody = document.getElementById('target-db-table-body');
  if (!dbRecords || dbRecords.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Target database is empty.</td></tr>`;
    return;
  }

  tbody.innerHTML = dbRecords.map(r => `
    <tr>
      <td><code>${r.employee_id}</code></td>
      <td>${r.first_name} ${r.last_name}</td>
      <td>${r.email}</td>
      <td>${r.department}</td>
      <td>${r.job_title}</td>
      <td><code>${r.hire_date}</code></td>
      <td>${r.salary ? `$${Number(r.salary).toLocaleString()}` : '-'}</td>
      <td><span class="pill pill-green">${r.status}</span></td>
    </tr>
  `).join('');
}

function renderPushResult(result) {
  const box = document.getElementById('push-result-box');
  box.classList.remove('hidden');
  box.innerHTML = `
    <div>
      <h3 style="color: #6ee7b7; margin-bottom: 4px;">Push Transaction Committed: ${result.transaction_id}</h3>
      <p style="margin: 0;" class="text-muted">
        Total Records: <strong>${result.total_records}</strong> &bull;
        Success: <strong style="color: #6ee7b7;">${result.success_count}</strong> &bull;
        Failed: <strong style="color: #fca5a5;">${result.failed_count}</strong>
      </p>
    </div>
    <div>
      <button class="btn btn-outline" style="border-color: #fca5a5; color: #fca5a5;" onclick="rollbackTransaction('${result.transaction_id}')">
        Rollback Transaction
      </button>
    </div>
  `;
}

window.rollbackTransaction = async function(txId) {
  if (confirm(`Are you sure you want to rollback transaction ${txId}? Destination database will revert to previous state.`)) {
    try {
      const res = await fetch('/api/target/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction_id: txId })
      });
      const data = await res.json();
      alert(`Rollback successful. Reverted ${data.reverted_records_count} records.`);
      await fetchStatus();
    } catch (err) {
      alert('Error during rollback: ' + err.message);
    }
  }
};
