"""
One-page executive decision brief
Standalone HTML with inline SVG charts - works offline and prints to a single PDF page (browser: Print > Save as PDF).
All user and LLM text is HTML-escaped.
"""

from datetime import date
from html import escape
import base64
from typing import Any, Dict, Optional
import re

from src.roi import total_task_hours
from src.template_engine import GATE_NEXT_STEP

GATE_HEX = {"Go": "#2e9e6b", "Pilot with conditions": "#3b82c4", "Fix process first": "#e08a1e", "Stop": "#d64545"}
TIER_HEX = {"Minimal": "#2e9e6b", "Limited": "#3b82c4", "High": "#e08a1e", "Unacceptable": "#d64545"}
SCENARIO_HEX = {"Conservative": "#e08a1e", "Expected": "#3b82c4", "Optimistic": "#2e9e6b"}
GRAY = "#9aa5b1"


# ------------------------------------------------------------------ formatting
def _money(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{'-' if value < 0 else ''}${abs(value):,.0f}"


def _short_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:.0f}k"
    return f"{sign}${v:.0f}"


def _md_to_html(text: str, max_paragraphs: int = 3) -> str:
    """Minimal, safe Markdown: escape first, then bold, bullet lists and paragraphs"""
    text = re.sub(r":material/[a-z_]+:\s*", "", text)
    text = re.sub(r":(?:red|orange|green|blue|violet|gray|grey)\[(.*?)\]", r"\1", text, flags=re.S)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()][:max_paragraphs]
    html = []
    for block in blocks:
        block = escape(block)
        block = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", block)
        lines = block.split("\n")
        if all(line.lstrip().startswith("- ") for line in lines):
            html.append("<ul>" + "".join(f"<li>{line.lstrip()[2:]}</li>" for line in lines) + "</ul>")
        else:
            html.append(f"<p>{'<br>'.join(lines)}</p>")
    return "".join(html)


# ------------------------------------------------------------------ SVG charts
def svg_score_bars(scores: Dict[str, int]) -> str:
    items = [("Value", scores["value"]), ("Feasibility", scores["feasibility"]),
             ("Adoption readiness", scores["adoption_readiness"])]
    left, width, row = 120, 220, 30
    parts = [f'<svg viewBox="0 0 380 {row * 3 + 18}" class="chart" role="img" aria-label="Scores">']
    for i, (label, value) in enumerate(items):
        y = i * row + 4
        color = "#2e9e6b" if value >= 50 else "#e08a1e"
        parts.append(f'<text x="{left - 8}" y="{y + 15}" text-anchor="end" class="lbl">{label}</text>')
        parts.append(f'<rect x="{left}" y="{y + 3}" width="{width}" height="16" rx="3" fill="#eef1f4"/>')
        parts.append(f'<rect x="{left}" y="{y + 3}" width="{width * value / 100:.1f}" height="16" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{left + width + 6}" y="{y + 15}" class="val">{value}</text>')
    threshold_x = left + width * 0.5
    parts.append(f'<line x1="{threshold_x}" y1="2" x2="{threshold_x}" y2="{row * 3 + 4}" stroke="#555" '
                 f'stroke-dasharray="3,3"/>')
    parts.append(f'<text x="{threshold_x}" y="{row * 3 + 16}" text-anchor="middle" class="note">threshold 50</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_cash_flow(roi: Dict[str, Dict[str, Any]], months_ahead: int = 36) -> str:
    """Cumulative net value lines; payback is where a line crosses zero"""
    series = {}
    for name, s in roi.items():
        monthly = (s["annual_benefit"] - s["annual_running_cost"]) / 12
        series[name] = [-s["implementation_cost"] + monthly * m for m in range(months_ahead + 1)]
    values = [v for line in series.values() for v in line] + [0]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    left, top, w, h = 58, 10, 300, 140

    def px(m):
        return left + w * m / months_ahead

    def py(v):
        return top + h * (hi - v) / span

    parts = [f'<svg viewBox="0 0 380 {top + h + 44}" class="chart" role="img" aria-label="Payback">']
    for tick in (hi, (hi + lo) / 2, lo):
        parts.append(f'<text x="{left - 6}" y="{py(tick) + 4:.1f}" text-anchor="end" class="note">{_short_money(tick)}</text>')
    parts.append(f'<line x1="{left}" y1="{py(0):.1f}" x2="{left + w}" y2="{py(0):.1f}" stroke="#555" stroke-width="1"/>')
    for m in range(0, months_ahead + 1, 12):
        parts.append(f'<text x="{px(m):.1f}" y="{top + h + 16}" text-anchor="middle" class="note">{m}</text>')
    parts.append(f'<text x="{left + w / 2}" y="{top + h + 30}" text-anchor="middle" class="note">months after go-live</text>')
    parts.append(f'<text x="{left + w + 4}" y="{py(0) + 3:.1f}" class="note">$0</text>')
    for name, line in series.items():
        points = " ".join(f"{px(m):.1f},{py(v):.1f}" for m, v in enumerate(line))
        width = 3 if name == "Expected" else 2
        parts.append(f'<polyline points="{points}" fill="none" stroke="{SCENARIO_HEX[name]}" stroke-width="{width}"/>')
    payback = roi["Expected"]["payback_months"]
    if payback is not None and payback <= months_ahead:
        x, y = px(payback), py(0)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="{SCENARIO_HEX["Expected"]}" '
                     f'stroke-width="2.5"/>')
        parts.append(f'<text x="{x + 7:.1f}" y="{y + 14:.1f}" class="val">Payback {payback:.1f} mo</text>')
    x = left
    for name in series:
        parts.append(f'<rect x="{x}" y="{top + h + 36}" width="10" height="4" fill="{SCENARIO_HEX[name]}"/>'
                     f'<text x="{x + 14}" y="{top + h + 41}" class="note">{name}</text>')
        x += 100
    parts.append("</svg>")
    return "".join(parts)


def svg_tier_ladder(tier: str) -> str:
    tiers = ["Minimal", "Limited", "High", "Unacceptable"]
    parts = ['<svg viewBox="0 0 380 36" class="chart" role="img" aria-label="Risk tier">']
    for i, t in enumerate(tiers):
        x = i * 95
        current = t == tier
        parts.append(f'<rect x="{x + 1}" y="2" width="91" height="30" rx="4" fill="{TIER_HEX[t]}" '
                     f'opacity="{1 if current else 0.18}"/>')
        parts.append(f'<text x="{x + 46}" y="21" text-anchor="middle" class="{"tier-on" if current else "tier-off"}">{t}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_progress(pct: float, color: str, label: str) -> str:
    return (f'<svg viewBox="0 0 380 34" class="chart" role="img" aria-label="{escape(label)}">'
            f'<rect x="0" y="4" width="300" height="14" rx="3" fill="#eef1f4"/>'
            f'<rect x="0" y="4" width="{3 * max(0.0, min(pct, 100)):.1f}" height="14" rx="3" fill="{color}"/>'
            f'<text x="308" y="16" class="val">{pct:.0f}%</text>'
            f'<text x="0" y="31" class="note">{escape(label)}</text></svg>')


def svg_time_bar(total_hours: float, freed_hours: float) -> str:
    freed = min(freed_hours, total_hours)
    share = freed / total_hours if total_hours else 0
    return (f'<svg viewBox="0 0 380 40" class="chart" role="img" aria-label="Time freed">'
            f'<rect x="0" y="4" width="300" height="16" rx="3" fill="{GRAY}"/>'
            f'<rect x="0" y="4" width="{300 * share:.1f}" height="16" rx="3" fill="#2e9e6b"/>'
            f'<text x="308" y="17" class="val">{share:.0%}</text>'
            f'<text x="0" y="36" class="note">{freed:,.0f} of {total_hours:,.0f} task hours/year freed (Expected)</text>'
            f'</svg>')


# Styles live inside each SVG: charts are embedded as <img> data URIs, which cannot see page CSS
SVG_STYLE = (
    "<style>text{font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif}"
    ".lbl{font-size:11px;fill:#1f2933}.val{font-size:11px;font-weight:700;fill:#1f2933}"
    ".note{font-size:9.5px;fill:#6b7785}.tier-on{font-size:11px;font-weight:700;fill:#ffffff}"
    ".tier-off{font-size:11px;fill:#6b7785}</style>"
)


def chart_img(svg: str, alt: str) -> str:
    """
    Embed an SVG chart as a data-URI image. Streamlit's st.html sanitizer strips inline <svg>
    elements but keeps <img> data URIs, so the same brief renders in the app preview, the
    downloaded file and print.
    """
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    open_end = svg.index(">") + 1
    svg = svg[:open_end] + SVG_STYLE + svg[open_end:]
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="chart" alt="{escape(alt)}" src="data:image/svg+xml;base64,{encoded}">'


# ------------------------------------------------------------------ document
CSS = """
.aan-brief { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2933; background: #ffffff;
  max-width: 880px; margin: 0 auto; padding: 22px 26px; font-size: 12.5px; line-height: 1.45; }
.aan-brief * { box-sizing: border-box; }
.aan-brief .kicker { font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: #6b7785; font-weight: 600; }
.aan-brief h1 { font-size: 24px; margin: 2px 0 2px; color: #111827; }
.aan-brief .meta { color: #6b7785; font-size: 11.5px; }
.aan-brief .verdict { margin: 14px 0 12px; border-radius: 8px; padding: 12px 16px; color: #fff; }
.aan-brief .verdict .gate { font-size: 20px; font-weight: 700; }
.aan-brief .verdict .next { font-size: 13px; margin-top: 2px; }
.aan-brief .verdict ul { margin: 6px 0 0 18px; padding: 0; font-size: 11.5px; }
.aan-brief .kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 12px; }
.aan-brief .kpi { border: 1px solid #e3e7ec; border-radius: 6px; padding: 7px 9px; }
.aan-brief .kpi .k { font-size: 10.5px; color: #6b7785; }
.aan-brief .kpi .v { font-size: 17px; font-weight: 700; color: #111827; }
.aan-brief .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; }
.aan-brief .card { border-top: 3px solid #e3e7ec; padding-top: 6px; }
.aan-brief h2 { font-size: 13.5px; margin: 0 0 6px; color: #111827; }
.aan-brief p { margin: 0 0 6px; }
.aan-brief ul { margin: 0 0 6px 18px; padding: 0; }
.aan-brief .chart { width: 100%; height: auto; display: block; margin: 2px 0 4px; }
.aan-brief .pill { display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 10.5px; font-weight: 600;
  color: #fff; margin-right: 4px; }
.aan-brief .footer { margin-top: 12px; border-top: 1px solid #e3e7ec; padding-top: 6px; font-size: 9.5px; color: #8a94a1; }
.aan-wrap { container-type: inline-size; }
@container (max-width: 640px) {
  .aan-brief .grid { grid-template-columns: 1fr; }
  .aan-brief .kpis { grid-template-columns: repeat(2, 1fr); }
}
@media print { @page { size: A4; margin: 10mm; } body { margin: 0; }
  .aan-brief { padding: 0; max-width: none; -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
"""


def build_brief_html(uc: Dict[str, Any], package: Dict[str, Any],
                     readiness: Optional[Dict[str, Any]] = None, standalone: bool = True) -> str:
    a = package["assessment"]
    gate = a["gate"]["gate"]
    tier = a["governance"]["tier"]
    exp, cons = a["roi"]["Expected"], a["roi"]["Conservative"]
    workforce = a["workforce"]

    conditions = a["gate"]["conditions"][:4]
    conditions_html = ("<ul>" + "".join(f"<li>{escape(c)}</li>" for c in conditions) + "</ul>") if conditions else ""

    critical = [f["flag"] for f in a["governance"]["flags"] if f["severity"] in ("Critical", "High")][:3]
    flags_html = ("<ul>" + "".join(f"<li>{escape(f)}</li>" for f in critical) + "</ul>") if critical \
        else "<p>No critical or high red flags.</p>"

    if readiness and readiness["total"]:
        ready_pct = readiness["readiness_pct"]
        ready_color = "#2e9e6b" if ready_pct >= 100 else "#3b82c4" if ready_pct >= 60 else "#e08a1e"
        readiness_label = (f"Governance readiness: {readiness['done']}/{readiness['total']} controls done"
                           + (f", {readiness['overdue']} overdue" if readiness["overdue"] else ""))
        readiness_svg = chart_img(svg_progress(ready_pct, ready_color, readiness_label), readiness_label)
        ready_kpi = f"{ready_pct:.0f}%"
    else:
        readiness_svg, ready_kpi = "", "n/a"

    meta = " &middot; ".join(escape(x) for x in [
        uc.get("business_unit") or "", f"Sponsor: {uc.get('sponsor')}" if uc.get("sponsor") else "",
        f"Status: {uc.get('status')}", date.today().strftime("%d %b %Y"), package.get("mode", "Template Engine"),
    ] if x)

    body = f"""
<div class="aan-wrap"><div class="aan-brief">
  <div class="kicker">AI use case decision brief</div>
  <h1>{escape(uc['name'])}</h1>
  <div class="meta">{meta}</div>

  <div class="verdict" style="background:{GATE_HEX[gate]}">
    <div class="gate">Decision: {escape(gate)}</div>
    <div class="next">{escape(GATE_NEXT_STEP[gate])}</div>
    {conditions_html}
  </div>

  <div class="kpis">
    <div class="kpi"><div class="k">3-yr net (expected)</div><div class="v">{_money(exp['net_3yr'])}</div></div>
    <div class="kpi"><div class="k">3-yr net (conservative)</div><div class="v">{_money(cons['net_3yr'])}</div></div>
    <div class="kpi"><div class="k">Payback (expected)</div><div class="v">{f"{exp['payback_months']:.1f} mo" if exp['payback_months'] is not None else "None"}</div></div>
    <div class="kpi"><div class="k">Capacity freed</div><div class="v">{exp['fte_equivalent']:.1f} FTE</div></div>
    <div class="kpi"><div class="k">Governance ready</div><div class="v">{ready_kpi}</div></div>
  </div>

  <div class="grid">
    <div class="card"><h2>The case</h2>{_md_to_html(package['sections']['executive_summary'])}</div>
    <div class="card"><h2>Scores</h2>{chart_img(svg_score_bars(a['scores']), "Scores vs the 50-point threshold")}
      <p><span class="pill" style="background:#6b7785">{escape(a['quadrant'])}</span>
      value and feasibility decide the portfolio quadrant; readiness decides whether it can scale.</p></div>

    <div class="card"><h2>When does it pay back?</h2>{chart_img(svg_cash_flow(a['roi']), "Cumulative net value by scenario")}</div>
    <div class="card"><h2>Risk and governance</h2>{chart_img(svg_tier_ladder(tier), f"Risk tier: {tier}")}
      <p style="margin-top:6px">{escape('; '.join(a['governance']['tier_reasons']))}</p>
      {readiness_svg}{flags_html}</div>

    <div class="card"><h2>People</h2>
      <p><span class="pill" style="background:#6b7785">{escape(workforce['category'])}</span>{escape(workforce['meaning'])}</p>
      {chart_img(svg_time_bar(total_task_hours(uc), exp['annual_hours_saved']), "Task hours freed by AI")}
      <p>Roles affected: {escape(', '.join(workforce['roles']) or 'not specified')}. Decide where freed capacity goes before go-live.</p></div>
    <div class="card"><h2>Pilot: 90 days, then decide</h2>
      <p><strong>Success metric:</strong> {escape(uc.get('success_metric') or 'Not defined yet')}</p>
      <p><strong>Stop if at day 90:</strong></p>
      <ul><li>Quality below the agreed threshold after two improvement cycles</li>
      <li>Adoption below 40% of pilot users despite training</li>
      <li>Realized hours below 40% of plan</li><li>A governance control cannot be met</li></ul></div>
  </div>

  <div class="footer">Generated with AI Adoption Navigator. Scores, ROI, risk tier and decision are calculated by
  transparent rules; AI (if used) adds narrative only. Risk tiers are inspired by the EU AI Act and NIST AI RMF and are
  not legal advice.</div>
</div></div>"""

    if not standalone:
        return f"<style>{CSS}</style>{body}"
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Decision brief - {escape(uc["name"])}</title><style>body{{background:#f3f5f7;margin:0;padding:16px}}'
            f'@media print{{body{{background:#fff;padding:0}}}}{CSS}</style></head><body>{body}</body></html>')
