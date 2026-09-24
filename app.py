"""
AI Adoption Value & Governance Navigator
Decide which AI use cases are worth it, safe, and people-ready - then prove the value.
"""

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.brief import build_brief_html
from src.config import Config, LLM_PROVIDERS, SUGGESTED_MODELS
from src.db import Database
from src.exporters import (
    actuals_dataframe, evidence_dataframe, export_markdown, portfolio_dataframe, roi_table,
)
from src.governance import EVIDENCE_STATUSES, assess_governance, evidence_readiness
from src.llm_client import MODEL_LISTING_PROVIDERS, list_models
from src.providers import EnhancedLLMProvider, TemplateProvider
from src.roi import (
    SCENARIOS, annual_running_cost, calculate_scenario, cumulative_cash_flow, realization_summary,
    total_task_hours,
)
from src.sample_data import (
    DECISION_TYPES, DEFAULT_USE_CASE, OVERSIGHT_LEVELS, SENSITIVITY_LEVELS, SOLUTION_TYPES,
    SPECIAL_CATEGORIES, STATUSES, get_sample_actuals, get_sample_evidence, get_sample_use_cases, new_use_case,
)
from src.template_engine import GATE_ICONS, GATE_NEXT_STEP, PACKAGE_VERSION
from src.utils import bullet_list, hours, money, months, pct
from src.validators import validate_use_case
from src import visualizations as viz


st.set_page_config(page_title="AI Adoption Navigator", page_icon=":material/explore:", layout="wide")

GATE_COLORS = {"Go": "green", "Pilot with conditions": "blue", "Fix process first": "orange", "Stop": "red"}
TIER_COLORS = {"Minimal": "green", "Limited": "blue", "High": "orange", "Unacceptable": "red"}
SEVERITY_COLORS = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "gray"}
STATUS_COLORS = {"On track": "green", "Watch": "blue", "Value leakage": "orange",
                 "Critical leakage": "red", "Too early": "gray"}

VIEWS = {
    "Portfolio": ":material/grid_view: Portfolio",
    "Use case": ":material/assignment: Use case",
    "Value tracker": ":material/trending_up: Value tracker",
}
TAB_INTAKE = ":material/edit_note: Intake"
TAB_SUMMARY = ":material/speed: Summary"
TAB_GOV = ":material/policy: Governance & risk"
TAB_PEOPLE = ":material/groups: People & adoption"
TAB_PILOT = ":material/science: Pilot plan"
TAB_REPORT = ":material/download: Report"


# --------------------------------------------------------------------------- state
@st.cache_resource
def get_db() -> Database:
    return Database()


db = get_db()
if "config" not in st.session_state:
    st.session_state.config = Config()
config: Config = st.session_state.config

FIELD_KEYS = list(DEFAULT_USE_CASE.keys())
NEW_USE_CASE = 0  # selectbox sentinel (None would render as "no selection"); SQLite ids start at 1


def load_into_form(uc: Dict[str, Any]):
    for key in FIELD_KEYS:
        st.session_state[f"f_{key}"] = uc.get(key, DEFAULT_USE_CASE[key])


def collect_form() -> Dict[str, Any]:
    return {key: st.session_state.get(f"f_{key}", DEFAULT_USE_CASE[key]) for key in FIELD_KEYS}


def on_select_use_case():
    use_case_id = st.session_state.selected_id
    load_into_form(db.get_use_case(use_case_id) if use_case_id else new_use_case())
    st.session_state.pop("extraction", None)
    st.session_state.view = "Use case"


use_cases = db.list_use_cases()
names = {uc["id"]: uc["name"] for uc in use_cases}

# Apply pending state changes before any widget is created
if "selected_id" not in st.session_state:
    st.session_state.selected_id = NEW_USE_CASE
    st.session_state.view = "Portfolio"  # shows the welcome screen when there are no use cases yet
    load_into_form(new_use_case())
if "pending_select" in st.session_state:
    st.session_state.selected_id = st.session_state.pop("pending_select")
    on_select_use_case()
if "pending_view" in st.session_state:
    st.session_state.view = st.session_state.pop("pending_view")
if "pending_fields" in st.session_state:
    for key, value in st.session_state.pop("pending_fields").items():
        st.session_state[f"f_{key}"] = value

if st.session_state.selected_id not in names:
    st.session_state.selected_id = NEW_USE_CASE


def get_provider():
    if config.get("mode") == "llm" and config.is_llm_ready():
        return EnhancedLLMProvider(
            provider=config.get("llm_provider"), model=config.get("llm_model"),
            base_url=config.get("ollama_url"),
        )
    return TemplateProvider()


def llm_active() -> bool:
    return config.get("mode") == "llm" and config.is_llm_ready()


def md(text: str):
    """Render Markdown with literal dollar signs (Streamlit treats $...$ as LaTeX)"""
    st.markdown(text.replace("$", r"\$"))


def flash(kind: str, message: str):
    st.session_state.setdefault("flash", []).append((kind, message))


def load_samples():
    added = db.load_samples(get_sample_use_cases(), get_sample_actuals(), get_sample_evidence())
    flash("success", f"Loaded {added} sample use cases." if added else "Samples are already loaded.")
    st.session_state.pending_view = "Portfolio"


# ------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title(":material/explore: AI Adoption Navigator")
    st.caption("Is this AI investment worth it, safe, and people-ready - and did the value show up?")

    st.selectbox(
        "Use case", options=[NEW_USE_CASE] + list(names.keys()), key="selected_id", on_change=on_select_use_case,
        format_func=lambda i: "+ New use case" if i == NEW_USE_CASE else names[i],
    )

    st.subheader("Engine")
    mode_label = st.segmented_control(
        "Mode", ["Template", "LLM Enhanced"], required=True,
        default="LLM Enhanced" if config.get("mode") == "llm" else "Template",
        help="Template mode runs fully offline. LLM Enhanced adds AI judgment and narrative - numbers never change.",
    )
    if (mode_label == "LLM Enhanced") != (config.get("mode") == "llm"):
        config.update(mode="llm" if mode_label == "LLM Enhanced" else "template")

    if config.get("mode") == "llm":
        provider_keys = list(LLM_PROVIDERS.keys())
        llm_provider = st.selectbox(
            "LLM provider", provider_keys, index=provider_keys.index(config.get("llm_provider")),
            format_func=lambda p: LLM_PROVIDERS[p],
        )
        if llm_provider != config.get("llm_provider"):
            config.update(llm_provider=llm_provider, llm_model=SUGGESTED_MODELS[llm_provider][0])
            st.rerun()
        if llm_provider == "ollama":
            url = st.text_input("Ollama URL", value=config.get("ollama_url"))
            if url != config.get("ollama_url"):
                config.update(ollama_url=url)
            st.caption(":material/lock: Local model - use case data never leaves this machine.")
        else:
            # One key field per provider, so a key is never applied to the wrong provider
            key_input = st.text_input(
                "API key", type="password", placeholder="Paste key (kept in memory only)",
                key=f"api_key_{llm_provider}",
                help="Stored only in this session's environment variables, never written to disk.",
            )
            if key_input:
                config.set_api_key(key_input, llm_provider)

        # Models: the account's real list when fetched, otherwise suggestions; any name can be typed
        fetched = st.session_state.get(f"models_{llm_provider}")
        base_options = fetched or SUGGESTED_MODELS[llm_provider]
        current_model = config.get("llm_model")
        options = base_options + ([current_model] if current_model not in base_options else [])
        model = st.selectbox(
            "Model", options, index=options.index(current_model), accept_new_options=True,
            help="Pick from the list or type any model name your provider supports."
                 + (" Use 'Load my models' to see every model your key can use."
                    if llm_provider in MODEL_LISTING_PROVIDERS else ""),
        )
        if model and model != current_model:
            config.update(llm_model=model)
        if llm_provider in MODEL_LISTING_PROVIDERS:
            label = "Installed models" if llm_provider == "ollama" else "Load my models"
            if st.button(label, icon=":material/sync:", width="stretch",
                         help="Fetch the models available to your account"):
                try:
                    found = list_models(llm_provider, config.get_api_key(llm_provider), config.get("ollama_url"))
                    st.session_state[f"models_{llm_provider}"] = found
                    if found and config.get("llm_model") not in found:
                        config.update(llm_model=found[0])  # newest model by default
                    flash("success", f"Found {len(found)} models for {LLM_PROVIDERS[llm_provider]}.")
                except Exception as e:
                    flash("error", f"Could not load models: {e}")
                st.rerun()
        if config.is_llm_ready():
            st.badge(f"LLM ready: {config.get('llm_model')}", icon=":material/check:", color="green")
        else:
            st.badge("No API key - using Template mode", icon=":material/warning:", color="orange")
    else:
        st.badge("Template mode - offline", icon=":material/offline_bolt:", color="gray")

    st.subheader("Data")
    if st.button("Load sample portfolio", icon=":material/dataset:", width="stretch"):
        load_samples()
        st.rerun()
    if st.session_state.selected_id:
        with st.popover("Delete this use case", icon=":material/delete:", width="stretch"):
            st.warning(f"Delete **{names[st.session_state.selected_id]}** and its tracked actuals? "
                       "This cannot be undone.")
            if st.button("Yes, delete", type="primary"):
                db.delete_use_case(st.session_state.selected_id)
                st.session_state.pending_select = NEW_USE_CASE
                flash("success", "Use case deleted.")
                st.rerun()


# ------------------------------------------------------------------------ helpers
current_id: Optional[int] = st.session_state.selected_id or None
current_uc: Dict[str, Any] = db.get_use_case(current_id) if current_id else collect_form()


def get_package() -> Optional[Dict[str, Any]]:
    """Saved package if current, otherwise a fresh (unsaved) Template Engine package"""
    if not current_id:
        return None
    saved = db.get_assessment(current_id)
    if saved and saved.get("version") == PACKAGE_VERSION:
        return saved
    return TemplateProvider().assess_use_case(current_uc)


def severity_badges(items: List[Dict[str, str]], text_key: str):
    for item in items:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(item["severity"], color=SEVERITY_COLORS.get(item["severity"], "gray"))
            if item.get("source") == "AI":
                st.badge("AI", icon=":material/auto_awesome:", color="violet")
            md(item[text_key])


def ai_block(title: str, content: Any):
    """Show LLM-only insights in a distinct container"""
    if not content:
        return
    with st.container(border=True):
        md(f"**:material/auto_awesome: {title}**")
        md(bullet_list(content) if isinstance(content, list) else content)


def assess_and_save(uc: Dict[str, Any], use_case_id: Optional[int]) -> int:
    with st.spinner("Assessing with the LLM..." if llm_active() else "Assessing..."):
        use_case_id = db.save_use_case(uc, use_case_id)
        result = get_provider().assess_use_case(uc)
        db.save_assessment(use_case_id, result)
    flash("success", f"Saved and assessed ({result['mode']}).")
    if result.get("llm_error"):
        flash("warning", f"LLM enhancement failed, showing Template Engine results: {result['llm_error']}")
    return use_case_id


def readiness_for(use_case_id: int, checklist: List[Dict[str, str]]) -> Dict[str, Any]:
    return evidence_readiness(checklist, db.get_evidence(use_case_id))


def readiness_color(pct_value: float) -> str:
    return "green" if pct_value >= 100 else "blue" if pct_value >= 60 else "orange"


def tracked_realization() -> pd.DataFrame:
    rows = []
    for uc in use_cases:
        actuals = db.get_actuals(uc["id"])
        if actuals:
            s = realization_summary(uc, actuals)
            rows.append({"Use case": uc["name"], "Realization %": round(s["realization_pct"]),
                         "Status": s["status"], "Months tracked": s["months_tracked"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- header
view = st.segmented_control("View", list(VIEWS.keys()), key="view", required=True,
                            format_func=lambda v: VIEWS[v], label_visibility="collapsed")
for kind, message in st.session_state.pop("flash", []):
    getattr(st, kind)(message)


# ========================================================================= PORTFOLIO
if view == "Portfolio":
    if not use_cases:
        st.header("Welcome to the AI Adoption Navigator")
        md("Many AI investments never show a return. The usual reasons are an unclear value case, "
           "unmanaged risk, or employees who never adopt the tool. This app helps you make every AI "
           "decision **measurable, governed and people-centered**.")
        c1, c2, c3 = st.columns(3)
        with c1.container(border=True):
            md("**:material/edit_note: 1. Describe**\n\nEnter an AI use case, or paste an idea or vendor "
               "pitch and let Smart intake fill in the form.")
        with c2.container(border=True):
            md("**:material/speed: 2. Decide**\n\nGet value, risk and readiness scores, 3-scenario ROI, "
               "a governance checklist, a people plan, and a clear Go / Pilot / Fix / Stop decision.")
        with c3.container(border=True):
            md("**:material/trending_up: 3. Prove**\n\nLog monthly results and see whether the promised "
               "value actually shows up, and why not if it doesn't.")
        with st.container(horizontal=True):
            if st.button("Explore the sample portfolio", icon=":material/dataset:", type="primary"):
                load_samples()
                st.rerun()
            if st.button("Start a new use case", icon=":material/add:"):
                st.session_state.pending_select = NEW_USE_CASE
                st.rerun()
    else:
        df = portfolio_dataframe(use_cases)
        df["id"] = [uc["id"] for uc in use_cases]
        readiness_list = [readiness_for(uc["id"], assess_governance(uc)["checklist"]) for uc in use_cases]
        df["Governance ready %"] = [round(r["readiness_pct"]) if r["total"] else None for r in readiness_list]
        overdue_controls = sum(r["overdue"] for r in readiness_list)
        pursued = df[df["Decision"].isin(["Go", "Pilot with conditions"])]

        st.header("AI portfolio overview")
        with st.container(horizontal=True):
            st.metric("Use cases", len(df), border=True)
            st.metric("Expected 3-yr net value", money(pursued["3-yr net (expected)"].sum()), border=True,
                      help="Use cases with a Go or Pilot decision")
            st.metric("Capacity freed", f"{pursued['Hours saved / yr (expected)'].sum() / 1800:.1f} FTE",
                      border=True, help="Expected scenario, Go and Pilot use cases only")
            st.metric("High / unacceptable risk", int(df["Risk tier"].isin(["High", "Unacceptable"]).sum()),
                      border=True)
            st.metric("Fix process first", int((df["Decision"] == "Fix process first").sum()), border=True,
                      help="Use cases where AI would scale a broken process")
            st.metric("Overdue governance controls", overdue_controls, border=True,
                      help="Controls past their due date that are not Done")

        c1, c2 = st.columns([3, 2])
        with c1.container(border=True):
            st.subheader("Where to invest")
            st.caption("Top-right = quick wins. Bubble size = expected 3-year net value; color = risk tier.")
            st.altair_chart(viz.portfolio_matrix(df))
        with c2:
            with st.container(border=True):
                st.subheader("Decisions")
                st.altair_chart(viz.decision_chart(df))
            realization = tracked_realization()
            with st.container(border=True):
                st.subheader("Is the value showing up?")
                if realization.empty:
                    st.caption("No actuals logged yet - use the Value tracker once a use case is live.")
                else:
                    st.caption("Share of promised hours actually saved. Dashed lines: 70% (watch) and 90% (on track).")
                    st.altair_chart(viz.portfolio_realization_chart(realization))

        st.subheader("Ranked portfolio")
        st.caption(":material/touch_app: Select a row to open that use case.")
        event = st.dataframe(
            df.sort_values(["Value", "Feasibility"], ascending=False), hide_index=True,
            on_select="rerun", selection_mode="single-row", key="portfolio_table",
            column_order=[c for c in df.columns if c != "id"],
            column_config={
                "Value": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                "Feasibility": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                "Adoption readiness": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                "Governance ready %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%"),
                "3-yr net (expected)": st.column_config.NumberColumn(format="dollar"),
                "3-yr net (conservative)": st.column_config.NumberColumn(format="dollar"),
            },
        )
        if event.selection.rows:
            ranked = df.sort_values(["Value", "Feasibility"], ascending=False)
            st.session_state.pending_select = int(ranked.iloc[event.selection.rows[0]]["id"])
            st.rerun()

        with st.container(horizontal=True):
            st.download_button("Download portfolio CSV", portfolio_dataframe(use_cases).to_csv(index=False),
                               file_name="ai_portfolio.csv", mime="text/csv", icon=":material/table:",
                               on_click="ignore")
            all_actuals = []
            for uc in use_cases:
                rows = db.get_actuals(uc["id"])
                if rows:
                    promised = calculate_scenario(uc, **SCENARIOS["Expected"])["annual_hours_saved"] / 12
                    all_actuals.append(actuals_dataframe(uc, rows, promised))
            if all_actuals:
                st.download_button("Download value tracker CSV", pd.concat(all_actuals).to_csv(index=False),
                                   file_name="ai_value_tracker.csv", mime="text/csv", icon=":material/table:",
                                   on_click="ignore")
            audit = [evidence_dataframe(r["rows"]).assign(**{"Use case": uc["name"]})
                     for uc, r in zip(use_cases, readiness_list) if r["rows"]]
            if audit:
                st.download_button("Download governance audit trail CSV",
                                   pd.concat(audit)[["Use case", *audit[0].columns[:-1]]].to_csv(index=False),
                                   file_name="ai_governance_audit_trail.csv", mime="text/csv",
                                   icon=":material/fact_check:", on_click="ignore")


# ========================================================================== USE CASE
elif view == "Use case":
    package = get_package()
    st.header(current_uc["name"] if current_id else "New AI use case")

    readiness: Optional[Dict[str, Any]] = None
    if package:
        a = package["assessment"]
        gate = a["gate"]["gate"]
        readiness = readiness_for(current_id, a["governance"]["checklist"])
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(gate, icon=GATE_ICONS[gate], color=GATE_COLORS[gate])
                st.badge(f"{a['governance']['tier']} risk", color=TIER_COLORS[a["governance"]["tier"]])
                if readiness["total"]:
                    st.badge(f"Governance {readiness['readiness_pct']:.0f}% ready", icon=":material/verified_user:",
                             color=readiness_color(readiness["readiness_pct"]))
                st.badge(a["quadrant"], color="gray")
                st.badge(a["workforce"]["category"], icon=":material/groups:", color="gray")
                st.caption(f"Engine: {package.get('mode', 'Template Engine')}")
            md(f"**Next step:** {GATE_NEXT_STEP[gate]}")
        if package.get("llm_error"):
            st.warning(f"LLM enhancement failed, showing Template Engine output: {package['llm_error']}")
    else:
        st.caption("Fill in what you know - fields marked * are required. Sliders run from 1 (low) to 5 (high). "
                   "Tip: paste a rough idea into Smart intake to pre-fill the form.")

    tab_intake, tab_summary, tab_gov, tab_people, tab_pilot, tab_report = st.tabs(
        [TAB_INTAKE, TAB_SUMMARY, TAB_GOV, TAB_PEOPLE, TAB_PILOT, TAB_REPORT],
        default=TAB_SUMMARY if package else TAB_INTAKE,
    )

    # ------------------------------------------------------------------- intake
    with tab_intake:
        with st.expander("Smart intake - paste an idea, email or vendor pitch", icon=":material/auto_awesome:",
                         expanded=not current_id):
            st.caption("Template mode uses keyword rules; LLM Enhanced mode reads the text with real understanding. "
                       "Suggestions are never applied without your review.")
            raw_text = st.text_area("Text", height=130, label_visibility="collapsed",
                                    placeholder="e.g. Our recruiters get 300 applications per week and spend 4 minutes "
                                                "on each resume. A vendor offers an AI that auto-rejects weak candidates...")
            if st.button("Extract fields", icon=":material/manage_search:", disabled=not raw_text.strip()):
                with st.spinner("Reading the text..."):
                    st.session_state.extraction = get_provider().extract_use_case(raw_text)
            extraction = st.session_state.get("extraction")
            if extraction:
                if extraction["fields"]:
                    st.dataframe(pd.DataFrame([{"Field": k, "Suggested value": str(v)}
                                               for k, v in extraction["fields"].items()]), hide_index=True)
                    if st.button("Apply suggestions to the form", icon=":material/check:", type="primary"):
                        st.session_state.pending_fields = extraction["fields"]
                        st.session_state.pop("extraction")
                        st.rerun()
                else:
                    st.info("No fields could be extracted.")
                if extraction.get("notes"):
                    md("**Notes**\n" + bullet_list(extraction["notes"]))
                if extraction.get("missing"):
                    md("**Still missing**\n" + bullet_list(extraction["missing"]))

        with st.form("intake"):
            st.subheader("1. Process and pain")
            c1, c2, c3, c4 = st.columns(4)
            c1.text_input("Use case name *", key="f_name")
            c2.text_input("Business unit", key="f_business_unit")
            c3.text_input("Sponsor", key="f_sponsor")
            c4.selectbox("Status", STATUSES, key="f_status")
            c1, c2 = st.columns(2)
            c1.text_area("Current process *", key="f_process_description", height=100,
                         help="How is the work done today, step by step?")
            c2.text_area("Pain point", key="f_pain_point", height=100,
                         help="What goes wrong today, and what does it cost?")

            st.subheader("2. Volume, cost and value")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.number_input("Tasks per month *", min_value=0, step=10, key="f_tasks_per_month")
            c2.number_input("Minutes per task *", min_value=0, step=1, key="f_minutes_per_task")
            c3.number_input("AI time reduction %", min_value=0, max_value=100, step=5, key="f_time_reduction_pct",
                            help="Share of task time AI removes. Validate on real samples.")
            c4.number_input("People involved", min_value=0, step=1, key="f_people_involved")
            c5.number_input("Loaded hourly cost ($) *", min_value=0.0, step=5.0, key="f_hourly_cost",
                            help="Salary + benefits + overhead per hour")
            c1, c2 = st.columns(2)
            c1.slider("Strategic alignment", 1, 5, key="f_strategic_alignment",
                      help="1 = nice to have, 5 = directly supports a top company priority")
            c2.slider("Customer / quality impact", 1, 5, key="f_customer_impact",
                      help="1 = internal convenience, 5 = major improvement for customers or quality")

            st.subheader("3. Data and feasibility")
            c1, c2 = st.columns([2, 1])
            c1.text_input("Data sources", key="f_data_sources")
            c2.selectbox("Data sensitivity", SENSITIVITY_LEVELS, key="f_data_sensitivity")
            c1, c2, c3, c4 = st.columns(4)
            c1.slider("Data quality", 1, 5, key="f_data_quality", help="1 = messy/incomplete, 5 = clean and complete")
            c2.slider("Integration complexity", 1, 5, key="f_integration_complexity",
                      help="1 = standalone tool, 5 = deep integration with several systems")
            c3.slider("In-house skills", 1, 5, key="f_inhouse_skills",
                      help="1 = no AI/data skills in the team, 5 = experienced team")
            c4.slider("Solution maturity", 1, 5, key="f_solution_maturity",
                      help="1 = experimental, 5 = proven product with references")
            st.selectbox("Solution type", SOLUTION_TYPES, key="f_solution_type")

            st.subheader("4. Decisions and oversight")
            c1, c2 = st.columns(2)
            c1.selectbox("Decision type", DECISION_TYPES, key="f_decision_type")
            c2.selectbox("Planned human oversight", OVERSIGHT_LEVELS, key="f_human_oversight")
            c1, c2, c3 = st.columns(3)
            c1.toggle("Customer-facing", key="f_customer_facing")
            c2.toggle("Generates content people read or act on", key="f_generates_content")
            c3.toggle("Influences decisions about people", key="f_people_decisions",
                      help="Hiring, credit, health, performance evaluation, access to services")
            st.multiselect("Special categories (if any)", SPECIAL_CATEGORIES, key="f_special_categories")

            st.subheader("5. Costs")
            c1, c2, c3 = st.columns(3)
            c1.number_input("Implementation cost ($, one-time)", min_value=0.0, step=1000.0,
                            key="f_implementation_cost", help="Integration, configuration, testing, training, change management")
            c2.number_input("License cost ($/year)", min_value=0.0, step=1000.0, key="f_license_cost_annual")
            c3.number_input("Run / support cost ($/year)", min_value=0.0, step=1000.0, key="f_run_cost_annual",
                            help="Support, monitoring, API usage, periodic re-validation")

            st.subheader("6. People and adoption")
            c1, c2 = st.columns(2)
            c1.text_input("Success metric", key="f_success_metric", help="How will you know it worked?")
            c2.text_input("Roles affected (comma-separated)", key="f_roles_affected")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.toggle("Sponsor committed", key="f_sponsor_committed")
            c2.toggle("Process standardized", key="f_process_standardized",
                      help="Is there one documented way of doing the work today?")
            c3.toggle("Training plan", key="f_has_training_plan")
            c4.toggle("User champions", key="f_has_champions")
            c5.slider("User involvement", 1, 5, key="f_user_involvement",
                      help="How involved are future users in designing the solution?")

            submitted = st.form_submit_button(
                "Save and assess" + (" with LLM" if llm_active() else ""),
                type="primary", icon=":material/play_arrow:",
            )

        if submitted:
            uc = collect_form()
            errors = validate_use_case(uc)
            if errors:
                st.error("\n".join(f"- {e}" for e in errors))
            else:
                st.session_state.pending_select = assess_and_save(uc, current_id)
                st.rerun()

    def need_package() -> bool:
        if package is None:
            st.info("Fill in the Intake tab and click **Save and assess** to see results.", icon=":material/info:")
            return False
        return True

    # ------------------------------------------------------------------ summary
    with tab_summary:
        if need_package():
            with st.container(horizontal=True):
                st.metric("3-yr net (expected)", money(a["roi"]["Expected"]["net_3yr"]), border=True)
                st.metric("3-yr net (conservative)", money(a["roi"]["Conservative"]["net_3yr"]), border=True,
                          help="The figure to commit to in a business case")
                st.metric("Payback (expected)", months(a["roi"]["Expected"]["payback_months"]), border=True)
                st.metric("Capacity freed", f"{a['roi']['Expected']['fte_equivalent']:.1f} FTE", border=True,
                          help=f"{hours(a['roi']['Expected']['annual_hours_saved'])} per year, Expected scenario")

            c1, c2 = st.columns([3, 2])
            with c1:
                st.subheader("Executive summary")
                md(package["sections"]["executive_summary"])
            with c2.container(border=True):
                md(package["sections"]["final_recommendation"])

            c1, c2 = st.columns([2, 3])
            with c1.container(border=True):
                st.subheader("Scores")
                st.caption("Green = above the 50-point threshold (dashed line) used for the decision; orange = below")
                st.altair_chart(viz.score_bars(a["scores"]))
                with st.expander("How the scores work"):
                    md("- **Value**: hours saved (40 pts, max at ~2 FTE), strategic alignment (30), "
                       "customer/quality impact (30)\n"
                       "- **Feasibility**: data quality (30), integration ease (25), in-house skills (25), "
                       "solution maturity (20), minus a penalty for confidential/personal data\n"
                       "- **Adoption readiness**: sponsor (25), standardized process (25), training plan (20), "
                       "champions (15), user involvement (15)\n\n"
                       "Scores, ROI and the decision are calculated by rules, never by the LLM.")
            with c2.container(border=True):
                st.subheader("When does it pay back?")
                st.caption("Cumulative net value after go-live. Where a line crosses $0 is the payback month.")
                st.altair_chart(viz.cash_flow_chart(cumulative_cash_flow(a["roi"])))

            with st.expander("ROI details and assumptions", icon=":material/calculate:"):
                st.dataframe(roi_table(a), hide_index=True, column_config={
                    "Annual benefit": st.column_config.NumberColumn(format="dollar"),
                    "Annual running cost": st.column_config.NumberColumn(format="dollar"),
                    "3-yr net value": st.column_config.NumberColumn(format="dollar"),
                    "Hours saved / yr": st.column_config.NumberColumn(format="localized"),
                })
                md(package["sections"]["roi_assumptions"])

            st.subheader("Assumption checks")
            if package["assumption_checks"]:
                severity_badges(package["assumption_checks"], "check")
            else:
                st.success("No assumption issues found.")

            if st.button(f"Re-assess with {'LLM' if llm_active() else 'Template Engine'}", icon=":material/refresh:"):
                assess_and_save(current_uc, current_id)
                st.rerun()

    # --------------------------------------------------------------- governance
    with tab_gov:
        if need_package():
            g = a["governance"]
            st.altair_chart(viz.tier_ladder(g["tier"]))
            c1, c2 = st.columns([2, 3])
            with c1:
                with st.container(border=True):
                    md(package["sections"]["governance_summary"])
                ai_block("Why this tier - AI rationale", package["ai_insights"].get("governance_rationale"))
            with c2:
                md("**Red flags**")
                if g["flags"]:
                    severity_badges(g["flags"], "flag")
                else:
                    st.success("No red flags.")
                ai_block("Controls that matter most here", package["ai_insights"].get("key_controls"))

            st.subheader("Governance evidence tracker (NIST AI RMF)")
            if not g["checklist"]:
                st.error("No checklist - this use case must not be deployed.")
            else:
                st.caption("Turn the checklist into proof: assign an owner and due date to each control and record "
                           "the evidence (document, link, decision). Go-live needs 100% readiness.")
                with st.container(horizontal=True):
                    st.metric("Go-live readiness", pct(readiness["readiness_pct"]), border=True,
                              help="Done / applicable controls (Not applicable controls are excluded)")
                    st.metric("Controls done", f"{readiness['done']} / {readiness['total']}", border=True)
                    st.metric("Overdue", readiness["overdue"], border=True,
                              delta="needs attention" if readiness["overdue"] else None, delta_color="inverse")
                    st.metric("Without owner", readiness["unassigned"], border=True)
                if readiness["readiness_pct"] >= 100:
                    st.success("All applicable controls have evidence - governance is ready for go-live.",
                               icon=":material/verified_user:")
                elif g["tier"] == "High":
                    st.warning("High-risk use case: do not go live until every control is Done.",
                               icon=":material/gpp_maybe:")

                with st.container(border=True):
                    st.markdown("**Control status by NIST AI RMF function**")
                    st.altair_chart(viz.governance_readiness_chart(readiness["by_function"]))
                with st.form(f"evidence_{current_id}"):
                    edited = st.data_editor(
                        evidence_dataframe(readiness["rows"]).assign(
                            **{"Due date": [r["due_date"] for r in readiness["rows"]],
                               "Overdue": [r["overdue"] for r in readiness["rows"]]}),
                        hide_index=True, num_rows="fixed",
                        disabled=["Function", "Control", "Required from tier", "Overdue"],
                        column_order=["Status", "Control", "Owner", "Due date", "Evidence", "Overdue",
                                      "Function", "Required from tier"],
                        column_config={
                            "Status": st.column_config.SelectboxColumn(options=EVIDENCE_STATUSES, required=True),
                            "Control": st.column_config.TextColumn(width="large"),
                            "Due date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                            "Evidence": st.column_config.TextColumn(width="medium",
                                                                    help="Document name, link or decision"),
                            "Overdue": st.column_config.CheckboxColumn(),
                        },
                    )
                    if st.form_submit_button("Save evidence", icon=":material/save:", type="primary"):
                        db.save_evidence(current_id, [{
                            "control": row["Control"],
                            "status": row["Status"],
                            "owner": row["Owner"] or "",
                            "due_date": None if pd.isna(row["Due date"]) else pd.Timestamp(row["Due date"]).date(),
                            "evidence": row["Evidence"] or "",
                        } for row in edited.to_dict("records")])
                        flash("success", "Governance evidence saved.")
                        st.rerun()
                slug = current_uc["name"].lower().replace(" ", "_")
                st.download_button("Download audit trail (CSV)",
                                   evidence_dataframe(readiness["rows"]).to_csv(index=False),
                                   file_name=f"governance_evidence_{slug}.csv", mime="text/csv",
                                   icon=":material/fact_check:", on_click="ignore")
            st.caption(g["disclaimer"])

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Data readiness")
                md(package["sections"]["data_readiness"])
            with c2:
                st.subheader("Human-in-the-loop design")
                md(package["sections"]["hitl_design"])

    # ------------------------------------------------------------------- people
    with tab_people:
        if need_package():
            with st.container(border=True):
                st.subheader("Where the time goes")
                st.caption("Annual hours spent on this task today, and how much AI frees up in each scenario. "
                           "Plan where the freed time goes before go-live.")
                st.altair_chart(viz.time_freed_chart(total_task_hours(current_uc), a["roi"]))
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Workforce impact and reskilling")
                md(package["sections"]["workforce_plan"])
                ai_block("AI workforce recommendations", package["ai_insights"].get("workforce_narrative"))
            with c2:
                st.subheader("Change and adoption plan (ADKAR)")
                md(package["sections"]["adoption_plan"])
                ai_block("AI adoption recommendations", package["ai_insights"].get("adoption_narrative"))
            st.subheader("Stakeholder communication")
            md(package["sections"]["stakeholder_comms"])

    # -------------------------------------------------------------------- pilot
    with tab_pilot:
        if need_package():
            with st.container(border=True):
                st.subheader("30/60/90-day pilot")
                st.altair_chart(viz.pilot_timeline())
            md(package["sections"]["pilot_plan"])
            ai_block("AI adjustments for this pilot", package["ai_insights"].get("pilot_adjustments"))
            st.subheader("Risk log")
            risks = pd.DataFrame(package["risks"])
            if "source" in risks.columns:
                risks["source"] = risks["source"].fillna("Rules")
            st.dataframe(risks, hide_index=True)

    # ------------------------------------------------------------------- report
    with tab_report:
        if need_package():
            slug = current_uc["name"].lower().replace(" ", "_")
            st.subheader("Executive decision brief")
            st.caption("One page for sponsors and leadership. Open the downloaded file in a browser and use "
                       "Print > Save as PDF for a PDF version.")
            with st.container(horizontal=True):
                st.download_button("Download executive brief (HTML)",
                                   build_brief_html(current_uc, package, readiness),
                                   file_name=f"decision_brief_{slug}.html", mime="text/html",
                                   icon=":material/summarize:", on_click="ignore", type="primary")
                report = export_markdown(current_uc, package, readiness)
                st.download_button("Download full report (Markdown)", report, file_name=f"ai_assessment_{slug}.md",
                                   mime="text/markdown", icon=":material/description:", on_click="ignore")
            with st.container(border=True):
                st.html(build_brief_html(current_uc, package, readiness, standalone=False))

            st.subheader("Achievement statement")
            st.code(package["sections"]["linkedin_statement"], language=None, wrap_lines=True)
            with st.expander("Preview full report"):
                md(report)


# ===================================================================== VALUE TRACKER
elif view == "Value tracker":
    st.header("Value tracker")
    st.caption("Approved is not the same as delivered. Log what actually happened each month; "
               "promised = the Expected scenario from the business case.")
    if not use_cases:
        st.info("No use cases yet. Load the sample portfolio from the sidebar or create a use case first.")
    else:
        ids = list(names.keys())
        months_logged = {i: len(db.get_actuals(i)) for i in ids}
        tracker_id = st.selectbox(
            "Use case", ids, index=ids.index(current_id) if current_id in ids else 0,
            format_func=lambda i: f"{names[i]}  ({months_logged[i]} months tracked)" if months_logged[i]
            else f"{names[i]}  (not tracked yet)",
        )
        tracked_uc = db.get_use_case(tracker_id)
        actuals = db.get_actuals(tracker_id)
        diagnoses = st.session_state.setdefault("diagnoses", {})

        with st.expander("Log a month", icon=":material/add:", expanded=not actuals):
            with st.form("actuals", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns(4)
                month = c1.date_input("Month (any day in it)", value=date.today()).strftime("%Y-%m")
                hours_saved = c2.number_input("Hours saved", min_value=0.0, step=10.0)
                adoption = c3.number_input("Adoption % of users", min_value=0.0, max_value=100.0, step=5.0)
                cost = c4.number_input("Actual cost ($)", min_value=0.0, step=100.0)
                notes = st.text_input("Notes (what happened this month)")
                if st.form_submit_button("Save month", icon=":material/save:"):
                    db.upsert_actual(tracker_id, month, hours_saved, adoption, cost, notes)
                    diagnoses.pop(tracker_id, None)  # the old diagnosis no longer matches the data
                    st.rerun()

        if not actuals:
            st.info("No months logged yet for this use case.")
        else:
            summary = realization_summary(tracked_uc, actuals)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(summary["status"], color=STATUS_COLORS[summary["status"]], icon=":material/monitoring:")
                st.caption(f"{summary['months_tracked']} months tracked - adoption trend: {summary['adoption_trend']}")
            with st.container(horizontal=True):
                st.metric("Realization", pct(summary["realization_pct"]), border=True,
                          help="Actual hours saved / promised hours")
                st.metric("Hours saved", hours(summary["actual_hours"]),
                          delta=f"{summary['actual_hours'] - summary['promised_hours']:,.0f} h vs plan", border=True)
                st.metric("Realized net value", money(summary["realized_value"]),
                          delta=f"{money(-summary['value_gap'])} vs plan", border=True)
                st.metric("Latest adoption", pct(summary["latest_adoption_pct"]), border=True)

            df_actuals = actuals_dataframe(tracked_uc, actuals, summary["promised_monthly_hours"])
            c1, c2 = st.columns([3, 2])
            with c1.container(border=True):
                st.subheader("Promised vs realized value")
                st.caption("The shaded gap is value leakage - approved, paid for, but not delivered.")
                st.altair_chart(viz.cumulative_value_chart(
                    df_actuals, float(tracked_uc["hourly_cost"]), annual_running_cost(tracked_uc) / 12))
            with c2.container(border=True):
                st.subheader("Adoption")
                st.caption("Share of intended users actively using the tool")
                st.altair_chart(viz.adoption_chart(df_actuals))

            with st.expander("Monthly data", icon=":material/table:"):
                st.dataframe(df_actuals.drop(columns=["use_case"]), hide_index=True)
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    month_to_delete = st.selectbox("Remove a month", [row["month"] for row in actuals])
                    if st.button("Remove", icon=":material/delete:"):
                        db.delete_actual(tracker_id, month_to_delete)
                        diagnoses.pop(tracker_id, None)
                        st.rerun()

            st.subheader("Why is value leaking?")
            if st.button("Diagnose", icon=":material/troubleshoot:", type="primary"):
                with st.spinner("Diagnosing..."):
                    diagnoses[tracker_id] = get_provider().diagnose_value_gap(tracked_uc, summary, actuals)
            diagnosis = diagnoses.get(tracker_id)
            if diagnosis:
                if diagnosis.get("narrative"):
                    ai_block("Summary for the sponsor", diagnosis["narrative"])
                c1, c2 = st.columns(2)
                with c1:
                    md("**Likely causes**\n" + bullet_list(diagnosis["causes"]))
                with c2:
                    md("**Corrective actions**\n" + bullet_list(diagnosis["actions"]))
