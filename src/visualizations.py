"""
Altair charts (ships with Streamlit - no extra dependency)
"""

from typing import Any, Dict, List

import altair as alt
import pandas as pd


TIER_COLORS = alt.Scale(
    domain=["Minimal", "Limited", "High", "Unacceptable"],
    range=["#2e9e6b", "#3b82c4", "#e08a1e", "#d64545"],
)


def portfolio_matrix(df: pd.DataFrame) -> alt.LayerChart:
    """Value vs feasibility bubble matrix: size = expected 3-yr net value, color = risk tier"""
    data = df.assign(bubble=df["3-yr net (expected)"].clip(lower=0))
    base = alt.Chart(data)
    points = base.mark_circle(opacity=0.75, stroke="white", strokeWidth=1).encode(
        x=alt.X("Feasibility:Q", scale=alt.Scale(domain=[0, 100]), title="Feasibility"),
        y=alt.Y("Value:Q", scale=alt.Scale(domain=[0, 100]), title="Value"),
        size=alt.Size("bubble:Q", title="3-yr net (expected)", scale=alt.Scale(range=[150, 2000]), legend=None),
        color=alt.Color("Risk tier:N", scale=TIER_COLORS),
        tooltip=["Use case", "Quadrant", "Risk tier", "Decision",
                 alt.Tooltip("3-yr net (expected):Q", format="$,.0f"), "Value", "Feasibility"],
    )
    # Mid-gray reads on both light and dark themes (default black disappears in dark mode)
    labels = base.mark_text(align="left", dx=16, fontSize=11, color="#9aa5b1").encode(
        x="Feasibility:Q", y="Value:Q", text="Use case:N")
    rules = alt.Chart(pd.DataFrame({"v": [50]})).mark_rule(strokeDash=[4, 4], color="gray")
    def quadrant_labels(rows, align):
        return alt.Chart(pd.DataFrame(rows)).mark_text(
            color="gray", fontStyle="italic", align=align).encode(x="x:Q", y="y:Q", text="t:N")

    right = quadrant_labels([{"x": 98, "y": 97, "t": "Quick Win"}, {"x": 98, "y": 3, "t": "Fill-in"}], "right")
    left = quadrant_labels([{"x": 2, "y": 97, "t": "Strategic Bet"}, {"x": 2, "y": 3, "t": "Avoid"}], "left")
    return (rules.encode(x="v:Q") + rules.encode(y="v:Q") + points + labels + right + left).properties(height=460)


GATE_SCALE = alt.Scale(
    domain=["Go", "Pilot with conditions", "Fix process first", "Stop"],
    range=["#2e9e6b", "#3b82c4", "#e08a1e", "#d64545"],
)
SCENARIO_SCALE = alt.Scale(domain=["Conservative", "Expected", "Optimistic"],
                           range=["#e08a1e", "#3b82c4", "#2e9e6b"])
PASS_THRESHOLD = 50


def score_bars(scores: Dict[str, int]) -> alt.LayerChart:
    """Three scores as bars against the 50-point threshold used by the quadrant and gate"""
    data = pd.DataFrame([
        {"Score": "Value", "Points": scores["value"]},
        {"Score": "Feasibility", "Points": scores["feasibility"]},
        {"Score": "Adoption readiness", "Points": scores["adoption_readiness"]},
    ])
    data["Status"] = data["Points"].apply(lambda p: "Above threshold" if p >= PASS_THRESHOLD else "Below threshold")
    order = list(data["Score"])
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Points:Q", scale=alt.Scale(domain=[0, 100]), title=None),
        y=alt.Y("Score:N", sort=order, title=None),
        color=alt.Color("Status:N", scale=alt.Scale(domain=["Above threshold", "Below threshold"],
                                                    range=["#2e9e6b", "#e08a1e"]),
                        legend=None),
        tooltip=["Score", "Points", "Status"],
    )
    text = bars.mark_text(align="left", dx=6).encode(text="Points:Q", color=alt.value("gray"))
    threshold = alt.Chart(pd.DataFrame({"x": [PASS_THRESHOLD]})).mark_rule(
        strokeDash=[4, 4], color="gray").encode(x="x:Q")
    return (bars + text + threshold).properties(height=150)


def cash_flow_chart(rows: List[Dict[str, Any]]) -> alt.LayerChart:
    """Cumulative net value over 36 months: where each line crosses zero is the payback month"""
    data = pd.DataFrame(rows)
    lines = alt.Chart(data).mark_line(strokeWidth=2.5).encode(
        x=alt.X("Month:Q", title="Months after go-live", scale=alt.Scale(domain=[0, 36]),
                axis=alt.Axis(values=list(range(0, 37, 6)))),
        y=alt.Y("Cumulative net value:Q", axis=alt.Axis(format="$,.0f"), title=None),
        color=alt.Color("Scenario:N", scale=SCENARIO_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Scenario", "Month", alt.Tooltip("Cumulative net value:Q", format="$,.0f")],
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="gray").encode(y="y:Q")
    return (zero + lines).properties(height=300)


def time_freed_chart(total_hours: float, roi: Dict[str, Dict[str, Any]]) -> alt.Chart:
    """Annual task hours today, split into time AI frees vs work that remains, per scenario"""
    rows = [{"Scenario": "Today", "Part": "Work that remains", "Hours": total_hours, "order": 1}]
    for name, s in roi.items():
        freed = min(s["annual_hours_saved"], total_hours)
        rows.append({"Scenario": name, "Part": "Time freed by AI", "Hours": freed, "order": 0})
        rows.append({"Scenario": name, "Part": "Work that remains", "Hours": total_hours - freed, "order": 1})
    return alt.Chart(pd.DataFrame(rows)).mark_bar().encode(
        y=alt.Y("Scenario:N", sort=["Today", *roi.keys()], title=None),
        x=alt.X("Hours:Q", stack="zero", title="Hours per year", axis=alt.Axis(format=",.0f")),
        color=alt.Color("Part:N", scale=alt.Scale(domain=["Time freed by AI", "Work that remains"],
                                                  range=["#2e9e6b", "#9aa5b1"]),
                        legend=alt.Legend(orient="bottom", title=None)),
        order=alt.Order("order:Q"),
        tooltip=["Scenario", "Part", alt.Tooltip("Hours:Q", format=",.0f")],
    ).properties(height=230)


def tier_ladder(current_tier: str) -> alt.LayerChart:
    """The four risk tiers side by side, with the current one highlighted"""
    tiers = ["Minimal", "Limited", "High", "Unacceptable"]
    data = pd.DataFrame({"Tier": tiers, "Current": [t == current_tier for t in tiers]})
    base = alt.Chart(data).encode(x=alt.X("Tier:N", sort=tiers, axis=None))
    boxes = base.mark_bar(size=110, cornerRadius=4).encode(
        y=alt.value(0), y2=alt.value(56),
        color=alt.Color("Tier:N", scale=TIER_COLORS, legend=None),
        opacity=alt.condition("datum.Current", alt.value(1.0), alt.value(0.18)),
    )
    labels = base.mark_text(fontSize=13, fontWeight="bold", y=28).encode(
        text="Tier:N", color=alt.condition("datum.Current", alt.value("white"), alt.value("gray")))
    return (boxes + labels).properties(height=60)


EVIDENCE_SCALE = alt.Scale(domain=["Done", "In progress", "Not started", "Not applicable"],
                           range=["#2e9e6b", "#3b82c4", "#d64545", "#9aa5b1"])


def governance_readiness_chart(by_function: List[Dict[str, Any]]) -> alt.Chart:
    """Control status per NIST AI RMF function"""
    order = {"Done": 0, "In progress": 1, "Not started": 2, "Not applicable": 3}
    data = pd.DataFrame(by_function).assign(order=lambda d: d["status"].map(order))
    return alt.Chart(data).mark_bar().encode(
        y=alt.Y("function:N", sort=["Govern", "Map", "Measure", "Manage"], title=None),
        x=alt.X("count:Q", stack="zero", title="Controls", axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("status:N", scale=EVIDENCE_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        order=alt.Order("order:Q"),
        tooltip=[alt.Tooltip("function:N", title="Function"), alt.Tooltip("status:N", title="Status"),
                 alt.Tooltip("count:Q", title="Controls")],
    ).properties(height=alt.Step(34))  # fixed row height so every function label stays visible


def pilot_timeline() -> alt.LayerChart:
    """30/60/90-day pilot phases with the decision point at day 90"""
    phases = pd.DataFrame([
        {"Phase": "1. Baseline & setup", "start": 0, "end": 30},
        {"Phase": "2. Run with human review", "start": 30, "end": 60},
        {"Phase": "3. Measure & decide", "start": 60, "end": 90},
    ])
    bars = alt.Chart(phases).mark_bar(cornerRadius=4).encode(
        x=alt.X("start:Q", title="Day", scale=alt.Scale(domain=[0, 95]), axis=alt.Axis(values=[0, 30, 60, 90])),
        x2="end:Q",
        y=alt.Y("Phase:N", sort=list(phases["Phase"]), title=None),
        color=alt.Color("Phase:N", scale=alt.Scale(range=["#9aa5b1", "#3b82c4", "#2e9e6b"]), legend=None),
    )
    decision = alt.Chart(pd.DataFrame({"x": [90], "label": ["Scale / stop decision"]}))
    rule = decision.mark_rule(color="#d64545", strokeWidth=2).encode(x="x:Q")
    label = decision.mark_text(align="right", baseline="top", dx=-6, color="#d64545", fontWeight="bold").encode(
        x="x:Q", y=alt.value(2), text="label:N")
    return (bars + rule + label).properties(height=210)


def decision_chart(df: pd.DataFrame) -> alt.Chart:
    """Number of use cases and expected 3-yr value per decision"""
    summary = df.groupby("Decision", as_index=False).agg(
        Count=("Use case", "count"), Value=("3-yr net (expected)", "sum"), Names=("Use case", ", ".join))
    order = ["Go", "Pilot with conditions", "Fix process first", "Stop"]
    bars = alt.Chart(summary).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Decision:N", sort=order, title=None),
        x=alt.X("Count:Q", title="Use cases", axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Decision:N", scale=GATE_SCALE, legend=None),
        tooltip=["Decision", "Count", "Names", alt.Tooltip("Value:Q", title="Expected 3-yr net", format="$,.0f")],
    )
    # Names stay in the tooltip - long text labels would squeeze the bars in a narrow column
    text = bars.mark_text(align="left", dx=6, color="gray").encode(text="Count:Q")
    return (bars + text).properties(height=200)


def portfolio_realization_chart(data: pd.DataFrame) -> alt.LayerChart:
    """Realization % of promised hours for every tracked use case, with Watch (70%) and On track (90%) lines"""
    status_scale = alt.Scale(domain=["On track", "Watch", "Value leakage", "Critical leakage", "Too early"],
                             range=["#2e9e6b", "#3b82c4", "#e08a1e", "#d64545", "#9aa5b1"])
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Use case:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X("Realization %:Q", title="% of promised hours saved",
                scale=alt.Scale(domain=[0, max(120, float(data["Realization %"].max()) + 10)])),
        color=alt.Color("Status:N", scale=status_scale, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Use case", "Status", alt.Tooltip("Realization %:Q", format=".0f"), "Months tracked"],
    )
    rules = alt.Chart(pd.DataFrame({"x": [70, 90]})).mark_rule(strokeDash=[4, 4], color="gray").encode(x="x:Q")
    return (bars + rules).properties(height=alt.Step(34))  # fixed row height keeps bars and labels readable


def cumulative_value_chart(df: pd.DataFrame, hourly_cost: float, monthly_running_cost: float) -> alt.LayerChart:
    """Cumulative promised vs realized net value - the gap between the lines is the value leakage"""
    data = df.sort_values("month").copy()
    data["Promised"] = (data["promised_hours"] * hourly_cost - monthly_running_cost).cumsum()
    data["Realized"] = (data["hours_saved"] * hourly_cost - data["actual_cost"]).cumsum()
    long = data.melt(id_vars="month", value_vars=["Promised", "Realized"], var_name="Series", value_name="Value")
    area = alt.Chart(data).mark_area(opacity=0.15, color="#d64545").encode(
        x="month:O", y="Realized:Q", y2="Promised:Q")
    lines = alt.Chart(long).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("month:O", title="Month", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Value:Q", axis=alt.Axis(format="$,.0f"), title="Cumulative net value"),
        color=alt.Color("Series:N", scale=alt.Scale(domain=["Promised", "Realized"], range=["#9aa5b1", "#2e9e6b"]),
                        legend=alt.Legend(orient="bottom", title=None)),
        strokeDash=alt.condition("datum.Series == 'Promised'", alt.value([5, 4]), alt.value([1, 0])),
        tooltip=["month", "Series", alt.Tooltip("Value:Q", format="$,.0f")],
    )
    return (area + lines).properties(height=300)


def adoption_chart(df: pd.DataFrame) -> alt.Chart:
    return alt.Chart(df).mark_area(opacity=0.35, line=True).encode(
        x=alt.X("month:O", title="Month", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("adoption_pct:Q", title="Adoption %", scale=alt.Scale(domain=[0, 100])),
        tooltip=["month", "adoption_pct"],
    ).properties(height=220)
