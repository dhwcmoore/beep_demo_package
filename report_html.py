"""
report_html.py — generates beep_report.html from beep_output.json
"""
import json
from pathlib import Path

LEVEL_COLORS = {
    "LOW":      ("#1a9e5c", "#e8f5ee"),
    "MEDIUM":   ("#d4920a", "#fdf6e3"),
    "HIGH":     ("#c0550a", "#fdf0e3"),
    "CRITICAL": ("#b01414", "#fdeaea"),
}

INTERPRETATIONS = {
    "LOW":      "All signals are within normal bounds. Cluster load is nominal and topology "
                "is intact. No structural anomaly detected.",
    "MEDIUM":   "Early warning: load or topology signals are drifting outside their certified "
                "baseline. The cluster is behaving outside normal operating bounds. "
                "Monitor closely and prepare contingency.",
    "HIGH":     "Elevated risk: temporal load instability and topological deviation are both "
                "present. The cluster is in a stressed state — ring integrity or connectivity "
                "is degraded. Mitigation should be prepared now.",
    "CRITICAL": "Both signals are firing simultaneously: the rupture engine has confirmed a "
                "load regime shift, and the boundary engine has detected a topological "
                "invariant violation in the cluster. "
                "The structural break was detected before it became operationally visible — "
                "the candidate was raised at the end of the calm phase and confirmed at the "
                "onset of the stress regime. Both the temporal load signal and the structural "
                "topology of the cluster are in agreement: this is a genuine structural failure.",
}

def severity_badge(severity: str) -> str:
    color = "#b01414" if severity == "CRITICAL" else "#d4920a"
    return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:3px;font-size:0.85em;font-weight:bold;">{severity}</span>')

def phase_timeline(meta: dict) -> str:
    """Render a phase boundary timeline from scenario metadata."""
    if not meta:
        return ""

    p1_ts = meta.get("phase1_ts", "—")
    p2_ts = meta.get("phase2_ts", "—")
    p3_ts = meta.get("phase3_ts", "—")

    return f"""
  <div class="section">
    <h2>Scenario Phases</h2>
    <div class="phase-timeline">
      <div class="phase calm">
        <div class="phase-label">Phase 1 — Calm</div>
        <div class="phase-detail">from {p1_ts}</div>
        <div class="phase-note">Nominal operation. No confirmed alarms.</div>
      </div>
      <div class="phase-arrow">→</div>
      <div class="phase stress">
        <div class="phase-label">Phase 2 — Stress onset</div>
        <div class="phase-detail">from {p2_ts}</div>
        <div class="phase-note">Rupture confirmed here. Structural break detected.</div>
      </div>
      <div class="phase-arrow">→</div>
      <div class="phase collapse">
        <div class="phase-label">Phase 3 — Collapse</div>
        <div class="phase-detail">from {p3_ts}</div>
        <div class="phase-note">Continued deterioration after confirmed break.</div>
      </div>
    </div>
  </div>"""

def render(data: dict) -> str:
    level   = data["risk_level"]
    score   = data["risk_score"]
    r_score = data["signals"]["rupture_score"]
    i_score = data["signals"]["invariant_score"]
    advisories    = data["signals"]["invariants"].get("advisories", [])
    stages        = data["signals"]["invariants"].get("stages", [])
    rupture_events = data["signals"]["rupture"].get("raw", [])
    meta          = data["signals"]["rupture"].get("scenario_meta", {})

    fg, bg = LEVEL_COLORS.get(level, ("#333", "#f9f9f9"))
    interpretation = INTERPRETATIONS.get(level, "")

    seen = set()
    unique_advisories = []
    for adv in advisories:
        key = (adv["severity"], adv["code"])
        if key not in seen:
            seen.add(key)
            unique_advisories.append(adv)

    advisory_rows = ""
    for adv in unique_advisories:
        advisory_rows += f"""
        <tr>
          <td>{severity_badge(adv['severity'])}</td>
          <td style="font-family:monospace;">{adv['code']}</td>
        </tr>"""

    stage_rows = ""
    for s in stages:
        stage_rows += f"""
        <tr>
          <td>{s.get('stage','—')}</td>
          <td style="font-family:monospace;">{s.get('system','—')}</td>
          <td style="text-align:center;">{s['b0']}</td>
          <td style="text-align:center;">{s['b1']}</td>
        </tr>"""

    rupture_rows = ""
    for ev in rupture_events:
        cand  = ev.get("candidate_timestamp", "—")
        conf  = ev.get("confirmed_timestamp", "—")
        rho   = ev.get("peak_rho", 0.0)
        lag   = ev.get("confirmation_k", "?")
        note  = ("Early warning raised at end of calm phase; confirmed at stress onset."
                 if conf and meta.get("phase2_ts") and conf >= meta.get("phase2_ts", "")
                 else "")
        note_html = f'<br><span style="color:#888;font-size:0.85em;">{note}</span>' if note else ""
        rupture_rows += f"""
        <tr>
          <td>{cand}{note_html}</td>
          <td>{conf}</td>
          <td style="text-align:right;">{rho:.4f}</td>
          <td style="text-align:right;">{lag}</td>
        </tr>"""

    timeline_html = phase_timeline(meta)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Beep Before Bang — Risk Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f4f4; margin: 0; padding: 0; color: #222; }}
    .container {{ max-width: 860px; margin: 40px auto; background: #fff;
                  border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.10);
                  overflow: hidden; }}
    .header {{ background: {fg}; color: #fff; padding: 32px 40px 24px; }}
    .header h1 {{ margin: 0 0 4px; font-size: 1.6em; letter-spacing: 0.02em; }}
    .header .subtitle {{ opacity: 0.85; font-size: 0.95em; }}
    .risk-banner {{ background: {bg}; border-left: 6px solid {fg};
                    padding: 20px 40px; display: flex; align-items: center; gap: 32px; }}
    .risk-level {{ font-size: 2.4em; font-weight: 800; color: {fg}; }}
    .risk-score {{ font-size: 1.1em; color: #555; }}
    .risk-score span {{ font-size: 1.5em; font-weight: 700; color: {fg}; }}
    .section {{ padding: 24px 40px; border-top: 1px solid #eee; }}
    .section h2 {{ font-size: 1.05em; text-transform: uppercase;
                   letter-spacing: 0.08em; color: #666; margin: 0 0 14px; }}
    .scores {{ display: flex; gap: 32px; }}
    .score-box {{ background: #f8f8f8; border-radius: 6px; padding: 16px 24px;
                  flex: 1; text-align: center; }}
    .score-box .label {{ font-size: 0.8em; color: #888; text-transform: uppercase;
                          letter-spacing: 0.05em; margin-bottom: 6px; }}
    .score-box .value {{ font-size: 2em; font-weight: 700; color: #333; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
    th {{ text-align: left; padding: 8px 10px; background: #f0f0f0;
          font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
    .interp {{ background: {bg}; border-radius: 6px; padding: 16px 20px;
                font-size: 0.95em; line-height: 1.6; color: #333;
                border-left: 4px solid {fg}; }}
    .phase-timeline {{ display: flex; align-items: stretch; gap: 0; margin-top: 4px; }}
    .phase {{ flex: 1; padding: 14px 16px; border-radius: 6px; font-size: 0.9em; }}
    .phase.calm    {{ background: #e8f5ee; border-left: 4px solid #1a9e5c; }}
    .phase.stress  {{ background: #fdf6e3; border-left: 4px solid #d4920a; }}
    .phase.collapse {{ background: #fdeaea; border-left: 4px solid #b01414; }}
    .phase-label {{ font-weight: 700; margin-bottom: 3px; }}
    .phase-detail {{ font-family: monospace; font-size: 0.85em; color: #555; margin-bottom: 4px; }}
    .phase-note {{ font-size: 0.82em; color: #666; }}
    .phase-arrow {{ display: flex; align-items: center; padding: 0 8px;
                    color: #aaa; font-size: 1.4em; }}
    .footer {{ padding: 16px 40px; background: #f8f8f8; font-size: 0.8em; color: #999;
               border-top: 1px solid #eee; }}
  </style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Beep Before Bang</h1>
    <div class="subtitle">4-Node Compute Cluster — Structural Early Warning Report</div>
  </div>

  <div class="risk-banner">
    <div class="risk-level">{level}</div>
    <div class="risk-score">
      Composite risk score<br>
      <span>{score}</span> / 10.0
    </div>
  </div>

  <div class="section">
    <h2>Signal Scores</h2>
    <div class="scores">
      <div class="score-box">
        <div class="label">Rupture Score</div>
        <div class="value">{r_score}</div>
      </div>
      <div class="score-box">
        <div class="label">Invariant Score</div>
        <div class="value">{i_score}</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Interpretation</h2>
    <div class="interp">{interpretation}</div>
  </div>

  {timeline_html}

  <div class="section">
    <h2>Rupture Events</h2>
    <table>
      <tr>
        <th>Candidate raised</th>
        <th>Confirmed</th>
        <th style="text-align:right;">Peak ρ</th>
        <th style="text-align:right;">Confirm lag</th>
      </tr>
      {rupture_rows if rupture_rows else '<tr><td colspan="4" style="color:#999;">No confirmed events</td></tr>'}
    </table>
  </div>

  <div class="section">
    <h2>Detected Issues — Cluster Topology (Invariant Engine)</h2>
    <table>
      <tr><th>Severity</th><th>Code</th></tr>
      {advisory_rows if advisory_rows else '<tr><td colspan="2" style="color:#999;">No advisories</td></tr>'}
    </table>
  </div>

  <div class="section">
    <h2>Topology Stages</h2>
    <table>
      <tr><th>Stage</th><th>System</th><th style="text-align:center;">b₀</th><th style="text-align:center;">b₁</th></tr>
      {stage_rows if stage_rows else '<tr><td colspan="4" style="color:#999;">No stage data</td></tr>'}
    </table>
  </div>

  <div class="footer">
    Generated by Beep Before Bang pipeline &nbsp;·&nbsp; beep_output.json
  </div>

</div>
</body>
</html>
"""

if __name__ == "__main__":
    src = Path("output/beep_output.json")
    if not src.exists():
        raise FileNotFoundError("output/beep_output.json not found — run beep_pipeline.py first")

    with open(src) as f:
        data = json.load(f)

    html = render(data)

    out = Path("output/beep_report.html")
    out.write_text(html, encoding="utf-8")
    print(f"Report written to {out.resolve()}")
