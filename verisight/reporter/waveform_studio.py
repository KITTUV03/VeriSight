"""
VeriSight Silicon Waveform Studio (VCD / FSDB Trace Viewer).

Embedded interactive client-side waveform viewer for RTL simulation traces,
supporting clock lines, 1-bit logic, multi-bit buses with transition envelopes,
unknown 'x' hazard stripes, high-Z 'z', interactive measurement cursors,
error cycle markers, zoom/pan controls, and client-side drag-and-drop VCD ingestion.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from verisight.parsers.vcd_parser import parse_vcd
from verisight.utils.logger import get_logger

logger = get_logger("waveform_studio")


def load_sample_vcd(vcd_path: str) -> Dict[str, Any]:
    """Parse a VCD file into a lightweight JSON dict for browser embedding."""
    p = Path(vcd_path)
    if not p.exists():
        return {}
    try:
        data = parse_vcd(str(p))
        if data.tool_status != "ok" or not data.signals:
            return {"raw_text": p.read_text(encoding="utf-8", errors="replace")}
        
        # Build normalized signal list
        signals = []
        max_time = 0
        for name, sig in data.signals.items():
            trans = [{"t": t.time_ps // 1000, "v": t.value} for t in sig.transitions]
            if trans:
                max_time = max(max_time, trans[-1]["t"])
            signals.append({
                "name": name.split(".")[-1],
                "hierarchy": name,
                "width": sig.width,
                "has_x": sig.has_x,
                "transitions": trans,
            })
        
        return {
            "name": p.name,
            "timescale": data.timescale or "1ns",
            "max_time": max_time,
            "signals": signals,
            "raw_text": p.read_text(encoding="utf-8", errors="replace"),
        }
    except Exception as e:
        logger.warning(f"Could not pre-parse sample VCD {vcd_path}: {e}")
        try:
            return {"raw_text": p.read_text(encoding="utf-8", errors="replace")}
        except Exception:
            return {}


def generate_waveform_studio_tab(
    vcd_path: Optional[str] = None,
    failure_timestamp_ns: Optional[float] = 65.0,
    failure_label: str = "Assertion / Scoreboard Mismatch",
    tab_id: str = "tab-waveform",
) -> str:
    """
    Generate self-contained HTML, CSS, and JS for the embedded VCD Waveform Studio.
    """
    # Load default traces if available
    alu_vcd_path = Path("examples/waveforms/alu_failure_trace.vcd")
    fifo_vcd_path = Path("examples/waveforms/fifo_xprop_trace.vcd")

    alu_trace = load_sample_vcd(str(alu_vcd_path)) if alu_vcd_path.exists() else {}
    fifo_trace = load_sample_vcd(str(fifo_vcd_path)) if fifo_vcd_path.exists() else {}
    custom_trace = load_sample_vcd(vcd_path) if vcd_path and Path(vcd_path).exists() else {}

    alu_json_str = json.dumps(alu_trace).replace("</script>", "<\\/script>")
    fifo_json_str = json.dumps(fifo_trace).replace("</script>", "<\\/script>")
    custom_json_str = json.dumps(custom_trace).replace("</script>", "<\\/script>")

    return f"""
    <!-- ============================================================================== -->
    <!-- VERISIGHT SILICON WAVEFORM STUDIO (VCD / TRACE VIEWER)                         -->
    <!-- ============================================================================== -->
    <div id="{tab_id}" class="tab-pane">
        <div class="wave-studio-container">
            <!-- Studio Toolbar -->
            <div class="wave-toolbar">
                <div class="wave-tb-left">
                    <span class="wave-brand">🌊 Waveform Studio</span>
                    <span class="wave-badge" id="waveTraceBadge">ALU Failure Trace (65ns)</span>
                    <span class="wave-timescale" id="waveTimescale">Scale: 1ns / tick</span>
                </div>
                
                <div class="wave-tb-center">
                    <div class="btn-group">
                        <button class="wave-btn active" id="btnTraceAlu" onclick="loadTracePreset('alu')">ALU Trace</button>
                        <button class="wave-btn" id="btnTraceFifo" onclick="loadTracePreset('fifo')">FIFO X-Prop</button>
                        <button class="wave-btn" id="btnTraceCustom" onclick="document.getElementById('waveFileInput').click()">📂 Open VCD...</button>
                        <input type="file" id="waveFileInput" accept=".vcd,.txt" style="display:none;" onchange="handleVcdFileSelected(event)">
                    </div>

                    <div class="wave-sep"></div>

                    <!-- Navigation & Time Jump -->
                    <div class="btn-group">
                        <button class="wave-btn" title="Jump to Start" onclick="jumpWaveTime(0)">⏮️</button>
                        <button class="wave-btn" title="Step Back 10ns" onclick="stepWaveTime(-10)">⏪ -10ns</button>
                        <button class="wave-btn" title="Step Forward 10ns" onclick="stepWaveTime(10)">+10ns ⏩</button>
                        <button class="wave-btn wave-btn-danger" title="Jump to Failure Cycle" onclick="jumpToFailure({failure_timestamp_ns})">🎯 Failure @{failure_timestamp_ns}ns</button>
                    </div>

                    <div class="wave-sep"></div>

                    <!-- Zoom Controls -->
                    <div class="btn-group">
                        <button class="wave-btn" title="Zoom Out" onclick="zoomWave(0.8)">🔍−</button>
                        <button class="wave-btn" title="Zoom In" onclick="zoomWave(1.25)">🔍+</button>
                        <button class="wave-btn" title="Zoom Fit" onclick="zoomFitWave()">↔️ Fit</button>
                        <button class="wave-btn" title="Reset Zoom" onclick="resetWaveZoom()">1:1</button>
                    </div>

                    <div class="wave-sep"></div>

                    <!-- Radix Toggle -->
                    <div class="btn-group">
                        <button class="wave-btn active" id="radixHex" onclick="setWaveRadix('hex')">HEX</button>
                        <button class="wave-btn" id="radixBin" onclick="setWaveRadix('bin')">BIN</button>
                        <button class="wave-btn" id="radixDec" onclick="setWaveRadix('dec')">DEC</button>
                    </div>
                </div>

                <div class="wave-tb-right">
                    <input type="text" id="waveSignalSearch" class="wave-search" placeholder="Filter signals..." oninput="filterWaveSignals()">
                    <button class="wave-btn" title="Export Waveform Image" onclick="exportWaveformPng()">📷 Snapshot</button>
                </div>
            </div>

            <!-- Drag & Drop Dropzone Banner (Collapsible/Ambient) -->
            <div class="wave-drop-target" id="waveDropTarget" ondragover="handleWaveDragOver(event)" ondragleave="handleWaveDragLeave(event)" ondrop="handleWaveDrop(event)">
                <div class="wave-cursor-banner">
                    <div class="cur-time-display">
                        <span class="cur-lbl">MARKER T:</span>
                        <span class="cur-val" id="cursorTimeReadout">{failure_timestamp_ns:.1f} ns</span>
                    </div>
                    <div class="cur-status-display" id="cursorEventReadout">
                        <span class="pulse-dot"></span>
                        <span class="cur-msg">Highlighted Anomaly: {failure_label} @ {failure_timestamp_ns}ns</span>
                    </div>
                    <div class="cur-hint">Drag & drop any simulator .vcd to visualize here</div>
                </div>

                <!-- Main Waveform Viewer Viewport -->
                <div class="wave-viewport" id="waveViewport">
                    <!-- Left Signal Names & Live Value Panel -->
                    <div class="wave-signals-panel" id="waveSignalsPanel">
                        <div class="wave-signal-header">
                            <span class="col-sig-name">Signal Hierarchy</span>
                            <span class="col-sig-val">Value @ T</span>
                        </div>
                        <div class="wave-signal-rows" id="waveSignalRowsContainer">
                            <!-- Populated dynamically -->
                        </div>
                    </div>

                    <!-- Right Waveform Canvas Area -->
                    <div class="wave-canvas-wrapper" id="waveCanvasWrapper" onscroll="syncWaveScroll(event)">
                        <!-- Time Ruler Canvas -->
                        <div class="wave-ruler-sticky">
                            <canvas id="waveRulerCanvas" height="28"></canvas>
                        </div>
                        <!-- Waveform Tracks Canvas -->
                        <div class="wave-canvas-body" id="waveCanvasBody">
                            <canvas id="waveCanvas" onmousemove="handleWaveMouseMove(event)" onclick="handleWaveClick(event)"></canvas>
                            <!-- Cursor Indicator Line -->
                            <div class="wave-cursor-line" id="waveCursorLine">
                                <div class="wave-cursor-flag" id="waveCursorFlag">{failure_timestamp_ns}ns</div>
                            </div>
                            <!-- Error Highlight Band -->
                            <div class="wave-error-band" id="waveErrorBand" style="display:block;">
                                <div class="wave-error-flag" id="waveErrorFlag">⚠️ ERROR @ {failure_timestamp_ns}ns</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Waveform Legend / Footer Bar -->
            <div class="wave-legend-bar">
                <div class="legend-item"><span class="leg-color leg-clk"></span> Clock Pulse</div>
                <div class="legend-item"><span class="leg-color leg-logic"></span> Logic High (1) / Low (0)</div>
                <div class="legend-item"><span class="leg-color leg-bus"></span> Multi-bit Bus Hex Envelope</div>
                <div class="legend-item"><span class="leg-color leg-x"></span> Unknown (X) Hazard Stripe</div>
                <div class="legend-item"><span class="leg-color leg-z"></span> High-Z (Z) Float</div>
                <div class="legend-item"><span class="leg-color leg-err"></span> Assertion / Scoreboard Violation</div>
                <div class="wave-stats" id="waveStatsText">9 Signals • 120ns Window • Click canvas to measure</div>
            </div>
        </div>
    </div>

    <!-- WAVEFORM STUDIO STYLES -->
    <style>
        .wave-studio-container {{
            background: #080c14;
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "JetBrains Mono", monospace;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
            margin: 16px 0 24px;
        }}
        .wave-toolbar {{
            background: #0d1322;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .wave-tb-left {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .wave-brand {{
            font-weight: 800;
            font-size: 14px;
            color: #38bdf8;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .wave-badge {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #7dd3fc;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        .wave-timescale {{
            color: #64748b;
            font-size: 11px;
            font-family: "JetBrains Mono", monospace;
        }}
        .wave-tb-center {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .wave-sep {{
            width: 1px;
            height: 20px;
            background: rgba(255, 255, 255, 0.12);
            margin: 0 4px;
        }}
        .wave-btn {{
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 4px 10px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: inherit;
        }}
        .wave-btn:hover {{
            background: #334155;
            color: #ffffff;
            border-color: rgba(56, 189, 248, 0.4);
        }}
        .wave-btn.active {{
            background: #0284c7;
            color: #ffffff;
            border-color: #38bdf8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
        }}
        .wave-btn-danger {{
            background: rgba(239, 68, 68, 0.2);
            border-color: rgba(239, 68, 68, 0.4);
            color: #fca5a5;
        }}
        .wave-btn-danger:hover {{
            background: #ef4444;
            color: #ffffff;
        }}
        .wave-search {{
            background: #111827;
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #f1f5f9;
            padding: 4px 10px;
            border-radius: 5px;
            font-size: 11px;
            width: 130px;
            outline: none;
            transition: width 0.2s;
        }}
        .wave-search:focus {{
            border-color: #38bdf8;
            width: 180px;
        }}
        .wave-cursor-banner {{
            background: #0b111e;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding: 6px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 11px;
        }}
        .cur-time-display {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .cur-lbl {{
            color: #64748b;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .cur-val {{
            color: #38bdf8;
            font-weight: 800;
            font-size: 13px;
            font-family: "JetBrains Mono", monospace;
        }}
        .cur-status-display {{
            display: flex;
            align-items: center;
            gap: 6px;
            color: #fca5a5;
            font-weight: 600;
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ef4444;
            box-shadow: 0 0 8px #ef4444;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.8); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
        .cur-hint {{
            color: #475569;
            font-style: italic;
        }}
        .wave-viewport {{
            display: flex;
            height: 380px;
            position: relative;
            background: #080c14;
            user-select: none;
        }}
        .wave-signals-panel {{
            width: 280px;
            flex-shrink: 0;
            background: #0a0f1c;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            flex-direction: column;
            overflow-y: hidden;
            z-index: 5;
        }}
        .wave-signal-header {{
            height: 28px;
            background: #0f172a;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            padding: 0 10px;
            font-size: 11px;
            font-weight: 700;
            color: #94a3b8;
        }}
        .col-sig-name {{ flex: 1; }}
        .col-sig-val {{ width: 85px; text-align: right; }}
        .wave-signal-rows {{
            overflow-y: hidden;
            flex: 1;
        }}
        .wave-sig-row {{
            height: 34px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-size: 11px;
            color: #cbd5e1;
            font-family: "JetBrains Mono", monospace;
            box-sizing: border-box;
            transition: background 0.1s;
        }}
        .wave-sig-row:hover {{
            background: rgba(56, 189, 248, 0.06);
        }}
        .sig-tag-clk {{
            color: #4ade80;
            margin-right: 6px;
            font-size: 10px;
        }}
        .sig-tag-bus {{
            color: #38bdf8;
            margin-right: 6px;
            font-size: 10px;
        }}
        .sig-tag-wire {{
            color: #cbd5e1;
            margin-right: 6px;
            font-size: 10px;
        }}
        .sig-name-text {{
            flex: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .sig-val-cur {{
            width: 85px;
            text-align: right;
            font-weight: 700;
            color: #38bdf8;
        }}
        .sig-val-cur.val-x {{
            color: #ef4444;
            background: rgba(239, 68, 68, 0.15);
            padding: 1px 4px;
            border-radius: 3px;
        }}
        .sig-val-cur.val-z {{
            color: #f59e0b;
        }}
        .wave-canvas-wrapper {{
            flex: 1;
            overflow-x: auto;
            overflow-y: hidden;
            position: relative;
            background: #080c14;
        }}
        .wave-ruler-sticky {{
            height: 28px;
            background: #0f172a;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            position: sticky;
            top: 0;
            left: 0;
            z-index: 4;
        }}
        .wave-canvas-body {{
            position: relative;
        }}
        #waveCanvas {{
            display: block;
            cursor: crosshair;
        }}
        .wave-cursor-line {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #38bdf8;
            box-shadow: 0 0 8px #38bdf8;
            pointer-events: none;
            z-index: 10;
            transition: left 0.04s ease-out;
        }}
        .wave-cursor-flag {{
            position: absolute;
            top: -24px;
            left: -28px;
            background: #0284c7;
            color: #ffffff;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 4px;
            white-space: nowrap;
            font-family: "JetBrains Mono", monospace;
        }}
        .wave-error-band {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #ef4444;
            box-shadow: 0 0 12px #ef4444;
            pointer-events: none;
            z-index: 8;
        }}
        .wave-error-flag {{
            position: absolute;
            top: 4px;
            left: 6px;
            background: rgba(239, 68, 68, 0.9);
            color: #ffffff;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 4px;
            white-space: nowrap;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }}
        .wave-legend-bar {{
            background: #0d1322;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            padding: 6px 14px;
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
            font-size: 11px;
            color: #94a3b8;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .leg-color {{
            width: 12px;
            height: 6px;
            border-radius: 2px;
            display: inline-block;
        }}
        .leg-clk {{ background: #4ade80; }}
        .leg-logic {{ background: #38bdf8; }}
        .leg-bus {{ background: #818cf8; }}
        .leg-x {{ background: repeating-linear-gradient(45deg, #ef4444, #ef4444 2px, #7f1d1d 2px, #7f1d1d 4px); }}
        .leg-z {{ background: #f59e0b; }}
        .leg-err {{ background: #ef4444; }}
        .wave-stats {{
            margin-left: auto;
            color: #64748b;
            font-family: "JetBrains Mono", monospace;
        }}
    </style>

    <!-- WAVEFORM STUDIO CLIENT-SIDE JAVASCRIPT LOGIC -->
    <script>
        // Preset Trace Databases
        const PRESET_TRACES = {{
            alu: {alu_json_str},
            fifo: {fifo_json_str},
            custom: {custom_json_str}
        }};

        // State Machine
        let activeTrace = null;
        let waveSignals = [];
        let waveMaxTime = 120; // in ns
        let wavePixPerNs = 8.0; // scale factor
        let waveCursorTime = {failure_timestamp_ns};
        let waveFailureTime = {failure_timestamp_ns};
        let waveFailureLabel = "{failure_label}";
        let waveRadix = 'hex';
        let waveSearchFilter = '';
        const ROW_HEIGHT = 34;

        // Initialize Waveform Viewer on page load
        function initWaveformStudio() {{
            if (PRESET_TRACES.alu && PRESET_TRACES.alu.signals && PRESET_TRACES.alu.signals.length > 0) {{
                loadTraceData(PRESET_TRACES.alu);
            }} else if (PRESET_TRACES.custom && PRESET_TRACES.custom.signals && PRESET_TRACES.custom.signals.length > 0) {{
                loadTraceData(PRESET_TRACES.custom);
            }} else {{
                // Parse embedded raw text fallback
                if (PRESET_TRACES.alu && PRESET_TRACES.alu.raw_text) {{
                    const parsed = parseClientVcd(PRESET_TRACES.alu.raw_text, 'alu_failure_trace.vcd');
                    loadTraceData(parsed);
                }}
            }}
        }}

        function loadTracePreset(presetKey) {{
            document.querySelectorAll('.wave-tb-center .wave-btn').forEach(b => b.classList.remove('active'));
            if (presetKey === 'alu') {{
                const btn = document.getElementById('btnTraceAlu');
                if (btn) btn.classList.add('active');
                document.getElementById('waveTraceBadge').innerText = 'ALU Failure Trace (65ns)';
                waveFailureTime = 65.0;
                waveFailureLabel = "Assertion Violation: result corrupted by overflow";
                if (PRESET_TRACES.alu.signals) {{
                    loadTraceData(PRESET_TRACES.alu);
                }} else if (PRESET_TRACES.alu.raw_text) {{
                    loadTraceData(parseClientVcd(PRESET_TRACES.alu.raw_text, 'alu_failure_trace.vcd'));
                }}
            }} else if (presetKey === 'fifo') {{
                const btn = document.getElementById('btnTraceFifo');
                if (btn) btn.classList.add('active');
                document.getElementById('waveTraceBadge').innerText = 'FIFO X-Propagation Trace (65ns Underflow)';
                waveFailureTime = 65.0;
                waveFailureLabel = "FIFO Underflow Error: rd_data sampled uninitialized X";
                if (PRESET_TRACES.fifo.signals) {{
                    loadTraceData(PRESET_TRACES.fifo);
                }} else if (PRESET_TRACES.fifo.raw_text) {{
                    loadTraceData(parseClientVcd(PRESET_TRACES.fifo.raw_text, 'fifo_xprop_trace.vcd'));
                }}
            }}
            jumpToFailure(waveFailureTime);
        }}

        function loadTraceData(data) {{
            if (!data || !data.signals) return;
            activeTrace = data;
            waveSignals = data.signals;
            waveMaxTime = Math.max(data.max_time || 120, 80);
            renderSignalNames();
            updateCanvasDimensions();
            renderRuler();
            renderWaveforms();
            updateCursorPosition(waveCursorTime);
            updateSignalValuesAtCursor(waveCursorTime);
            updateStatsText();
        }}

        // Fast Client-Side VCD Parser
        function parseClientVcd(text, filename) {{
            const lines = text.split(/\\r?\\n/);
            let timescale = '1ns';
            let signals = [];
            let idToSig = {{}};
            let currentTime = 0;
            let maxTime = 0;

            for (let i = 0; i < lines.length; i++) {{
                const line = lines[i].trim();
                if (!line) continue;

                if (line.startsWith('$timescale')) {{
                    const m = text.match(/\\$timescale\\s+([0-9]+\\s*[a-z]+)/i);
                    if (m) timescale = m[1].replace(/\\s+/g, '');
                }} else if (line.startsWith('$var')) {{
                    const parts = line.split(/\\s+/);
                    // $var wire 8 & result [7:0] $end
                    if (parts.length >= 5) {{
                        const type = parts[1];
                        const width = parseInt(parts[2], 10) || 1;
                        const id = parts[3];
                        const name = parts[4];
                        const sigObj = {{
                            name: name,
                            hierarchy: name,
                            width: width,
                            has_x: false,
                            transitions: []
                        }};
                        signals.push(sigObj);
                        idToSig[id] = sigObj;
                    }}
                }} else if (line.startsWith('#')) {{
                    currentTime = parseInt(line.substring(1), 10) || 0;
                    if (currentTime > maxTime) maxTime = currentTime;
                }} else if (line.startsWith('b') || line.startsWith('B')) {{
                    // Multi-bit transition: b00010100 %
                    const spaceIdx = line.indexOf(' ');
                    if (spaceIdx > 0) {{
                        const val = line.substring(1, spaceIdx).trim();
                        const id = line.substring(spaceIdx + 1).trim();
                        if (idToSig[id]) {{
                            if (val.includes('x') || val.includes('X')) idToSig[id].has_x = true;
                            idToSig[id].transitions.push({{ t: currentTime, v: val }});
                        }}
                    }}
                }} else if (line.length >= 2 && !line.startsWith('$')) {{
                    // 1-bit transition: 1!, 0!, x!, z!
                    const val = line[0];
                    const id = line.substring(1);
                    if (idToSig[id]) {{
                        if (val === 'x' || val === 'X') idToSig[id].has_x = true;
                        idToSig[id].transitions.push({{ t: currentTime, v: val }});
                    }}
                }}
            }}

            return {{
                name: filename || 'uploaded_trace.vcd',
                timescale: timescale,
                max_time: maxTime,
                signals: signals
            }};
        }}

        // Render Left Panel Signal List
        function renderSignalNames() {{
            const container = document.getElementById('waveSignalRowsContainer');
            container.innerHTML = '';
            const filter = waveSearchFilter.toLowerCase();

            waveSignals.forEach((sig, idx) => {{
                if (filter && !sig.name.toLowerCase().includes(filter)) return;
                const row = document.createElement('div');
                row.className = 'wave-sig-row';
                row.id = 'sig-row-' + idx;

                let iconHtml = '<span class="sig-tag-wire">⚡</span>';
                if (sig.name.toLowerCase().includes('clk')) {{
                    iconHtml = '<span class="sig-tag-clk">⏱️</span>';
                }} else if (sig.width > 1) {{
                    iconHtml = '<span class="sig-tag-bus">🚌 [' + (sig.width - 1) + ':0]</span>';
                }}

                row.innerHTML = `
                    ` + iconHtml + `
                    <span class="sig-name-text" title="` + sig.name + `">` + sig.name + `</span>
                    <span class="sig-val-cur" id="sig-val-` + idx + `">—</span>
                `;
                container.appendChild(row);
            }});
        }}

        function updateCanvasDimensions() {{
            const canvas = document.getElementById('waveCanvas');
            const rulerCanvas = document.getElementById('waveRulerCanvas');
            const visibleSignals = getVisibleSignals();
            const totalWidth = Math.max(800, (waveMaxTime + 20) * wavePixPerNs);
            const totalHeight = visibleSignals.length * ROW_HEIGHT;

            canvas.width = totalWidth;
            canvas.height = totalHeight;
            rulerCanvas.width = totalWidth;
            rulerCanvas.height = 28;

            document.getElementById('waveCanvasBody').style.width = totalWidth + 'px';
            document.getElementById('waveCanvasBody').style.height = totalHeight + 'px';
        }}

        function getVisibleSignals() {{
            const filter = waveSearchFilter.toLowerCase();
            return waveSignals.filter(s => !filter || s.name.toLowerCase().includes(filter));
        }}

        // Draw Time Ruler
        function renderRuler() {{
            const ruler = document.getElementById('waveRulerCanvas');
            const ctx = ruler.getContext('2d');
            const width = ruler.width;
            ctx.clearRect(0, 0, width, 28);

            ctx.fillStyle = '#0f172a';
            ctx.fillRect(0, 0, width, 28);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
            ctx.lineWidth = 1;
            ctx.fillStyle = '#64748b';
            ctx.font = '10px "JetBrains Mono", monospace';

            const tickIntervalNs = wavePixPerNs < 5 ? 20 : (wavePixPerNs > 15 ? 5 : 10);

            for (let t = 0; t <= waveMaxTime + 10; t += tickIntervalNs) {{
                const x = t * wavePixPerNs;
                ctx.beginPath();
                ctx.moveTo(x, 14);
                ctx.lineTo(x, 28);
                ctx.stroke();

                ctx.fillText(t + 'ns', x + 3, 12);

                // Minor ticks
                if (tickIntervalNs >= 10) {{
                    const subX = (t + tickIntervalNs / 2) * wavePixPerNs;
                    ctx.beginPath();
                    ctx.moveTo(subX, 20);
                    ctx.lineTo(subX, 28);
                    ctx.stroke();
                }}
            }}
        }}

        // Render Waveform Tracks
        function renderWaveforms() {{
            const canvas = document.getElementById('waveCanvas');
            const ctx = canvas.getContext('2d');
            const width = canvas.width;
            const height = canvas.height;
            const visibleSignals = getVisibleSignals();

            ctx.clearRect(0, 0, width, height);

            // Background & Grid
            ctx.fillStyle = '#080c14';
            ctx.fillRect(0, 0, width, height);

            // Vertical Time Gridlines
            const tickIntervalNs = wavePixPerNs < 5 ? 20 : (wavePixPerNs > 15 ? 5 : 10);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
            ctx.lineWidth = 1;
            for (let t = 0; t <= waveMaxTime + 10; t += tickIntervalNs) {{
                const x = t * wavePixPerNs;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
                ctx.stroke();
            }}

            // Draw each signal row
            visibleSignals.forEach((sig, idx) => {{
                const rowTop = idx * ROW_HEIGHT;
                const rowBottom = rowTop + ROW_HEIGHT;
                const midY = rowTop + ROW_HEIGHT / 2;
                const highY = rowTop + 6;
                const lowY = rowBottom - 6;

                // Alternating row background
                if (idx % 2 === 1) {{
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.015)';
                    ctx.fillRect(0, rowTop, width, ROW_HEIGHT);
                }}

                // Horizontal dividing line
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
                ctx.beginPath();
                ctx.moveTo(0, rowBottom);
                ctx.lineTo(width, rowBottom);
                ctx.stroke();

                if (!sig.transitions || sig.transitions.length === 0) return;

                const isClk = sig.name.toLowerCase().includes('clk');
                const isBus = sig.width > 1;

                if (isClk) {{
                    // Draw crisp clock wave
                    ctx.strokeStyle = '#4ade80';
                    ctx.lineWidth = 1.8;
                    ctx.beginPath();
                    let lastVal = sig.transitions[0].v;
                    let lastX = 0;
                    let lastY = (lastVal === '1') ? highY : lowY;
                    ctx.moveTo(lastX, lastY);

                    for (let i = 0; i < sig.transitions.length; i++) {{
                        const tr = sig.transitions[i];
                        const x = tr.t * wavePixPerNs;
                        ctx.lineTo(x, lastY);
                        const curY = (tr.v === '1') ? highY : lowY;
                        ctx.lineTo(x, curY);
                        lastY = curY;
                        lastX = x;
                    }}
                    ctx.lineTo(width, lastY);
                    ctx.stroke();
                }} else if (isBus) {{
                    // Draw multi-bit bus with hexagonal envelopes and centered text
                    for (let i = 0; i < sig.transitions.length; i++) {{
                        const tr = sig.transitions[i];
                        const nextTr = sig.transitions[i + 1];
                        const startX = tr.t * wavePixPerNs;
                        const endX = nextTr ? (nextTr.t * wavePixPerNs) : width;
                        const val = tr.v;
                        const isX = val.includes('x') || val.includes('X');
                        const isZ = val.includes('z') || val.includes('Z');
                        const segW = endX - startX;

                        if (segW <= 0) continue;

                        const envW = Math.min(4, segW / 2);

                        // Fill polygon
                        ctx.beginPath();
                        ctx.moveTo(startX + envW, highY);
                        ctx.lineTo(endX - envW, highY);
                        ctx.lineTo(endX, midY);
                        ctx.lineTo(endX - envW, lowY);
                        ctx.lineTo(startX + envW, lowY);
                        ctx.lineTo(startX, midY);
                        ctx.closePath();

                        if (isX) {{
                            ctx.fillStyle = 'rgba(239, 68, 68, 0.25)';
                            ctx.strokeStyle = '#ef4444';
                        }} else if (isZ) {{
                            ctx.fillStyle = 'rgba(245, 158, 11, 0.15)';
                            ctx.strokeStyle = '#f59e0b';
                        }} else {{
                            ctx.fillStyle = 'rgba(129, 140, 248, 0.12)';
                            ctx.strokeStyle = '#818cf8';
                        }}
                        ctx.lineWidth = 1.4;
                        ctx.fill();
                        ctx.stroke();

                        // Centered text representation
                        if (segW > 24) {{
                            const displayVal = formatBusValue(val, sig.width);
                            ctx.fillStyle = isX ? '#fca5a5' : (isZ ? '#fbbf24' : '#e0e7ff');
                            ctx.font = '10px "JetBrains Mono", monospace';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            const textX = startX + segW / 2;
                            ctx.fillText(displayVal, textX, midY);
                        }}
                    }}
                }} else {{
                    // Draw 1-bit logic signal
                    let lastVal = sig.transitions[0].v;
                    let lastX = 0;

                    for (let i = 0; i < sig.transitions.length; i++) {{
                        const tr = sig.transitions[i];
                        const nextTr = sig.transitions[i + 1];
                        const startX = tr.t * wavePixPerNs;
                        const endX = nextTr ? (nextTr.t * wavePixPerNs) : width;
                        const val = tr.v;
                        const isX = val === 'x' || val === 'X';
                        const isZ = val === 'z' || val === 'Z';
                        const curY = (val === '1') ? highY : lowY;

                        ctx.lineWidth = 1.8;
                        if (isX) {{
                            // X hazard line in red
                            ctx.strokeStyle = '#ef4444';
                            ctx.beginPath();
                            ctx.moveTo(startX, midY);
                            ctx.lineTo(endX, midY);
                            ctx.stroke();
                        }} else if (isZ) {{
                            // Z high-impedance line
                            ctx.strokeStyle = '#f59e0b';
                            ctx.beginPath();
                            ctx.moveTo(startX, midY);
                            ctx.lineTo(endX, midY);
                            ctx.stroke();
                        }} else {{
                            // 0 or 1
                            ctx.strokeStyle = (sig.name.toLowerCase().includes('err')) ? '#ef4444' : '#38bdf8';
                            ctx.beginPath();
                            if (i > 0) {{
                                const prevY = (sig.transitions[i - 1].v === '1') ? highY : lowY;
                                ctx.moveTo(startX, prevY);
                                ctx.lineTo(startX, curY);
                            }} else {{
                                ctx.moveTo(startX, curY);
                            }}
                            ctx.lineTo(endX, curY);
                            ctx.stroke();
                        }}
                    }}
                }}
            }});
        }}

        function formatBusValue(binaryStr, width) {{
            if (!binaryStr) return "0";
            if (binaryStr.includes('x') || binaryStr.includes('X')) return "'hxx";
            if (binaryStr.includes('z') || binaryStr.includes('Z')) return "'hzz";

            if (waveRadix === 'bin') {{
                return binaryStr;
            }} else if (waveRadix === 'dec') {{
                const num = parseInt(binaryStr, 2);
                return isNaN(num) ? binaryStr : num.toString(10);
            }} else {{
                // Hex
                const num = parseInt(binaryStr, 2);
                if (isNaN(num)) return binaryStr;
                const hexDigits = Math.max(1, Math.ceil(width / 4));
                return '0x' + num.toString(16).toUpperCase().padStart(hexDigits, '0');
            }}
        }}

        // Cursor & Measurement Marker Handling
        function handleWaveMouseMove(e) {{
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const timeNs = Math.max(0, mouseX / wavePixPerNs);
            updateCursorPosition(timeNs);
            updateSignalValuesAtCursor(timeNs);
        }}

        function handleWaveClick(e) {{
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            waveCursorTime = Math.max(0, mouseX / wavePixPerNs);
            updateCursorPosition(waveCursorTime);
            updateSignalValuesAtCursor(waveCursorTime);
        }}

        function updateCursorPosition(timeNs) {{
            waveCursorTime = timeNs;
            const x = timeNs * wavePixPerNs;
            const cursorLine = document.getElementById('waveCursorLine');
            const cursorFlag = document.getElementById('waveCursorFlag');
            const readout = document.getElementById('cursorTimeReadout');

            if (cursorLine) cursorLine.style.left = x + 'px';
            if (cursorFlag) cursorFlag.innerText = timeNs.toFixed(1) + ' ns';
            if (readout) readout.innerText = timeNs.toFixed(1) + ' ns';

            // Also place error marker band
            const errBand = document.getElementById('waveErrorBand');
            if (errBand && waveFailureTime !== null) {{
                errBand.style.left = (waveFailureTime * wavePixPerNs) + 'px';
            }}
        }}

        function updateSignalValuesAtCursor(timeNs) {{
            const visibleSignals = getVisibleSignals();
            visibleSignals.forEach((sig, idx) => {{
                const valElem = document.getElementById('sig-val-' + idx);
                if (!valElem) return;

                let curVal = "0";
                for (let i = 0; i < sig.transitions.length; i++) {{
                    if (sig.transitions[i].t <= timeNs) {{
                        curVal = sig.transitions[i].v;
                    }} else {{
                        break;
                    }}
                }}

                valElem.classList.remove('val-x', 'val-z');
                if (curVal.includes('x') || curVal.includes('X')) {{
                    valElem.innerText = 'X';
                    valElem.classList.add('val-x');
                }} else if (curVal.includes('z') || curVal.includes('Z')) {{
                    valElem.innerText = 'Z';
                    valElem.classList.add('val-z');
                }} else if (sig.width > 1) {{
                    valElem.innerText = formatBusValue(curVal, sig.width);
                }} else {{
                    valElem.innerText = curVal;
                }}
            }});
        }}

        // Navigation Controls
        function stepWaveTime(deltaNs) {{
            const newT = Math.max(0, Math.min(waveMaxTime, waveCursorTime + deltaNs));
            updateCursorPosition(newT);
            updateSignalValuesAtCursor(newT);
            scrollToCursor(newT);
        }}

        function jumpWaveTime(targetNs) {{
            updateCursorPosition(targetNs);
            updateSignalValuesAtCursor(targetNs);
            scrollToCursor(targetNs);
        }}

        function jumpToFailure(timeNs) {{
            jumpWaveTime(timeNs);
            const statusBox = document.getElementById('cursorEventReadout');
            if (statusBox) {{
                statusBox.innerHTML = '<span class="pulse-dot"></span> <span class="cur-msg">' + waveFailureLabel + ' @ ' + timeNs + 'ns</span>';
            }}
        }}

        function scrollToCursor(timeNs) {{
            const wrapper = document.getElementById('waveCanvasWrapper');
            if (wrapper) {{
                const targetX = timeNs * wavePixPerNs;
                wrapper.scrollTo({{
                    left: Math.max(0, targetX - wrapper.clientWidth / 2),
                    behavior: 'smooth'
                }});
            }}
        }}

        // Zoom Controls
        function zoomWave(factor) {{
            wavePixPerNs = Math.max(2.0, Math.min(40.0, wavePixPerNs * factor));
            updateCanvasDimensions();
            renderRuler();
            renderWaveforms();
            updateCursorPosition(waveCursorTime);
            scrollToCursor(waveCursorTime);
        }}

        function zoomFitWave() {{
            const wrapper = document.getElementById('waveCanvasWrapper');
            const availableW = wrapper ? (wrapper.clientWidth - 40) : 800;
            wavePixPerNs = Math.max(2.0, availableW / Math.max(waveMaxTime, 1));
            updateCanvasDimensions();
            renderRuler();
            renderWaveforms();
            updateCursorPosition(waveCursorTime);
        }}

        function resetWaveZoom() {{
            wavePixPerNs = 8.0;
            updateCanvasDimensions();
            renderRuler();
            renderWaveforms();
            updateCursorPosition(waveCursorTime);
        }}

        function setWaveRadix(radix) {{
            waveRadix = radix;
            document.querySelectorAll('#radixHex, #radixBin, #radixDec').forEach(b => b.classList.remove('active'));
            const activeBtn = document.getElementById('radix' + radix.charAt(0).toUpperCase() + radix.slice(1));
            if (activeBtn) activeBtn.classList.add('active');
            renderWaveforms();
            updateSignalValuesAtCursor(waveCursorTime);
        }}

        function filterWaveSignals() {{
            waveSearchFilter = document.getElementById('waveSignalSearch').value;
            renderSignalNames();
            updateCanvasDimensions();
            renderWaveforms();
            updateSignalValuesAtCursor(waveCursorTime);
        }}

        function syncWaveScroll(e) {{
            const signalsContainer = document.getElementById('waveSignalRowsContainer');
            if (signalsContainer) {{
                // Can sync vertical scrolling if needed
            }}
        }}

        // File Drag & Drop and Upload
        function handleWaveDragOver(e) {{
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('waveDropTarget').style.borderColor = '#38bdf8';
        }}

        function handleWaveDragLeave(e) {{
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('waveDropTarget').style.borderColor = 'rgba(56, 189, 248, 0.2)';
        }}

        function handleWaveDrop(e) {{
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('waveDropTarget').style.borderColor = 'rgba(56, 189, 248, 0.2)';
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {{
                processUploadedVcdFile(files[0]);
            }}
        }}

        function handleVcdFileSelected(e) {{
            const file = e.target.files[0];
            if (file) processUploadedVcdFile(file);
        }}

        function processUploadedVcdFile(file) {{
            const reader = new FileReader();
            reader.onload = function(e) {{
                const content = e.target.result;
                const parsed = parseClientVcd(content, file.name);
                document.getElementById('waveTraceBadge').innerText = file.name;
                document.getElementById('waveTimescale').innerText = 'Scale: ' + parsed.timescale;
                loadTraceData(parsed);
                jumpWaveTime(0);
                alert('Successfully loaded VCD waveform: ' + file.name + ' (' + parsed.signals.length + ' signals, ' + parsed.max_time + 'ns)');
            }};
            reader.readAsText(file);
        }}

        function updateStatsText() {{
            const stats = document.getElementById('waveStatsText');
            if (stats) {{
                stats.innerText = waveSignals.length + ' Signals • ' + waveMaxTime + 'ns Trace • Click canvas to measure';
            }}
        }}

        function exportWaveformPng() {{
            const canvas = document.getElementById('waveCanvas');
            const link = document.createElement('a');
            link.download = (activeTrace ? activeTrace.name : 'verisight_waveform') + '.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        }}

        // Auto-run on DOM ready
        window.addEventListener('DOMContentLoaded', () => {{
            setTimeout(initWaveformStudio, 150);
        }});
    </script>
    """
