"""
BioOps Guardian — Streamlit Dashboard
======================================
Run with:  streamlit run app/streamlit_app.py
"""

import sys
import pathlib
import os

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.log_parser import parse_nextflow_log
from src.sample_validator import validate_sample_sheet
from src.patterns import ERROR_PATTERNS
from src.scrna_patterns import SCRNA_PATTERNS
from src.ml_classifier import MLClassifier
from src.preflight import run_preflight

ALL_PATTERNS = ERROR_PATTERNS + SCRNA_PATTERNS

DEMO_LOG = PROJECT_ROOT / "data" / "demo_assets" / "example.log"
DEMO_SHEET = PROJECT_ROOT / "data" / "demo_assets" / "example_samplesheet.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "guardian_v1.pkl"


@st.cache_resource
def load_model():
    if MODEL_PATH.exists():
        clf = MLClassifier()
        clf.load(str(MODEL_PATH))
        return clf
    return None


PATTERN_LOOKUP = {p["id"]: p for p in ALL_PATTERNS}

st.set_page_config(
    page_title="BioOps Guardian",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════
# GLOBAL CSS — Scientific Playground vibe
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── Force light background ────────────────────── */
    .stApp {
        background: #F8F9FC !important;
        font-family: 'DM Sans', sans-serif !important;
        color: #1E1E2E !important;
    }
    .stApp > header { background: transparent !important; }

    /* ── Sidebar hide ──────────────────────────────── */
    [data-testid="stSidebar"] { display: none; }
    .stDeployButton { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ── Top brand bar ─────────────────────────────── */
    .brand-bar {
        background: linear-gradient(135deg, #6C5CE7, #A78BFA, #7C3AED);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }
    .brand-bar::before {
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 200px; height: 200px;
        background: rgba(255,255,255,0.08);
        border-radius: 50%;
    }
    .brand-bar::after {
        content: '🧬';
        position: absolute;
        top: 16px; right: 28px;
        font-size: 3rem;
        opacity: 0.3;
    }
    .brand-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #fff;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .brand-sub {
        color: rgba(255,255,255,0.8);
        font-size: 0.95rem;
        margin: 4px 0 0 0;
    }

    /* ── Tabs ───────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: #fff;
        border-radius: 12px;
        padding: 6px;
        gap: 4px;
        border: 1px solid #E8E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        color: #6B7280 !important;
        font-family: 'DM Sans', sans-serif;
    }
    .stTabs [aria-selected="true"] {
        background: #6C5CE7 !important;
        color: #fff !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 20px;
    }

    /* ── Cards ──────────────────────────────────────── */
    .card {
        background: #FFFFFF;
        border: 1px solid #E8E8F0;
        border-radius: 14px;
        padding: 22px 26px;
        margin-bottom: 16px;
        box-shadow: 0 1px 4px rgba(108,92,231,0.04);
    }
    .card-header {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #9CA3AF;
        margin-bottom: 8px;
    }

    /* Status cards */
    .card-success { border-left: 4px solid #10B981; }
    .card-error   { border-left: 4px solid #EF4444; }
    .card-warning { border-left: 4px solid #F59E0B; }
    .card-info    { border-left: 4px solid #6C5CE7; }

    /* ── Stat cards ─────────────────────────────────── */
    .stat-card {
        background: #FFFFFF;
        border: 1px solid #E8E8F0;
        border-radius: 12px;
        padding: 18px 22px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        margin: 0;
        line-height: 1.2;
    }
    .stat-label {
        font-size: 0.7rem;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 6px 0 0 0;
        font-weight: 500;
    }

    /* ── Badges ─────────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
        vertical-align: middle;
    }
    .badge-critical { background: #FEE2E2; color: #DC2626; }
    .badge-high     { background: #FEF3C7; color: #D97706; }
    .badge-medium   { background: #FEF9C3; color: #CA8A04; }
    .badge-warning  { background: #FEF3C7; color: #D97706; }
    .badge-info     { background: #EDE9FE; color: #6C5CE7; }
    .badge-clean    { background: #D1FAE5; color: #059669; }
    .badge-pass     { background: #D1FAE5; color: #059669; }
    .badge-fail     { background: #FEE2E2; color: #DC2626; }
    .badge-warn     { background: #FEF3C7; color: #D97706; }
    .badge-csv      { background: #EDE9FE; color: #6C5CE7; }
    .badge-config   { background: #DBEAFE; color: #2563EB; }

    /* ── Verdict banners ───────────────────────────── */
    .verdict {
        border-radius: 14px;
        padding: 22px 28px;
        margin: 16px 0;
    }
    .verdict-pass {
        background: linear-gradient(135deg, #D1FAE5, #F0FDF4);
        border: 1px solid #A7F3D0;
    }
    .verdict-fail {
        background: linear-gradient(135deg, #FEE2E2, #FEF2F2);
        border: 1px solid #FECACA;
    }
    .verdict-warn {
        background: linear-gradient(135deg, #FEF3C7, #FFFBEB);
        border: 1px solid #FDE68A;
    }
    .verdict-text {
        font-size: 1.15rem;
        font-weight: 600;
        margin: 0;
    }
    .verdict-pass .verdict-text { color: #065F46; }
    .verdict-fail .verdict-text { color: #991B1B; }
    .verdict-warn .verdict-text { color: #92400E; }

    /* ── Check items ───────────────────────────────── */
    .check-item {
        background: #fff;
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 8px;
        font-size: 0.9rem;
        border: 1px solid #E8E8F0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .check-pass { border-left: 4px solid #10B981; }
    .check-fail { border-left: 4px solid #EF4444; }
    .check-warn { border-left: 4px solid #F59E0B; }
    .check-skip { border-left: 4px solid #8B5CF6; }
    .check-icon { font-size: 1.1rem; flex-shrink: 0; }
    .check-content { flex: 1; }
    .check-name { font-weight: 600; color: #1E1E2E; }
    .check-msg  { color: #6B7280; }

    /* ── Section headers ───────────────────────────── */
    .section-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1E1E2E;
        margin: 28px 0 14px 0;
        padding-bottom: 10px;
        border-bottom: 2px solid #EDE9FE;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-icon {
        width: 28px; height: 28px;
        background: #EDE9FE;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
    }

    /* ── Process bars ──────────────────────────────── */
    .process-bar {
        background: #F3F4F6;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: #374151;
        border: 1px solid #E5E7EB;
    }

    /* ── Feature bars ──────────────────────────────── */
    .feat-bar-container {
        display: flex;
        align-items: center;
        margin-bottom: 6px;
        font-size: 0.82rem;
    }
    .feat-bar {
        height: 10px;
        background: linear-gradient(90deg, #6C5CE7, #A78BFA);
        border-radius: 5px;
        margin-right: 12px;
        min-width: 6px;
    }
    .feat-name {
        color: #6B7280;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ── What we check sidebar ─────────────────────── */
    .info-card {
        background: #fff;
        border: 1px solid #E8E8F0;
        border-radius: 14px;
        padding: 20px 22px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .info-card h4 {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1E1E2E;
        margin: 0 0 12px 0;
    }
    .info-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 0;
        font-size: 0.85rem;
        color: #4B5563;
    }
    .info-icon {
        width: 24px; height: 24px;
        border-radius: 6px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7rem;
        flex-shrink: 0;
    }

    /* ── Buttons override ──────────────────────────── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6C5CE7, #7C3AED) !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'DM Sans', sans-serif !important;
        padding: 12px 24px !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #5B4BD5, #6D28D9) !important;
    }

    /* ── Text inputs ───────────────────────────────── */
    .stTextArea textarea, .stTextInput input {
        border-radius: 10px !important;
        border: 1px solid #E5E7EB !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        background: #FAFBFC !important;
        color: #1E1E2E !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #6C5CE7 !important;
        box-shadow: 0 0 0 3px rgba(108,92,231,0.1) !important;
    }

    /* ── File uploader ─────────────────────────────── */
    [data-testid="stFileUploader"] {
        border-radius: 12px;
    }
    [data-testid="stFileUploader"] section {
        border-radius: 12px !important;
        border: 2px dashed #D1D5DB !important;
        background: #FAFBFC !important;
    }

    /* ── Expanders ─────────────────────────────────── */
    .streamlit-expanderHeader {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
    }

    /* ── Code blocks ───────────────────────────────── */
    code {
        font-family: 'JetBrains Mono', monospace !important;
    }
    .stCodeBlock {
        border-radius: 10px !important;
    }

    /* ── Privacy footer ────────────────────────────── */
    .privacy-footer {
        text-align: center;
        color: #9CA3AF;
        font-size: 0.75rem;
        padding: 20px 0 10px 0;
        border-top: 1px solid #E8E8F0;
        margin-top: 40px;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ─────────────────────────────────────────────
def badge(text, style="info"):
    return f'<span class="badge badge-{style}">{text}</span>'

def verdict_banner(verdict, message):
    return f'<div class="verdict verdict-{verdict}"><p class="verdict-text">{message}</p></div>'

def stat_card(value, label, color="#6C5CE7"):
    return f'<div class="stat-card"><p class="stat-value" style="color:{color}">{value}</p><p class="stat-label">{label}</p></div>'

def section_header(icon, text):
    return f'<div class="section-header"><span class="section-icon">{icon}</span> {text}</div>'

def check_html(status, name, message):
    icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}
    return f"""<div class="check-item check-{status}">
        <span class="check-icon">{icons.get(status, "•")}</span>
        <div class="check-content"><span class="check-name">{name}</span><br><span class="check-msg">{message}</span></div>
    </div>"""

def info_card_html():
    return """<div class="info-card"><h4>What we check</h4>
        <div class="info-item"><span class="info-icon" style="background:#D1FAE5">📋</span> Sample sheet format & integrity</div>
        <div class="info-item"><span class="info-icon" style="background:#DBEAFE">📁</span> File paths & accessibility</div>
        <div class="info-item"><span class="info-icon" style="background:#EDE9FE">⚙️</span> Config syntax & parameters</div>
        <div class="info-item"><span class="info-icon" style="background:#FEF3C7">💾</span> Resource requirements</div>
        <div class="info-item"><span class="info-icon" style="background:#FEE2E2">🔍</span> Known failure patterns</div>
    </div>"""

def get_regex_details(pattern_id, log_text):
    pattern = PATTERN_LOOKUP.get(pattern_id)
    if not pattern:
        return []
    lines = log_text.split("\n")
    matched = []
    for idx, line in enumerate(lines):
        if any(p.search(line) for p in pattern["patterns"]):
            matched.append({"line_num": idx + 1, "text": line.strip()})
    return matched


# ── Callbacks ────────────────────────────────────────────────────
def on_log_upload():
    u = st.session_state.get("log_upload")
    if u: st.session_state["log_data"] = u.read().decode("utf-8", errors="replace")

def on_sheet_upload():
    u = st.session_state.get("sheet_upload")
    if u: st.session_state["sheet_data"] = u.read().decode("utf-8", errors="replace")

def on_pf_sheet_upload():
    u = st.session_state.get("pf_sheet_upload")
    if u: st.session_state["pf_sheet_data"] = u.read().decode("utf-8", errors="replace")

def on_pf_config_upload():
    u = st.session_state.get("pf_config_upload")
    if u: st.session_state["pf_config_data"] = u.read().decode("utf-8", errors="replace")

# ── Session state ────────────────────────────────────────────────
for key in ["log_data", "sheet_data", "pf_sheet_data", "pf_config_data"]:
    if key not in st.session_state: st.session_state[key] = ""
for key in ["log_result", "sheet_result", "preflight_result"]:
    if key not in st.session_state: st.session_state[key] = None


# ── Brand bar ────────────────────────────────────────────────────
st.markdown("""
<div class="brand-bar">
    <p class="brand-title">🧬 BioOps Guardian</p>
    <p class="brand-sub">Let's catch failures before they happen — validate inputs, analyze logs, and launch with confidence.</p>
</div>
""", unsafe_allow_html=True)

ml_model = load_model()

tab_preflight, tab_log, tab_sheet, tab_ref = st.tabs([
    "🚀 Pre-Flight Check",
    "🔬 Log Analyzer",
    "📋 Sheet Validator",
    "📖 Pattern Reference",
])


# ═══════════════════════════════════════════════════════════════════
# TAB 0 — Pre-Flight Check
# ═══════════════════════════════════════════════════════════════════
with tab_preflight:
    col_main, col_side = st.columns([3, 1], gap="large")

    with col_main:
        col_left, col_right = st.columns(2, gap="medium")

        with col_left:
            st.markdown(f"**Sample Sheet** {badge('CSV', 'csv')}", unsafe_allow_html=True)
            st.file_uploader("Upload", type=["csv", "txt", "tsv"],
                             key="pf_sheet_upload", on_change=on_pf_sheet_upload, label_visibility="collapsed")
            pf_sheet = st.text_area("Or paste CSV content", value=st.session_state["pf_sheet_data"],
                                    height=130, key="pf_sheet_area",
                                    placeholder="sample,fastq_1,fastq_2,strandedness\nS1,/data/S1_R1.fastq.gz,/data/S1_R2.fastq.gz,reverse")
            if pf_sheet and pf_sheet != st.session_state["pf_sheet_data"]:
                st.session_state["pf_sheet_data"] = pf_sheet

        with col_right:
            st.markdown(f"**Nextflow Config** {badge('CONFIG', 'config')}", unsafe_allow_html=True)
            st.file_uploader("Upload", type=["config", "txt", "conf"],
                             key="pf_config_upload", on_change=on_pf_config_upload, label_visibility="collapsed")
            pf_config = st.text_area("Or paste config content", value=st.session_state["pf_config_data"],
                                     height=130, key="pf_config_area",
                                     placeholder="params {\n  genome = 'GRCh38'\n  max_memory = '32.GB'\n}")
            if pf_config and pf_config != st.session_state["pf_config_data"]:
                st.session_state["pf_config_data"] = pf_config

        pf_work_dir = st.text_input("📁 Work Directory Path", value=".",
                                    help="Where Nextflow work dir will be created")

        if st.button("🚀 Run Pre-Flight Check", type="primary", key="run_preflight", use_container_width=True):
            sheet_text = st.session_state["pf_sheet_data"] or pf_sheet
            config_text = st.session_state["pf_config_data"] or pf_config
            if not sheet_text and not config_text:
                st.warning("Provide at least a sample sheet or nextflow.config.")
            else:
                result = run_preflight(samplesheet_text=sheet_text or None,
                                      config_text=config_text or None, work_dir=pf_work_dir or ".")
                st.session_state["preflight_result"] = result

    with col_side:
        st.markdown(info_card_html(), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""<div class="info-card"><h4>💡 Pro Tip</h4>
            <p style="font-size:0.85rem;color:#6B7280;margin:0">Keep your config and sample sheet version-controlled for reproducibility.</p>
        </div>""", unsafe_allow_html=True)

    # Results
    if st.session_state["preflight_result"] is not None:
        result = st.session_state["preflight_result"]
        v = result["verdict"]

        st.markdown(verdict_banner(v, result["verdict_message"]), unsafe_allow_html=True)

        s = result["summary"]
        cols = st.columns(4, gap="medium")
        cols[0].markdown(stat_card(s["pass"], "Passed", "#10B981"), unsafe_allow_html=True)
        cols[1].markdown(stat_card(s["warn"], "Warnings", "#F59E0B"), unsafe_allow_html=True)
        cols[2].markdown(stat_card(s["fail"], "Failed", "#EF4444"), unsafe_allow_html=True)
        cols[3].markdown(stat_card(s["skip"], "Skipped", "#8B5CF6"), unsafe_allow_html=True)

        settings = result.get("config_settings", {})
        if settings and any(val is not None for val in settings.values()):
            st.markdown(section_header("⚙️", "Detected Configuration"), unsafe_allow_html=True)
            sc = st.columns(4, gap="medium")
            sc[0].markdown(stat_card(f"{settings['max_memory']} GB" if settings.get('max_memory') else "—", "Memory", "#6C5CE7"), unsafe_allow_html=True)
            sc[1].markdown(stat_card(settings.get('max_cpus') or "—", "CPUs", "#6C5CE7"), unsafe_allow_html=True)
            sc[2].markdown(stat_card(settings.get('genome') or "—", "Genome", "#6C5CE7"), unsafe_allow_html=True)
            sc[3].markdown(stat_card(settings.get('container_engine') or "—", "Engine", "#6C5CE7"), unsafe_allow_html=True)

        ss = result.get("sheet_summary")
        if ss:
            st.markdown(section_header("📋", "Sample Sheet"), unsafe_allow_html=True)
            sc2 = st.columns(4, gap="medium")
            sc2[0].markdown(stat_card(ss["total_samples"], "Samples", "#10B981"), unsafe_allow_html=True)
            sc2[1].markdown(stat_card(ss["unique_samples"], "Unique IDs", "#10B981"), unsafe_allow_html=True)
            sc2[2].markdown(stat_card(ss["paired_end"], "Paired-end", "#6C5CE7"), unsafe_allow_html=True)
            sc2[3].markdown(stat_card(ss["single_end"], "Single-end", "#6C5CE7"), unsafe_allow_html=True)

        st.markdown(section_header("🔍", "Detailed Results"), unsafe_allow_html=True)
        failed = [c for c in result["checks"] if c["status"] == "fail"]
        warned = [c for c in result["checks"] if c["status"] == "warn"]
        passed = [c for c in result["checks"] if c["status"] == "pass"]
        skipped = [c for c in result["checks"] if c["status"] == "skip"]

        for ck in failed:
            st.markdown(check_html("fail", ck['check'], ck['message']), unsafe_allow_html=True)
            if ck.get("details"):
                with st.expander("Show details"):
                    for d in ck["details"]: st.code(d, language=None)
        for ck in warned:
            st.markdown(check_html("warn", ck['check'], ck['message']), unsafe_allow_html=True)
        if passed:
            with st.expander(f"✅ Passed ({len(passed)})"):
                for ck in passed:
                    st.markdown(check_html("pass", ck['check'], ck['message']), unsafe_allow_html=True)
        if skipped:
            with st.expander(f"⏭️ Skipped ({len(skipped)})"):
                for ck in skipped:
                    st.markdown(check_html("skip", ck['check'], ck['message']), unsafe_allow_html=True)

    st.markdown('<div class="privacy-footer">🔒 Secure · Private · Your data stays with you</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — Log Analyzer
# ═══════════════════════════════════════════════════════════════════
with tab_log:
    st.markdown(section_header("🔬", "Nextflow Log Analysis"), unsafe_allow_html=True)

    if ml_model is None:
        st.markdown('<div class="card card-warning">⚠️ No trained model found. Run <code>python src/train.py --n_per_category 200</code></div>', unsafe_allow_html=True)

    col_up, col_demo = st.columns([5, 1])
    with col_demo:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Demo", key="demo_log"):
            if DEMO_LOG.exists(): st.session_state["log_data"] = DEMO_LOG.read_text()

    st.file_uploader("Upload .nextflow.log", type=["log", "txt"], key="log_upload", on_change=on_log_upload)
    log_text = st.text_area("Or paste log contents:", value=st.session_state["log_data"], height=190,
                            placeholder="Paste your .nextflow.log contents here...")
    if log_text and log_text != st.session_state["log_data"]: st.session_state["log_data"] = log_text
    analysis_text = st.session_state["log_data"] or log_text

    if st.button("🔍 Analyze Log", type="primary", key="analyze_log", use_container_width=True):
        if not analysis_text.strip():
            st.warning("Please provide a log to analyze.")
        else:
            parsed = parse_nextflow_log(analysis_text)
            ml_result = ml_model.explain(analysis_text) if ml_model else None
            st.session_state["log_result"] = (parsed, ml_result, analysis_text)

    if st.session_state["log_result"] is not None:
        parsed, ml_result, original_text = st.session_state["log_result"]

        st.markdown(section_header("📊", "Run Metadata"), unsafe_allow_html=True)
        meta = parsed["meta"]
        mc = st.columns(3, gap="medium")
        mc[0].markdown(stat_card(meta["pipeline"] or "—", "Pipeline", "#6C5CE7"), unsafe_allow_html=True)
        mc[1].markdown(stat_card(meta["nf_version"] or "—", "NF Version", "#6C5CE7"), unsafe_allow_html=True)
        mc[2].markdown(stat_card(meta["revision"] or "—", "Revision", "#6C5CE7"), unsafe_allow_html=True)

        if meta["failed_process"]:
            st.markdown(f'<div class="card card-error">💥 <strong>Failed process:</strong> <code>{meta["failed_process"]}</code></div>', unsafe_allow_html=True)
        if meta["work_dir"]:
            st.markdown(f'<div class="process-bar">📁 {meta["work_dir"]}</div>', unsafe_allow_html=True)

        if parsed["processes"]:
            st.markdown(section_header("⚡", "Process Execution"), unsafe_allow_html=True)
            pc = st.columns(3, gap="medium")
            pc[0].markdown(stat_card(parsed["total_processes"], "Total", "#6C5CE7"), unsafe_allow_html=True)
            pc[1].markdown(stat_card(parsed["completed_processes"], "Completed", "#10B981"), unsafe_allow_html=True)
            pc[2].markdown(stat_card(parsed["failed_processes"], "Incomplete", "#EF4444"), unsafe_allow_html=True)
            for proc in parsed["processes"]:
                pct = proc["completed"] / proc["total"] if proc["total"] else 0
                icon = "✅" if proc["done"] else "❌"
                st.markdown(f'<div class="process-bar">[{proc["hash"]}] {proc["name"]} — {proc["completed"]}/{proc["total"]} {icon}</div>', unsafe_allow_html=True)
                st.progress(pct)

        st.markdown(section_header("🩺", "Diagnosis"), unsafe_allow_html=True)
        if ml_result is None:
            st.markdown('<div class="card card-warning">ML model not available.</div>', unsafe_allow_html=True)
        else:
            ml_label = ml_result["label"]
            ml_conf = ml_result["confidence"]

            if ml_label == "clean":
                st.markdown(verdict_banner("pass", f"🟢 Pipeline Healthy — no errors detected (confidence: {ml_conf:.0%})"), unsafe_allow_html=True)
            else:
                pattern = PATTERN_LOOKUP.get(ml_label, {})
                icon = pattern.get("icon", "⚠️")
                label = pattern.get("label", ml_label.replace("_", " ").title())
                severity = pattern.get("severity", "high")
                vtype = "fail" if severity in ("critical", "high") else "warn"

                st.markdown(verdict_banner(vtype, f"{icon} {label} — confidence: {ml_conf:.0%} {badge(severity, severity)}"), unsafe_allow_html=True)

                sc = st.columns(3, gap="medium")
                sc[0].markdown(stat_card(1 if severity == "critical" else 0, "Critical", "#EF4444"), unsafe_allow_html=True)
                sc[1].markdown(stat_card(1 if severity == "high" else 0, "High", "#F59E0B"), unsafe_allow_html=True)
                sc[2].markdown(stat_card(1 if severity == "medium" else 0, "Medium", "#6C5CE7"), unsafe_allow_html=True)

                if pattern:
                    st.markdown(section_header("📝", "Error Details"), unsafe_allow_html=True)
                    st.markdown(f"""<div class="card card-error">
                        <p style="margin:0 0 8px 0">{badge(severity, severity)} <strong>{label}</strong></p>
                        <p style="margin:0 0 6px 0;color:#4B5563"><strong>Cause:</strong> {pattern['cause']}</p>
                        <p style="margin:0;color:#4B5563"><strong>Fix:</strong> {pattern['fix']}</p>
                    </div>""", unsafe_allow_html=True)
                    st.code(pattern["command"], language="bash")

                    matched_lines = get_regex_details(ml_label, original_text)
                    if matched_lines:
                        st.markdown(section_header("📄", "Matched Log Lines"), unsafe_allow_html=True)
                        for ml_line in matched_lines:
                            st.markdown(f'<div class="process-bar">L{ml_line["line_num"]:>4} &nbsp;{ml_line["text"]}</div>', unsafe_allow_html=True)

                other_probs = {k: v for k, v in ml_result["probabilities"].items() if k != ml_label and k != "clean" and v > 0.05}
                if other_probs:
                    st.markdown(section_header("🔀", "Other Possible Issues"), unsafe_allow_html=True)
                    for al, ap in other_probs.items():
                        alt_pat = PATTERN_LOOKUP.get(al, {})
                        with st.expander(f"{alt_pat.get('icon', '⚠️')} {alt_pat.get('label', al)} — {ap:.0%}"):
                            if alt_pat:
                                st.markdown(f"**Cause:** {alt_pat['cause']}")
                                st.markdown(f"**Fix:** {alt_pat['fix']}")

                explanations = ml_result.get("shap_explanation", [])
                if explanations:
                    st.markdown(section_header("🧠", "Prediction Explanation"), unsafe_allow_html=True)
                    for feat in explanations[:8]:
                        name = feat.get("feature", "").replace("regex_", "Pattern: ")
                        imp = feat.get("importance", feat.get("shap_value", 0))
                        if imp > 0.001:
                            bw = min(int(imp * 400), 220)
                            st.markdown(f'<div class="feat-bar-container"><div class="feat-bar" style="width:{bw}px"></div><span class="feat-name">{name}</span></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — Sheet Validator
# ═══════════════════════════════════════════════════════════════════
with tab_sheet:
    st.markdown(section_header("📋", "Sample Sheet Validation"), unsafe_allow_html=True)

    col_sv, col_d2 = st.columns([5, 1])
    with col_d2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Demo", key="demo_sheet"):
            if DEMO_SHEET.exists(): st.session_state["sheet_data"] = DEMO_SHEET.read_text()

    st.file_uploader("Upload samplesheet.csv", type=["csv", "txt", "tsv"], key="sheet_upload", on_change=on_sheet_upload)
    sheet_text = st.text_area("Or paste CSV:", value=st.session_state["sheet_data"], height=170,
                              placeholder="sample,fastq_1,fastq_2,strandedness\n...")
    if sheet_text and sheet_text != st.session_state["sheet_data"]: st.session_state["sheet_data"] = sheet_text
    analysis_sheet = st.session_state["sheet_data"] or sheet_text

    if st.button("✅ Validate Sheet", type="primary", key="validate_sheet", use_container_width=True):
        if not analysis_sheet.strip(): st.warning("Please provide a sample sheet.")
        else:
            st.session_state["sheet_result"] = validate_sample_sheet(analysis_sheet)

    if st.session_state["sheet_result"] is not None:
        result = st.session_state["sheet_result"]
        if result["summary"]:
            sm = result["summary"]
            sc = st.columns(4, gap="medium")
            sc[0].markdown(stat_card(sm["total_samples"], "Samples", "#10B981"), unsafe_allow_html=True)
            sc[1].markdown(stat_card(sm["unique_samples"], "Unique IDs", "#10B981"), unsafe_allow_html=True)
            sc[2].markdown(stat_card(sm["paired_end"], "Paired-end", "#6C5CE7"), unsafe_allow_html=True)
            sc[3].markdown(stat_card(sm["single_end"], "Single-end", "#6C5CE7"), unsafe_allow_html=True)
            st.markdown(f'<div class="process-bar">Columns: {", ".join(sm["columns"])}</div>', unsafe_allow_html=True)

        issues = result["issues"]
        if issues:
            st.markdown(section_header("⚠️", f"Issues Found ({len(issues)})"), unsafe_allow_html=True)
            for iss in issues:
                t = iss["type"]
                css = "fail" if t == "critical" else ("warn" if t == "warning" else "skip")
                st.markdown(check_html(css, t.title(), iss["message"]), unsafe_allow_html=True)
        else:
            st.markdown(verdict_banner("pass", "🎉 Sample sheet is valid — no issues found"), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — Pattern Reference
# ═══════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown(section_header("📖", "Error Pattern Reference"), unsafe_allow_html=True)
    st.caption("All error categories the ML model detects, with regex patterns for log line matching.")

    st.markdown(f"**Bulk RNA-seq Patterns** ({len(ERROR_PATTERNS)})")
    for pat in ERROR_PATTERNS:
        sev = pat["severity"]
        with st.expander(f"{pat['icon']}  {pat['label']}  —  {badge(sev, sev)}", expanded=False):
            st.markdown(f"""<div class="card card-info">
                <p style="margin:0 0 6px 0;color:#374151"><strong>Cause:</strong> {pat['cause']}</p>
                <p style="margin:0;color:#374151"><strong>Fix:</strong> {pat['fix']}</p>
            </div>""", unsafe_allow_html=True)
            st.code(pat["command"], language="bash")
            st.markdown(f"**Regex patterns** ({len(pat['patterns'])}):")
            for p in pat["patterns"]:
                st.code(p.pattern, language=None)

    st.markdown(f"**scRNA-seq Patterns** ({len(SCRNA_PATTERNS)})")
    for pat in SCRNA_PATTERNS:
        sev = pat["severity"]
        with st.expander(f"{pat['icon']}  {pat['label']}  —  {badge(sev, sev)}", expanded=False):
            st.markdown(f"""<div class="card card-info">
                <p style="margin:0 0 6px 0;color:#374151"><strong>Cause:</strong> {pat['cause']}</p>
                <p style="margin:0;color:#374151"><strong>Fix:</strong> {pat['fix']}</p>
            </div>""", unsafe_allow_html=True)
            st.code(pat["command"], language="bash")
            st.markdown(f"**Regex patterns** ({len(pat['patterns'])}):")
            for p in pat["patterns"]:
                st.code(p.pattern, language=None)
