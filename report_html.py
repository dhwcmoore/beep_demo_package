import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SEALED_PATH = OUTPUT_DIR / "beep_output_sealed.json"
RAW_PATH = OUTPUT_DIR / "beep_output.json"
OUTPUT = PROJECT_ROOT / "beep_report.html"


def load_report_input() -> tuple[dict, dict | None]:
    """
    Returns:
      payload, sealed_envelope_or_none
    """
    if SEALED_PATH.exists():
        with SEALED_PATH.open("r", encoding="utf-8") as f:
            sealed = json.load(f)

        payload = sealed.get("payload", {})
        return payload, sealed

    if RAW_PATH.exists():
        with RAW_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload, None

    raise FileNotFoundError(
        f"Neither sealed nor raw BEEP output was found in {OUTPUT_DIR}"
    )


def load():
    payload, _ = load_report_input()
    return payload


def render_integrity_section(sealed: dict | None) -> str:
    if not sealed:
        return """
        <section>
          <h2>Integrity</h2>
          <p><strong>Status:</strong> Unsealed raw artefact</p>
          <p><strong>Seal:</strong> Not present</p>
        </section>
        """

    integrity = sealed.get("integrity", {})
    verification = sealed.get("verification", {})

    payload_hash = integrity.get("payload_sha256", "unknown")
    seal_type = integrity.get("seal_type", "unknown")
    seal_version = integrity.get("seal_version", "unknown")
    verified = verification.get("verified_at_seal_time", False)

    verified_text = "valid" if verified else "invalid"

    return f"""
    <section>
      <h2>Integrity</h2>
      <p><strong>Status:</strong> {verified_text}</p>
      <p><strong>Seal type:</strong> {seal_type}</p>
      <p><strong>Seal version:</strong> {seal_version}</p>
      <p><strong>Payload SHA-256:</strong> <code>{payload_hash}</code></p>
    </section>
    """


def render():
    d, sealed = load_report_input()

    risk_level = d["risk_level"]
    risk_score = d["risk_score"]
    rupture = d["signals"]["rupture"]
    invariants = d["signals"]["invariants"]

    rupture_features = d.get("rupture_features", {})
    rupture_semantics_version = d.get("rupture_semantics_version", "v1")
    semantic_contracts = d.get("semantic_contracts", {})
    rupture_contract = semantic_contracts.get("rupture_contract", "rupture_contract.v")
    audit_envelope = d.get("audit_envelope", {})
    structural_inputs = d.get("structural_inputs", {})
    structural_judgement = invariants.get("structural_judgement", "SJ_NoBreak")
    structural_judgement_source = semantic_contracts.get("structural_judgement_source", invariants.get("structural_judgement_source", d.get("structural_judgement_source", "ocaml")))
    structural_semantics_version = semantic_contracts.get("structural_semantics_version", d.get("structural_semantics_version", "v1"))
    structural_contract = semantic_contracts.get("structural_contract", "structural_judgement_contract.v")
    risk_contract = semantic_contracts.get("risk_contract", "risk_escalation_contract.v")
    guardrails_enforced = semantic_contracts.get("guardrails_enforced", True)
    structural_meanings = {
        "SJ_NoBreak": "No structural break detected.",
        "SJ_CycleLoss": "System remains connected but has lost ring redundancy.",
        "SJ_ConnectivityPartition": "System has become partitioned; connectivity has been disrupted.",
    }
    structural_meaning = structural_meanings.get(structural_judgement, "Structural judgement produced by OCaml bridge.")

    events = rupture.get("classified_events", [])
    detection_start = rupture.get("detection_start_index")

    # Risk level color
    risk_colors = {
        "LOW": "#28a745",
        "MEDIUM": "#ffc107",
        "HIGH": "#fd7e14",
        "CRITICAL": "#dc3545"
    }
    risk_color = risk_colors.get(risk_level, "#6c757d")

    # Risk interpretation
    interpretations = {
        "LOW": "The system is operating normally with no significant issues detected.",
        "MEDIUM": "Some irregularities detected. Monitor the system closely.",
        "HIGH": "Elevated risk of structural failure. Prepare mitigation measures.",
        "CRITICAL": "Immediate risk of system failure. Take corrective action now."
    }
    interpretation = interpretations.get(risk_level, "Risk assessment completed.")

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Beep Before Bang — Risk Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            color: #212529;
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        header p {{
            margin: 10px 0 0;
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .risk-summary {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }}
        .risk-score {{
            font-size: 4em;
            font-weight: bold;
            color: {risk_color};
            margin: 10px 0;
        }}
        .risk-level {{
            font-size: 1.5em;
            color: {risk_color};
            margin-bottom: 20px;
        }}
        .interpretation {{
            background: #e9ecef;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid {risk_color};
            margin-top: 20px;
        }}
        .section {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #495057;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .alert-list {{
            list-style: none;
            padding: 0;
        }}
        .alert-list li {{
            background: #f8d7da;
            color: #721c24;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 5px solid #dc3545;
        }}
        .glossary {{
            background: #d1ecf1;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .glossary h3 {{
            margin-top: 0;
            color: #0c5460;
        }}
        .glossary dl {{
            margin: 0;
        }}
        .glossary dt {{
            font-weight: bold;
            color: #0c5460;
        }}
        .glossary dd {{
            margin-bottom: 10px;
        }}
        footer {{
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9em;
        }}
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            header {{
                padding: 20px 10px;
            }}
            header h1 {{
                font-size: 2em;
            }}
            .risk-score {{
                font-size: 3em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Beep Before Bang</h1>
            <p>Early Warning System for Structural Risk Assessment</p>
        </header>

        <section class="risk-summary">
            <h2>Overall Risk Assessment</h2>
            <div class="risk-score">{risk_score:.1f}</div>
            <div class="risk-level">{risk_level} Risk</div>
            <p>Composite risk score out of 10.0</p>
            <div class="interpretation">
                <strong>What this means:</strong> {interpretation}
            </div>
        </section>

        <section class="section">
            <h2>Detection Details</h2>
            <p>The system monitors two independent signals: temporal ruptures (changes in behavior patterns) and structural invariants (topology integrity).</p>
            <p><strong>Detection started at index:</strong> {detection_start or 'Automatic'}</p>
        </section>

        <section class="section">
            <h2>Rupture Events</h2>
            <p>Detected changes in system behavior patterns. These indicate when the system's operation deviates from its normal baseline.</p>
            <table>
                <thead>
                    <tr>
                        <th>Classification</th>
                        <th>Data Point</th>
                        <th>Severity (ρ)</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f"<tr><td>{e.get('classification', 'Unknown')}</td><td>{e.get('candidate_index', 'N/A')}</td><td>{e.get('peak_rho', 0):.2f}</td></tr>" for e in events)}
                </tbody>
            </table>
        </section>

        <section class="section">
            <h2>Structural Alerts</h2>
            <p>Violations of the system's certified structural design. These indicate physical or logical connectivity issues.</p>
            <ul class="alert-list">
                {''.join(f"<li>{a.get('code', 'Unknown Alert')}</li>" for a in invariants.get('advisories', []))}
            </ul>
        </section>

        <section class="section">
            <h2>Structural Judgement</h2>
            <p><strong>Source:</strong> {structural_judgement_source}</p>
            <p><strong>Version:</strong> {structural_semantics_version}</p>
            <p><strong>Result:</strong> {structural_judgement}</p>
            <p><strong>Meaning:</strong> {structural_meaning}</p>
        </section>

        <section class="section">
            <h2>Classifier Inputs</h2>
            <p><strong>Nominal b0:</strong> {structural_inputs.get('nominal_b0', 'N/A')}</p>
            <p><strong>Nominal b1:</strong> {structural_inputs.get('nominal_b1', 'N/A')}</p>
            <p><strong>Fault b0:</strong> {structural_inputs.get('fault_b0', 'N/A')}</p>
            <p><strong>Fault b1:</strong> {structural_inputs.get('fault_b1', 'N/A')}</p>
        </section>

        <section class="section">
            <h2>Rupture Features</h2>
            <p><strong>Event Count:</strong> {rupture_features.get('event_count', 'N/A')}</p>
            <p><strong>Filtered Event Count:</strong> {rupture_features.get('filtered_event_count', 'N/A')}</p>
            <p><strong>Max Peak Rho:</strong> {rupture_features.get('max_peak_rho', 'N/A')}</p>
            <p><strong>Phase Threshold:</strong> {rupture_features.get('phase_threshold', 'N/A')}</p>
        </section>

        <section class="section">
            <h2>Semantic Contracts</h2>
            <p><strong>Structural contract:</strong> {structural_contract}</p>
            <p><strong>Rupture contract:</strong> {rupture_contract}</p>
            <p><strong>Risk escalation contract:</strong> {risk_contract}</p>
            <p><strong>Guardrails enforced:</strong> {"Yes" if guardrails_enforced else "No"}</p>
        </section>

        {render_integrity_section(sealed)}

        <section class="section glossary">
            <h3>Understanding the Terms</h3>
            <dl>
                <dt>Rupture Score</dt>
                <dd>Measures how much the system's behavior has changed from normal patterns. Higher scores indicate more significant deviations.</dd>
                <dt>Invariant Score</dt>
                <dd>Checks if the system's structure matches its designed topology. Violations suggest connectivity or integrity problems.</dd>
                <dt>Risk Levels</dt>
                <dd>LOW (0-2): Normal operation. MEDIUM (2-4): Monitor closely. HIGH (4-7): Prepare action. CRITICAL (7-10): Act immediately.</dd>
            </dl>
        </section>

        <footer>
            <p>Report generated by Beep Before Bang system. For technical details, see beep_output.json.</p>
        </footer>
    </div>
</body>
</html>
"""

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(html)

    print("✔ Professional report generated:", OUTPUT)

if __name__ == "__main__":
    render()
