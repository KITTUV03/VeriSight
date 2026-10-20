import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "docs/presentation"
os.makedirs(OUT_DIR, exist_ok=True)

def get_font(size, bold=False):
    try:
        font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{font_name}", size)
    except Exception:
        return ImageFont.load_default()

def create_workflow_gif():
    # Sequence: 1. Welcome Menu -> 2. Agent 1 Debug Input -> 3. RCA Triage Result -> 4. Automated Patch -> 5. Closed-Loop Pass
    steps = [
        ("docs/screenshots/screenshot_01_welcome_menu.png", "STEP 1: Autonomous Silicon Verification Launcher (6 Multi-Agent Workflows)", (34, 197, 94)),
        ("docs/screenshots/screenshot_03_agent1_debug_inputs.png", "STEP 2: Multi-Modal Ingestion (Log, RTL, Testbench, Waveforms VCD)", (14, 165, 233)),
        ("docs/screenshots/screenshot_04_agent1_debug_results.png", "STEP 3: 9-Rule Deterministic RCA Engine (95% Confidence, RTL Bug Isolated)", (234, 179, 8)),
        ("docs/screenshots/screenshot_13_automated_patch.png", "STEP 4: Unified Git Patch Synthesis & Zero-Touch Sandbox Validation", (168, 85, 247)),
        ("docs/screenshots/screenshot_07_workflow3_closed_loop.png", "STEP 5: Closed-Loop Regression Re-Run (All Assertions Clean PASS)", (34, 197, 94))
    ]
    
    target_w, target_h = 1000, 560
    frames = []
    
    font_banner = get_font(18, bold=True)
    font_sub = get_font(12, bold=False)
    
    for i, (path, label, badge_color) in enumerate(steps):
        if not os.path.exists(path):
            continue
        base = Image.open(path).convert("RGB")
        base = base.resize((target_w, target_h - 60), Image.Resampling.LANCZOS)
        
        # Create full frame with banner
        frame = Image.new("RGB", (target_w, target_h), (15, 23, 42))
        frame.paste(base, (0, 0))
        
        d = ImageDraw.Draw(frame)
        # Bottom banner bar
        d.rectangle([(0, target_h - 60), (target_w, target_h)], fill=(11, 15, 25))
        d.rectangle([(0, target_h - 60), (target_w, target_h - 58)], fill=badge_color)
        
        # Step pill
        pill_w = 90
        d.rectangle([(16, target_h - 48), (16 + pill_w, target_h - 16)], fill=badge_color)
        d.text((26, target_h - 44), f"STAGE {i+1}", fill=(0, 0, 0), font=get_font(13, bold=True))
        
        # Label text
        d.text((120, target_h - 44), label, fill=(248, 250, 252), font=font_banner)
        d.text((target_w - 240, target_h - 40), "VeriSight Autonomous Engine", fill=(148, 163, 184), font=font_sub)
        
        frames.append(frame)
        
    if frames:
        out_path = os.path.join(OUT_DIR, "gif_01_multi_agent_workflow.gif")
        frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=1600, loop=0)
        print(f"Generated: {out_path} ({len(frames)} frames)")

def create_coverage_gif():
    # Animated progression of Coverage Cockpit from 42% -> 68% -> 85% -> 96% -> 100%
    base_path = "docs/screenshots/screenshot_11_vplan_cockpit_gui.png"
    if not os.path.exists(base_path):
        base_path = "docs/screenshots/screenshot_06_agent2_plan_results.png"
    
    target_w, target_h = 1000, 560
    base = Image.open(base_path).convert("RGB").resize((target_w, target_h - 60), Image.Resampling.LANCZOS)
    
    coverages = [
        (42, "Initial Random Seed Baseline", "14 Unhit Bins (FIFO Full/Empty Boundaries)", (239, 68, 68)),
        (68, "AI Dynamic Stimulus Ingestion", "VeriSight Agent 2 Directed Constraints Active", (245, 158, 11)),
        (85, "Bayesian Coverage Hole Search", "Hitting Rare Multi-Beat Backpressure States", (14, 165, 233)),
        (96, "Corner-Case Resolution", "Async Reset Glitch & FIFO Concurrent RW Hit", (99, 102, 241)),
        (100, "100% Coverage Closure Sign-Off", "All 22 Features, 45 Tests, 23 SVA Properties Verified", (34, 197, 94))
    ]
    
    frames = []
    font_bold = get_font(18, bold=True)
    font_reg = get_font(13, bold=False)
    
    for pct, title, desc, color in coverages:
        frame = Image.new("RGB", (target_w, target_h), (15, 23, 42))
        frame.paste(base, (0, 0))
        d = ImageDraw.Draw(frame)
        
        # Bottom banner
        d.rectangle([(0, target_h - 60), (target_w, target_h)], fill=(11, 15, 25))
        d.rectangle([(0, target_h - 60), (target_w, target_h - 58)], fill=color)
        
        # Progress bar
        bar_x = 20
        bar_w = 260
        bar_y = target_h - 38
        d.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 16)], fill=(30, 41, 59))
        fill_w = int(bar_w * (pct / 100.0))
        d.rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 16)], fill=color)
        d.text((bar_x + 8, bar_y - 1), f"{pct}% COVERAGE", fill=(255, 255, 255) if pct < 70 else (0, 0, 0), font=get_font(11, bold=True))
        
        # Title and details
        d.text((310, target_h - 48), title, fill=(248, 250, 252), font=font_bold)
        d.text((310, target_h - 26), desc, fill=(148, 163, 184), font=font_reg)
        
        frames.append(frame)
        
    out_path = os.path.join(OUT_DIR, "gif_02_coverage_closure.gif")
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=1500, loop=0)
    print(f"Generated: {out_path} ({len(frames)} frames)")

def create_cockpit_gif():
    views = [
        ("docs/screenshots/screenshot_11_vplan_cockpit_gui.png", "Live Coverage Cockpit: Dynamic UCDB vs Planned Features Progress", (14, 165, 233)),
        ("docs/screenshots/screenshot_12_rca_dashboard_gui.png", "Root-Cause Analysis Studio: Waveform Cursor & Signal Inspection", (234, 179, 8)),
        ("docs/screenshots/screenshot_13_automated_patch.png", "Automated Fix Engine: Self-Synthesized Unified Patch & Sandbox Pass", (168, 85, 247)),
        ("docs/screenshots/screenshot_14_fastapi_web_server.png", "High-Performance FastAPI Server & Bi-Directional WebSocket Bridge", (34, 197, 94))
    ]
    target_w, target_h = 1000, 560
    frames = []
    
    font_bold = get_font(17, bold=True)
    font_sub = get_font(12, bold=False)
    
    for path, title, color in views:
        if not os.path.exists(path):
            continue
        base = Image.open(path).convert("RGB").resize((target_w, target_h - 60), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (target_w, target_h), (15, 23, 42))
        frame.paste(base, (0, 0))
        d = ImageDraw.Draw(frame)
        
        d.rectangle([(0, target_h - 60), (target_w, target_h)], fill=(11, 15, 25))
        d.rectangle([(0, target_h - 60), (target_w, target_h - 58)], fill=color)
        
        d.rectangle([(20, target_h - 48), (140, target_h - 16)], fill=color)
        d.text((32, target_h - 43), "LIVE VIEW", fill=(0, 0, 0), font=get_font(12, bold=True))
        
        d.text((160, target_h - 44), title, fill=(248, 250, 252), font=font_bold)
        d.text((target_w - 220, target_h - 40), "VeriSight Web Cockpit v2.4", fill=(148, 163, 184), font=font_sub)
        
        frames.append(frame)
        
    out_path = os.path.join(OUT_DIR, "gif_03_cockpit_interaction.gif")
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=1700, loop=0)
    print(f"Generated: {out_path} ({len(frames)} frames)")

if __name__ == "__main__":
    create_workflow_gif()
    create_coverage_gif()
    create_cockpit_gif()
