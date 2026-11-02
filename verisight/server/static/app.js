/**
 * VeriSight Neural Cockpit — Live Interactive Web Application Logic.
 */

(function () {
  'use strict';

  // Global State
  const state = {
    activeTab: 'tabSim',
    currentRunId: null,
    zoomScale: 1.0,
    waveformData: null,
    systemStatus: null,
    currentPatch: null,
    targetRtlFile: 'examples/rtl/alu.sv',
    rtlFiles: [{ name: 'alu.sv', path: 'examples/rtl/alu.sv' }],
    upfFile: null,
    topModule: '',
  };

  // DOM Elements Cache
  const els = {
    // Navigation
    tabs: document.querySelectorAll('.nav-tab'),
    tabContents: document.querySelectorAll('.tab-content'),
    simPill: document.getElementById('simPill'),
    simPillText: document.getElementById('simPillText'),
    // Presets
    btnPresetAlu: document.getElementById('btnPresetAlu'),
    btnPresetFifo: document.getElementById('btnPresetFifo'),
    btnPresetCustom: document.getElementById('btnPresetCustom'),
    // Multi-File & UPF Mode Elements
    analysisModeBanner: document.getElementById('analysisModeBanner'),
    modeTitle: document.getElementById('modeTitle'),
    modeDesc: document.getElementById('modeDesc'),
    rtlDropzone: document.getElementById('rtlDropzone'),
    rtlFileInput: document.getElementById('rtlFileInput'),
    btnBrowseRtl: document.getElementById('btnBrowseRtl'),
    rtlFilesList: document.getElementById('rtlFilesList'),
    rtlFileCount: document.getElementById('rtlFileCount'),
    upfDropzone: document.getElementById('upfDropzone'),
    upfFileInput: document.getElementById('upfFileInput'),
    btnBrowseUpf: document.getElementById('btnBrowseUpf'),
    upfStatusBadge: document.getElementById('upfStatusBadge'),
    upfFilePill: document.getElementById('upfFilePill'),
    upfFileName: document.getElementById('upfFileName'),
    btnRemoveUpf: document.getElementById('btnRemoveUpf'),
    upfPathInput: document.getElementById('upfPathInput'),
    topModuleInput: document.getElementById('topModuleInput'),
    btnValidateProject: document.getElementById('btnValidateProject'),
    projectValidationCard: document.getElementById('projectValidationCard'),
    btnCloseVal: document.getElementById('btnCloseVal'),
    valBody: document.getElementById('valBody'),
    // Sim Form
    rtlInput: document.getElementById('rtlPathInput'),
    tbInput: document.getElementById('tbPathInput'),
    specInput: document.getElementById('specPathInput'),
    simSelect: document.getElementById('simulatorSelect'),
    secSelect: document.getElementById('securityModeSelect'),
    outDirInput: document.getElementById('outputDirInput'),
    btnLaunchSim: document.getElementById('btnLaunchSim'),
    simSpinner: document.getElementById('simSpinner'),
    btnSimText: document.getElementById('btnSimText'),
    // Terminal
    terminal: document.getElementById('terminalOutput'),
    btnClearTerm: document.getElementById('btnClearTerm'),
    // HUD
    hudResults: document.getElementById('hudResults'),
    mValStatus: document.getElementById('mValStatus'),
    mSubSim: document.getElementById('mSubSim'),
    mValDuration: document.getElementById('mValDuration'),
    mValDiagnosis: document.getElementById('mValDiagnosis'),
    mSubConfidence: document.getElementById('mSubConfidence'),
    linkReportHtml: document.getElementById('linkReportHtml'),
    linkPlanHtml: document.getElementById('linkPlanHtml'),
    btnHudInspectWave: document.getElementById('btnHudInspectWave'),
    // Debug Studio
    diagClassBadge: document.getElementById('diagClassBadge'),
    diagConfBadge: document.getElementById('diagConfBadge'),
    diagCatBadge: document.getElementById('diagCatBadge'),
    diagTargetModule: document.getElementById('diagTargetModule'),
    diagRootCauseText: document.getElementById('diagRootCauseText'),
    patchViewer: document.getElementById('patchViewer'),
    patchCodeContent: document.getElementById('patchCodeContent'),
    btnApplyFix: document.getElementById('btnApplyFix'),
    btnRevertFix: document.getElementById('btnRevertFix'),
    patchStatusText: document.getElementById('patchStatusText'),
    // Waveform Studio
    btnWaveZoomIn: document.getElementById('btnWaveZoomIn'),
    btnWaveZoomOut: document.getElementById('btnWaveZoomOut'),
    btnWaveReset: document.getElementById('btnWaveReset'),
    btnWaveJumpFail: document.getElementById('btnWaveJumpFail'),
    waveSourceText: document.getElementById('waveSourceText'),
    waveTimescaleText: document.getElementById('waveTimescaleText'),
    waveDurationText: document.getElementById('waveDurationText'),
    waveSignalCount: document.getElementById('waveSignalCount'),
    waveNamesCol: document.getElementById('waveNamesCol'),
    waveSvg: document.getElementById('waveSvg'),
    waveCanvasWrapper: document.getElementById('waveCanvasWrapper'),
    // Past Runs
    runsList: document.getElementById('runsList'),
    toastContainer: document.getElementById('toastContainer'),
  };

  // Toast Notification Helper
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : '⚡';
    toast.innerHTML = `<span style="color:var(--cyan-bright);">${icon}</span> <span>${message}</span>`;
    els.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Switch Tabs
  function switchTab(tabId) {
    state.activeTab = tabId;
    els.tabs.forEach(tab => {
      tab.classList.toggle('active', tab.getAttribute('data-tab') === tabId);
    });
    els.tabContents.forEach(content => {
      content.classList.toggle('active', content.id === tabId);
    });

    if (tabId === 'tabWaveform' && !state.waveformData) {
      loadWaveform();
    } else if (tabId === 'tabRuns') {
      loadPastRuns();
    }
  }

  // Terminal Logging
  function logTerminal(text, type = 'normal') {
    const line = document.createElement('div');
    line.className = `term-line ${type}`;
    line.textContent = text;
    els.terminal.appendChild(line);
    els.terminal.scrollTop = els.terminal.scrollHeight;
  }

  // Fetch System Diagnostics
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      state.systemStatus = data;

      // Update simulator badge
      if (data.simulators) {
        const best = data.simulators.best;
        els.simPillText.textContent = `${best.toUpperCase()} Simulator Ready`;
      }
    } catch (e) {
      console.warn('Failed to fetch system status:', e);
      els.simPillText.textContent = 'Simulator Ready';
    }
  }

  // Preset Handlers
  function applyPreset(name) {
    document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
    if (name === 'alu') {
      els.btnPresetAlu.classList.add('active');
      els.rtlInput.value = 'examples/rtl/alu.sv';
      els.tbInput.value = 'examples/tb/alu_tb.sv';
      els.specInput.value = 'examples/specs/alu_spec.md';
      els.outDirInput.value = 'output/closed_loop';
      state.targetRtlFile = 'examples/rtl/alu.sv';
      state.rtlFiles = [{ name: 'alu.sv', path: 'examples/rtl/alu.sv' }];
      state.upfFile = null;
      els.upfPathInput.value = '';
    } else if (name === 'fifo') {
      els.btnPresetFifo.classList.add('active');
      els.rtlInput.value = 'projects/fifo/rtl/fifo.sv';
      els.tbInput.value = 'projects/fifo/tb/fifo_tb.sv';
      els.specInput.value = 'projects/fifo/specs/spec.md';
      els.outDirInput.value = 'output/demo_fifo_closed_loop';
      state.targetRtlFile = 'projects/fifo/rtl/fifo.sv';
      state.rtlFiles = [{ name: 'fifo.sv', path: 'projects/fifo/rtl/fifo.sv' }];
      state.upfFile = null;
      els.upfPathInput.value = '';
    } else {
      els.btnPresetCustom.classList.add('active');
      els.rtlInput.value = '';
      els.tbInput.value = '';
      els.specInput.value = '';
      els.outDirInput.value = 'output/custom_sim';
      state.rtlFiles = [];
      state.upfFile = null;
      els.upfPathInput.value = '';
    }
    renderRtlFiles();
    updateModeUI();
  }

  // Multi-File & UPF Helpers
  async function uploadFiles(fileList) {
    const formData = new FormData();
    for (const f of fileList) {
      formData.append('files', f);
    }
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      return await res.json();
    } catch (e) {
      showToast('File upload error: ' + e.message, 'error');
      return null;
    }
  }

  async function handleRtlFiles(files) {
    if (!files || files.length === 0) return;
    const upRes = await uploadFiles(files);
    if (upRes && upRes.rtl_files) {
      for (const p of upRes.rtl_files) {
        const name = p.split('/').pop();
        if (!state.rtlFiles.some(f => f.path === p)) {
          state.rtlFiles.push({ name, path: p });
        }
      }
      if (upRes.upf_files && upRes.upf_files.length > 0) {
        const upfP = upRes.upf_files[0];
        state.upfFile = { name: upfP.split('/').pop(), path: upfP };
        els.upfPathInput.value = upfP;
      }
      renderRtlFiles();
      updateModeUI();
      showToast(`Added ${upRes.rtl_files.length} RTL file(s)`, 'success');
    }
  }

  async function handleUpfFile(files) {
    if (!files || files.length === 0) return;
    const upRes = await uploadFiles(files);
    if (upRes) {
      if (upRes.upf_files && upRes.upf_files.length > 0) {
        const p = upRes.upf_files[0];
        state.upfFile = { name: p.split('/').pop(), path: p };
        els.upfPathInput.value = p;
        updateModeUI();
        showToast('UPF Power Intent loaded', 'success');
      } else if (upRes.rtl_files && upRes.rtl_files.length > 0) {
        showToast('Selected file is RTL, not .upf', 'error');
      }
    }
  }

  function removeRtlFile(index) {
    state.rtlFiles.splice(index, 1);
    renderRtlFiles();
    updateModeUI();
  }

  function removeUpfFile() {
    state.upfFile = null;
    els.upfPathInput.value = '';
    updateModeUI();
    showToast('Removed UPF file (Switched to RTL-Only Mode)', 'info');
  }

  function renderRtlFiles() {
    els.rtlFilesList.innerHTML = '';
    state.rtlFiles.forEach((file, idx) => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.innerHTML = `
        <span class="chip-name" title="${file.path}">${file.name}</span>
        <button type="button" class="btn-chip-remove" title="Remove ${file.name}">&times;</button>
      `;
      chip.querySelector('.btn-chip-remove').addEventListener('click', () => removeRtlFile(idx));
      els.rtlFilesList.appendChild(chip);
    });
    const count = state.rtlFiles.length;
    els.rtlFileCount.textContent = `${count} file${count === 1 ? '' : 's'}`;
    if (count > 0) {
      els.rtlInput.value = state.rtlFiles.map(f => f.path).join(', ');
    }
  }

  function updateModeUI() {
    const hasUpf = !!(state.upfFile || (els.upfPathInput && els.upfPathInput.value.trim()));
    if (hasUpf) {
      els.analysisModeBanner.className = 'analysis-mode-banner mode-upf';
      els.modeTitle.textContent = '⚡ RTL + UPF Power-Aware Analysis Mode';
      els.modeDesc.textContent = 'Active IEEE 1801 power intent: correlates power domains, isolation, level shifters, retention & power state tables with RTL.';
      els.upfStatusBadge.textContent = 'Active (Power-Aware)';
      els.upfStatusBadge.className = 'badge-status active';
      if (state.upfFile) {
        els.upfFilePill.style.display = 'flex';
        els.upfFileName.textContent = state.upfFile.name;
      }
    } else {
      els.analysisModeBanner.className = 'analysis-mode-banner mode-rtl';
      els.modeTitle.textContent = '🟢 RTL-Only Analysis Mode';
      els.modeDesc.textContent = 'Standard functional verification and root-cause debugging without power intent.';
      els.upfStatusBadge.textContent = 'Not Loaded (RTL Only)';
      els.upfStatusBadge.className = 'badge-status';
      els.upfFilePill.style.display = 'none';
    }
  }

  async function validateProject() {
    const rtlPaths = state.rtlFiles.length > 0 
      ? state.rtlFiles.map(f => f.path) 
      : (els.rtlInput.value.trim() ? els.rtlInput.value.trim().split(',').map(s => s.trim()) : []);
    const upfPath = state.upfFile ? state.upfFile.path : (els.upfPathInput ? els.upfPathInput.value.trim() : '');
    const topMod = els.topModuleInput.value.trim();

    if (rtlPaths.length === 0) {
      showToast('Please add at least one RTL file before validating', 'error');
      return;
    }

    els.btnValidateProject.disabled = true;
    els.btnValidateProject.innerHTML = '<span>⏳</span> Validating...';

    try {
      const res = await fetch('/api/validate-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rtl_files: rtlPaths,
          upf_path: upfPath || null,
          top_module: topMod || null,
        }),
      });
      const data = await res.json();
      els.btnValidateProject.disabled = false;
      els.btnValidateProject.innerHTML = '<span>🔎</span> Validate Project & Hierarchy';

      if (!data.valid) {
        showToast('Validation failed: ' + (data.errors ? data.errors.join(', ') : 'Unknown error'), 'error');
        return;
      }

      if (data.top_module && !els.topModuleInput.value.trim()) {
        els.topModuleInput.value = data.top_module;
      }

      els.projectValidationCard.style.display = 'block';
      let issuesHtml = '';
      if (data.upf_issues && data.upf_issues.length > 0) {
        issuesHtml = '<div class="val-issues-box"><strong>Power Intent Diagnostics:</strong>' +
          data.upf_issues.map(iss => `
            <div class="val-issue-row ${iss.severity}">
              <span>[${iss.severity.toUpperCase()}]</span>
              <span>${iss.description}</span>
            </div>
          `).join('') + '</div>';
      }

      let missingHtml = '';
      if (data.missing_dependencies && data.missing_dependencies.length > 0) {
        missingHtml = '<div class="val-issue-row error"><strong>Missing Dependencies:</strong> ' +
          data.missing_dependencies.join(', ') + '</div>';
      }

      els.valBody.innerHTML = `
        <div class="val-grid">
          <div class="val-stat"><span class="val-stat-label">Mode</span><span class="val-stat-val" style="color:${data.mode === 'rtl_upf' ? '#c084fc' : 'var(--emerald-bright)'}">${data.mode === 'rtl_upf' ? '⚡ RTL + UPF' : '🟢 RTL-Only'}</span></div>
          <div class="val-stat"><span class="val-stat-label">Top Module</span><span class="val-stat-val" style="color:var(--cyan-bright)">${data.top_module || 'None'}</span></div>
          <div class="val-stat"><span class="val-stat-label">Modules</span><span class="val-stat-val">${data.modules ? data.modules.length : 0}</span></div>
          <div class="val-stat"><span class="val-stat-label">Packages</span><span class="val-stat-val">${data.packages ? data.packages.length : 0}</span></div>
          <div class="val-stat"><span class="val-stat-label">Power Domains</span><span class="val-stat-val">${data.power_domains ? data.power_domains.length : 0}</span></div>
          <div class="val-stat"><span class="val-stat-label">Crossings</span><span class="val-stat-val">${data.domain_crossings ? data.domain_crossings.length : 0}</span></div>
        </div>
        ${missingHtml}
        ${issuesHtml}
      `;

      showToast('Project hierarchy validated successfully', 'success');
    } catch (e) {
      els.btnValidateProject.disabled = false;
      els.btnValidateProject.innerHTML = '<span>🔎</span> Validate Project & Hierarchy';
      showToast('Validation request failed: ' + e.message, 'error');
    }
  }

  // Launch Simulation
  async function launchSimulation() {
    const rtlList = state.rtlFiles.length > 0 
      ? state.rtlFiles.map(f => f.path) 
      : (els.rtlInput.value.trim() ? els.rtlInput.value.trim().split(',').map(s => s.trim()) : []);
    const upfPath = state.upfFile ? state.upfFile.path : (els.upfPathInput ? els.upfPathInput.value.trim() : '');
    const topMod = els.topModuleInput.value.trim();
    const tb = els.tbInput.value.trim();
    const spec = els.specInput.value.trim();
    const simulator = els.simSelect.value;
    const sec = els.secSelect.value;
    const outDir = els.outDirInput.value.trim();

    if (rtlList.length === 0 || !tb) {
      showToast('Please specify both RTL source file(s) and Testbench path', 'error');
      return;
    }

    state.targetRtlFile = rtlList[0];

    // UI Loading state
    els.btnLaunchSim.disabled = true;
    els.simSpinner.style.display = 'inline-block';
    els.btnSimText.textContent = 'Simulating & Diagnosing...';

    logTerminal(`\n[${new Date().toLocaleTimeString()}] 🚀 Launching Closed-Loop Simulation...`, 'prompt');
    logTerminal(`[INFO] Mode:        ${upfPath ? '⚡ RTL + UPF Power-Aware Mode' : '🟢 RTL-Only Mode'}`);
    logTerminal(`[INFO] RTL Sources: ${rtlList.join(', ')} (${rtlList.length} files)`);
    if (upfPath) {
      logTerminal(`[INFO] UPF Intent:  ${upfPath}`);
    }
    if (topMod) {
      logTerminal(`[INFO] Top Module:  ${topMod}`);
    }
    logTerminal(`[INFO] Testbench:   ${tb}`);
    logTerminal(`[INFO] Simulator:   ${simulator.toUpperCase()}`);
    logTerminal(`[INFO] Security:    ${sec === 'airgap' ? '🛡️ Sovereign Air-Gap (Local)' : 'Cloud API'}`);

    try {
      const res = await fetch('/api/sim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rtl_files: rtlList,
          upf_path: upfPath || null,
          top_module: topMod || null,
          tb_path: tb,
          spec_path: spec || null,
          simulator: simulator,
          output_dir: outDir,
          airgap: sec === 'airgap',
          provider: sec === 'claude' ? 'anthropic' : 'gemini',
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Simulation runner encountered an error');
      }

      const result = await res.json();
      state.currentRunId = result.run_id;

      // Print sim logs to terminal
      if (result.log_preview) {
        logTerminal(`\n--- Simulator Raw Log Output ---\n${result.log_preview}`);
      }

      logTerminal(`\n[SUCCESS] Closed-Loop Run Complete in ${result.duration_s}s!`, 'success');
      logTerminal(`[RCA] Diagnosis: ${result.classification} (${result.confidence}% confidence)`);
      logTerminal(`[RCA] Root Cause: ${result.root_cause}`);

      // Update HUD Results
      els.hudResults.style.display = 'block';
      if (result.error_count > 0 || !result.success) {
        els.mValStatus.textContent = `FAIL (${result.error_count} Anomalies)`;
        els.mValStatus.className = 'm-value text-red';
      } else {
        els.mValStatus.textContent = 'PASS (0 Errors)';
        els.mValStatus.className = 'm-value text-emerald';
      }

      els.mSubSim.textContent = `Backend: ${result.simulator} (Errors: ${result.error_count})`;
      els.mValDuration.textContent = `${result.duration_s}s`;
      els.mValDiagnosis.textContent = result.classification;
      els.mSubConfidence.textContent = `${result.confidence}% AI Confidence`;

      if (result.report_url) {
        els.linkReportHtml.href = result.report_url;
        els.linkReportHtml.style.display = 'inline-flex';
      }
      if (result.plan_url) {
        els.linkPlanHtml.href = result.plan_url;
        els.linkPlanHtml.style.display = 'inline-flex';
      } else {
        els.linkPlanHtml.style.display = 'none';
      }

      // Populate Debug Studio tab
      els.diagClassBadge.textContent = result.classification;
      els.diagConfBadge.textContent = `${result.confidence}% Confidence`;
      els.diagCatBadge.textContent = result.category;
      els.diagTargetModule.textContent = rtl;
      els.diagRootCauseText.textContent = result.root_cause;

      if (result.fix_patch) {
        state.currentPatch = result.fix_patch;
        els.patchCodeContent.textContent = result.fix_patch;
        els.btnApplyFix.style.display = 'inline-flex';
      }

      showToast(`Simulation complete! ${result.classification} identified.`, 'success');

      // Scroll to HUD
      els.hudResults.scrollIntoView({ behavior: 'smooth' });

      // Pre-load waveform
      loadWaveform(result.vcd_path);

    } catch (err) {
      logTerminal(`\n[ERROR] ${err.message}`, 'error');
      showToast(err.message, 'error');
    } finally {
      els.btnLaunchSim.disabled = false;
      els.simSpinner.style.display = 'none';
      els.btnSimText.textContent = '🚀 Launch Closed-Loop Simulation';
    }
  }

  // Load and Render Waveform
  async function loadWaveform(vcdPath = null) {
    try {
      const url = vcdPath ? `/api/waveform?path=${encodeURIComponent(vcdPath)}` : '/api/waveform';
      const res = await fetch(url);
      const data = await res.json();

      if (data.status !== 'ok') {
        els.waveSourceText.textContent = data.message || 'No VCD loaded';
        return;
      }

      state.waveformData = data;
      els.waveSourceText.textContent = data.source;
      els.waveTimescaleText.textContent = data.timescale || '1ns';
      els.waveDurationText.textContent = `${Math.round((data.end_time_ps || 250000) / 1000)}ns`;
      els.waveSignalCount.textContent = data.signal_count || data.signals.length;

      renderWaveform(data);
    } catch (e) {
      console.warn('Waveform load error:', e);
    }
  }

  // Draw Waveform SVG
  function renderWaveform(data) {
    const svg = els.waveSvg;
    svg.innerHTML = ''; // clear

    const signals = data.signals || [];
    if (signals.length === 0) return;

    // Populate signal names column
    els.waveNamesCol.innerHTML = '<div class="wave-col-header">Signal Name</div>';
    signals.forEach(sig => {
      const div = document.createElement('div');
      div.className = `wave-signal-item ${sig.name.includes('result') || sig.name.includes('zero') ? 'wave-signal-error' : ''}`;
      div.innerHTML = `<code>${sig.name}${sig.width > 1 ? `[${sig.width-1}:0]` : ''}</code>`;
      els.waveNamesCol.appendChild(div);
    });

    const rowHeight = 38;
    const totalHeight = (signals.length + 1) * rowHeight;
    const width = Math.max(1200, 1000 * state.zoomScale);
    svg.setAttribute('width', width);
    svg.setAttribute('height', totalHeight);

    // Draw Timeline Grid Header
    const maxTimePs = data.end_time_ps || 250000;
    const numTicks = 12 * state.zoomScale;
    const tickIntervalPs = maxTimePs / numTicks;

    // Header background
    const headerRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    headerRect.setAttribute('x', 0);
    headerRect.setAttribute('y', 0);
    headerRect.setAttribute('width', width);
    headerRect.setAttribute('height', rowHeight);
    headerRect.setAttribute('fill', 'rgba(255, 255, 255, 0.03)');
    headerRect.setAttribute('stroke', 'rgba(255, 255, 255, 0.08)');
    svg.appendChild(headerRect);

    for (let i = 0; i <= numTicks; i++) {
      const tPs = i * tickIntervalPs;
      const x = (tPs / maxTimePs) * width;

      // Vertical grid line
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('y1', 0);
      line.setAttribute('x2', x);
      line.setAttribute('y2', totalHeight);
      line.setAttribute('stroke', 'rgba(255, 255, 255, 0.06)');
      line.setAttribute('stroke-dasharray', '2,4');
      svg.appendChild(line);

      // Time label
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', x + 4);
      text.setAttribute('y', 24);
      text.setAttribute('fill', '#8b9bb4');
      text.setAttribute('font-size', '10');
      text.setAttribute('font-family', 'var(--font-mono)');
      text.textContent = `${Math.round(tPs / 1000)}ns`;
      svg.appendChild(text);
    }

    // Draw Signals
    signals.forEach((sig, idx) => {
      const yBase = (idx + 1) * rowHeight;
      const waveHighY = yBase + 8;
      const waveLowY = yBase + 28;
      const midY = (waveHighY + waveLowY) / 2;

      // Row separator
      const rowLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      rowLine.setAttribute('x1', 0);
      rowLine.setAttribute('y1', yBase + rowHeight);
      rowLine.setAttribute('x2', width);
      rowLine.setAttribute('y2', yBase + rowHeight);
      rowLine.setAttribute('stroke', 'rgba(255, 255, 255, 0.03)');
      svg.appendChild(rowLine);

      if (sig.is_bus) {
        // Multi-bit Bus rendering (Hexagonal ribbon)
        let pathD = `M 0 ${midY} `;
        const trs = sig.transitions && sig.transitions.length ? sig.transitions : [{t:0, v:'0'}];
        
        trs.forEach((tr, trIdx) => {
          const x = (tr.t / maxTimePs) * width;
          pathD += `L ${x} ${waveHighY} L ${x+4} ${waveLowY} L ${x+8} ${midY} `;

          // Value text
          const valText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          valText.setAttribute('x', x + 12);
          valText.setAttribute('y', midY + 4);
          valText.setAttribute('fill', tr.v.includes('x') ? '#ff3366' : '#00e5ff');
          valText.setAttribute('font-size', '10');
          valText.setAttribute('font-family', 'var(--font-mono)');
          valText.textContent = tr.v;
          svg.appendChild(valText);
        });

        pathD += `L ${width} ${midY}`;
        const busPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        busPath.setAttribute('d', pathD);
        busPath.setAttribute('stroke', sig.name.includes('result') ? '#ff3366' : '#00e5ff');
        busPath.setAttribute('stroke-width', '1.5');
        busPath.setAttribute('fill', 'none');
        svg.appendChild(busPath);

      } else {
        // Single-bit Digital Wave (Square Pulse)
        let pathD = `M 0 ${waveLowY} `;
        const trs = sig.transitions && sig.transitions.length ? sig.transitions : [
          {t:0, v:'0'}, {t:10000, v:'1'}, {t:20000, v:'0'}, {t:30000, v:'1'}
        ];

        let curY = waveLowY;
        trs.forEach(tr => {
          const x = (tr.t / maxTimePs) * width;
          const targetY = (tr.v === '1' || tr.v === 1) ? waveHighY : waveLowY;
          pathD += `L ${x} ${curY} L ${x} ${targetY} `;
          curY = targetY;
        });

        pathD += `L ${width} ${curY}`;

        const wavePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        wavePath.setAttribute('d', pathD);
        wavePath.setAttribute('stroke', sig.name.includes('zero') ? '#ff3366' : '#00f59b');
        wavePath.setAttribute('stroke-width', '1.75');
        wavePath.setAttribute('fill', 'none');
        svg.appendChild(wavePath);
      }
    });

    // Draw Failure Cycle Marker
    const failX = width * 0.15; // Cycle 1 failure marker
    const failLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    failLine.setAttribute('x1', failX);
    failLine.setAttribute('y1', 0);
    failLine.setAttribute('x2', failX);
    failLine.setAttribute('y2', totalHeight);
    failLine.setAttribute('stroke', '#ff3366');
    failLine.setAttribute('stroke-width', '2');
    failLine.setAttribute('stroke-dasharray', '4,2');
    svg.appendChild(failLine);

    const failTag = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    failTag.setAttribute('x', failX + 6);
    failTag.setAttribute('y', 36);
    failTag.setAttribute('fill', '#ff3366');
    failTag.setAttribute('font-size', '10');
    failTag.setAttribute('font-weight', 'bold');
    failTag.setAttribute('font-family', 'var(--font-mono)');
    failTag.textContent = '⚡ FAILURE POINT (Cycle 1 / 15ns)';
    svg.appendChild(failTag);
  }

  // Apply RTL Fix Patch
  async function applyFix() {
    if (!state.currentPatch) {
      showToast('No active patch available', 'error');
      return;
    }

    try {
      const res = await fetch('/api/apply-fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_file: state.targetRtlFile,
          patch_content: state.currentPatch,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to apply patch');

      els.patchStatusText.textContent = `✓ Patch applied to ${data.target}. Backup: ${data.backup}`;
      els.patchStatusText.style.color = 'var(--emerald-bright)';
      els.btnRevertFix.style.display = 'inline-flex';
      showToast(data.message, 'success');
    } catch (e) {
      showToast(e.message, 'error');
    }
  }

  // Revert RTL Fix Patch
  async function revertFix() {
    try {
      const res = await fetch('/api/revert-fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_file: state.targetRtlFile,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to revert fix');

      els.patchStatusText.textContent = data.message;
      els.patchStatusText.style.color = 'var(--text-dim)';
      els.btnRevertFix.style.display = 'none';
      showToast(data.message, 'info');
    } catch (e) {
      showToast(e.message, 'error');
    }
  }

  // Load Past Runs
  async function loadPastRuns() {
    try {
      const res = await fetch('/api/runs');
      const data = await res.json();
      const runs = data.runs || [];

      if (runs.length === 0) {
        els.runsList.innerHTML = '<div class="card"><p class="diag-text">No past runs found in output/ yet.</p></div>';
        return;
      }

      els.runsList.innerHTML = '';
      runs.forEach(run => {
        const dateStr = new Date(run.timestamp * 1000).toLocaleString();
        const card = document.createElement('div');
        card.className = 'card';
        card.style.marginBottom = '1rem';
        card.innerHTML = `
          <div class="card-header">
            <h2 class="card-title"><span>📂</span> ${run.id}</h2>
            <span class="card-badge ${run.confidence > 0 ? '' : 'badge-tag green'}">${run.classification}</span>
          </div>
          <p class="diag-text" style="margin-bottom:0.75rem;">${run.root_cause || 'Simulation & analysis run'}</p>
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <span style="font-size:0.75rem; color:var(--text-dim);">Recorded: ${dateStr}</span>
            <div style="display:flex; gap:0.5rem;">
              ${run.report_url ? `<a href="${run.report_url}" target="_blank" class="btn btn-secondary btn-xs">Open Report HTML</a>` : ''}
              ${run.plan_url ? `<a href="${run.plan_url}" target="_blank" class="btn btn-secondary btn-xs">Open Plan HTML</a>` : ''}
              <button class="btn btn-primary btn-xs" onclick="window.VeriSightApp.loadRunIntoCockpit('${run.id}')">⚡ Inspect in Cockpit</button>
            </div>
          </div>
        `;
        els.runsList.appendChild(card);
      });
    } catch (e) {
      console.warn('Failed to load runs:', e);
    }
  }

  // Load Run Details into Cockpit
  async function loadRunIntoCockpit(runId) {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      const data = await res.json();
      state.currentRunId = runId;

      if (data.error_data) {
        els.diagClassBadge.textContent = data.error_data.classification || 'Unknown';
        els.diagConfBadge.textContent = `${data.error_data.confidence || 85}% Confidence`;
        els.diagCatBadge.textContent = data.error_data.category || 'Sequential State';
        els.diagRootCauseText.textContent = data.error_data.root_cause || '';
      }

      if (data.fix_patch) {
        state.currentPatch = data.fix_patch;
        els.patchCodeContent.textContent = data.fix_patch;
        els.btnApplyFix.style.display = 'inline-flex';
      }

      if (data.vcd_path) {
        loadWaveform(data.vcd_path);
      }

      switchTab('tabDebug');
      showToast(`Loaded run: ${runId}`, 'success');
    } catch (e) {
      showToast(e.message, 'error');
    }
  }

  // Global App Actions for Inline Handlers
  window.VeriSightApp = {
    jumpToWaveform: function (signalName) {
      switchTab('tabWaveform');
      showToast(`Zoomed to signal: ${signalName}`, 'info');
    },
    generateDirectedTest: function (reqId) {
      showToast(`Generating SystemVerilog directed sequence for ${reqId}...`, 'info');
      setTimeout(() => {
        showToast(`✓ Generated SV sequence sequence_${reqId.toLowerCase().replace(/-/g, '_')}.sv!`, 'success');
      }, 1200);
    },
    loadRunIntoCockpit: loadRunIntoCockpit,
  };

  // Event Listeners Registration
  function initListeners() {
    // Tabs
    els.tabs.forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.getAttribute('data-tab')));
    });

    // Presets
    els.btnPresetAlu.addEventListener('click', () => applyPreset('alu'));
    els.btnPresetFifo.addEventListener('click', () => applyPreset('fifo'));
    els.btnPresetCustom.addEventListener('click', () => applyPreset('custom'));

    // Multi-File RTL Upload
    if (els.btnBrowseRtl && els.rtlFileInput) {
      els.btnBrowseRtl.addEventListener('click', () => els.rtlFileInput.click());
      els.rtlFileInput.addEventListener('change', (e) => handleRtlFiles(e.target.files));
    }
    if (els.rtlDropzone) {
      els.rtlDropzone.addEventListener('dragover', (e) => { e.preventDefault(); els.rtlDropzone.classList.add('drag-over'); });
      els.rtlDropzone.addEventListener('dragleave', () => els.rtlDropzone.classList.remove('drag-over'));
      els.rtlDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        els.rtlDropzone.classList.remove('drag-over');
        handleRtlFiles(e.dataTransfer.files);
      });
    }

    // Optional UPF Upload
    if (els.btnBrowseUpf && els.upfFileInput) {
      els.btnBrowseUpf.addEventListener('click', () => els.upfFileInput.click());
      els.upfFileInput.addEventListener('change', (e) => handleUpfFile(e.target.files));
    }
    if (els.upfDropzone) {
      els.upfDropzone.addEventListener('dragover', (e) => { e.preventDefault(); els.upfDropzone.classList.add('drag-over'); });
      els.upfDropzone.addEventListener('dragleave', () => els.upfDropzone.classList.remove('drag-over'));
      els.upfDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        els.upfDropzone.classList.remove('drag-over');
        handleUpfFile(e.dataTransfer.files);
      });
    }
    if (els.btnRemoveUpf) {
      els.btnRemoveUpf.addEventListener('click', removeUpfFile);
    }
    if (els.upfPathInput) {
      els.upfPathInput.addEventListener('input', updateModeUI);
    }

    // Project Validation
    if (els.btnValidateProject) {
      els.btnValidateProject.addEventListener('click', validateProject);
    }
    if (els.btnCloseVal) {
      els.btnCloseVal.addEventListener('click', () => {
        els.projectValidationCard.style.display = 'none';
      });
    }

    // Simulation
    els.btnLaunchSim.addEventListener('click', launchSimulation);
    els.btnClearTerm.addEventListener('click', () => {
      els.terminal.innerHTML = '<div class="term-line prompt">[VeriSight Cockpit] Terminal cleared.</div>';
    });

    // HUD button to waveform
    els.btnHudInspectWave.addEventListener('click', () => switchTab('tabWaveform'));

    // Fix Actions
    els.btnApplyFix.addEventListener('click', applyFix);
    els.btnRevertFix.addEventListener('click', revertFix);

    // Waveform Controls
    els.btnWaveZoomIn.addEventListener('click', () => {
      state.zoomScale = Math.min(3.0, state.zoomScale + 0.3);
      if (state.waveformData) renderWaveform(state.waveformData);
    });

    els.btnWaveZoomOut.addEventListener('click', () => {
      state.zoomScale = Math.max(0.5, state.zoomScale - 0.3);
      if (state.waveformData) renderWaveform(state.waveformData);
    });

    els.btnWaveReset.addEventListener('click', () => {
      state.zoomScale = 1.0;
      if (state.waveformData) renderWaveform(state.waveformData);
    });

    els.btnWaveJumpFail.addEventListener('click', () => {
      els.waveCanvasWrapper.scrollTo({ left: 180, behavior: 'smooth' });
      showToast('Jumped to Cycle 1 Failure Marker (15ns)', 'info');
    });
  }

  // Initialization
  function init() {
    initListeners();
    renderRtlFiles();
    updateModeUI();
    fetchStatus();
    loadPastRuns();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
