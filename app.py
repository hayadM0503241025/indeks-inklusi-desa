import streamlit as st
import pandas as pd
import numpy as np
import os
import base64
from io import BytesIO
import networkx as nx
from community import community_louvain
import plotly.graph_objects as go
import plotly.io as pio
import plotly.express as px

# =========================================================
# 1. KONFIGURASI TEMA & UI DDP (WHITE SIDEBAR STANDARD)
# =========================================================
LOGO_PATH = os.path.join("assets", "logo-banner2.png")
HEADER_PATH = next(
    (
        p
        for p in [
            os.path.join("assets", "header.png"),
            os.path.join("assets", "header.jpg"),
            os.path.join("assets", "header.jpeg"),
        ]
        if os.path.exists(p)
    ),
    None,
)
FRAME_PATH = os.path.join("assets", "frame.png") if os.path.exists(os.path.join("assets", "frame.png")) else None

# Jika file logo ada di assets, pakai itu. Jika tidak, pakai icon default sementara.
if os.path.exists(LOGO_PATH):
    page_icon = LOGO_PATH
else:
    page_icon = "SNA"


def get_image_data_uri(path):
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg" if ext in {".jpg", ".jpeg"} else "application/octet-stream"
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return None


def get_logo_data_uri(path):
    if not os.path.exists(path):
        return None
    return get_image_data_uri(path)

st.set_page_config(
    page_title="DDP Dashboard SNA",
    page_icon=page_icon,
    layout="wide"
)

DDP_BLUE = "#111827"
DDP_RED = "#B91C1C"
LIGHT_BG = "#EEF2F7"

# Skala Warna High-Contrast Satelit (Red -> Yellow -> Cyan)
SATELLITE_COLORS = [[0, DDP_RED], [0.5, "yellow"], [1, "cyan"]]
CONTRAST_COLORS = [
    "#E6194B", "#3CB44B", "#4363D8", "#F58231", "#911EB4",
    "#46F0F0", "#F032E6", "#BCF60C", "#FABEBE", "#008080",
    "#E6BEFF", "#9A6324", "#FFFAC8", "#800000", "#AAFFC3",
    "#808000", "#000075", "#808080"
]
PLOTLY_DRAW_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": ["drawrect", "drawline", "drawopenpath", "drawclosedpath", "drawcircle", "eraseshape"],
}
BINARY_COLOR_MAP = {"YA": "#00D4FF", "TIDAK": DDP_RED}
BANSOS_TARGETING_COLORS = {
    "Rendah - Penerima": "#0f766e",
    "Rendah - Belum Menerima": "#b91c1c",
    "Sedang - Penerima": "#14b8a6",
    "Sedang - Belum Menerima": "#f59e0b",
    "Tinggi - Penerima": "#2563eb",
    "Tinggi - Belum Menerima": "#64748b",
    "Sangat Tinggi - Penerima": "#7c3aed",
    "Sangat Tinggi - Belum Menerima": "#94a3b8",
    "Tidak Valid": "#cbd5e1",
}
BPS_CATEGORY_COLORS = {
    "Rendah": "#b91c1c",
    "Sedang": "#f59e0b",
    "Tinggi": "#16a34a",
    "Sangat Tinggi": "#2563eb",
    "Tidak Valid": "#94a3b8",
}
PLOT_TEXT_COLOR = "#0f172a"
PLOT_GRID_COLOR = "#cbd5e1"
HEADER_DATA_URI = get_image_data_uri(HEADER_PATH)
FRAME_DATA_URI = get_image_data_uri(FRAME_PATH)
KPI_FRAME_STYLE = (
    f"""
        border: none;
        border-radius: 0;
        padding: 18px 12px 14px 12px;
        background-image: url('{FRAME_DATA_URI}');
        background-size: 100% 100%;
        background-repeat: no-repeat;
        background-position: center;
    """
    if FRAME_DATA_URI
    else """
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 18px;
        padding: 18px 14px;
    """
)


def render_global_header():
    if not HEADER_DATA_URI:
        return
    st.markdown(
        f"""
        <div class="global-header-wrap">
            <img src="{HEADER_DATA_URI}" class="global-header-img" alt="Dashboard Header"/>
        </div>
        """,
        unsafe_allow_html=True,
    )


def subbab_dropdown(title, expanded=False):
    return st.expander(title, expanded=expanded)


pio.templates["ddp_clarity"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(255,255,255,0.0)",
        plot_bgcolor="rgba(248,250,252,0.85)",
        font=dict(color=PLOT_TEXT_COLOR, size=14),
        title=dict(font=dict(color=PLOT_TEXT_COLOR, size=18)),
        legend=dict(
            bgcolor="rgba(255,255,255,0.78)",
            bordercolor="#cbd5e1",
            borderwidth=1,
            font=dict(color=PLOT_TEXT_COLOR),
        ),
        xaxis=dict(
            color=PLOT_TEXT_COLOR,
            gridcolor=PLOT_GRID_COLOR,
            zerolinecolor="#94a3b8",
            linecolor="#334155",
            ticks="outside",
        ),
        yaxis=dict(
            color=PLOT_TEXT_COLOR,
            gridcolor=PLOT_GRID_COLOR,
            zerolinecolor="#94a3b8",
            linecolor="#334155",
            ticks="outside",
        ),
        coloraxis=dict(
            colorbar=dict(
                tickfont=dict(color=PLOT_TEXT_COLOR),
                title=dict(font=dict(color=PLOT_TEXT_COLOR)),
            )
        ),
    )
)
pio.templates.default = "ddp_clarity"

st.markdown(f"""
    <style>
    :root {{
        --surface: rgba(255, 255, 255, 0.88);
        --surface-strong: rgba(255, 255, 255, 0.96);
        --stroke: rgba(15, 23, 42, 0.12);
        --shadow: 0 18px 45px rgba(15, 23, 42, 0.10);
        --text-main: {DDP_BLUE};
        --accent: #2563EB;
    }}
    .stApp {{
        font-family: "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Segoe UI", sans-serif;
        background:
            radial-gradient(1200px 460px at 5% -10%, rgba(37, 99, 235, 0.13) 0%, rgba(37, 99, 235, 0) 62%),
            radial-gradient(900px 420px at 98% 0%, rgba(15, 23, 42, 0.08) 0%, rgba(15, 23, 42, 0) 65%),
            linear-gradient(180deg, {LIGHT_BG} 0%, #F8FAFC 60%, #FFFFFF 100%);
    }}
    .main .block-container {{
        max-width: 1400px;
        padding-top: 1.1rem;
        padding-bottom: 1.6rem;
    }}
    .global-header-wrap {{
        width: 100%;
        border-radius: 0;
        overflow: hidden;
        margin: 0.1rem 0 1.0rem 0;
        border: 1px solid rgba(15, 23, 42, 0.10);
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.16);
        background: rgba(255,255,255,0.82);
    }}
    .global-header-img {{
        width: 100%;
        display: block;
        object-fit: cover;
    }}
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0F172A 0%, #111827 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.10);
    }}
    section[data-testid="stSidebar"] * {{
        color: #E5E7EB !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"] > div,
    section[data-testid="stSidebar"] .stSlider {{
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px !important;
    }}
    .sidebar-logo-shell {{
        width: 62px;
        height: 62px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.42);
        background: linear-gradient(145deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.06) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.24), 0 8px 20px rgba(2,6,23,0.34);
    }}
    .sidebar-logo-disc {{
        width: 48px;
        height: 48px;
        border-radius: 999px;
        background: #FFFFFF;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid #E5E7EB;
        overflow: hidden;
    }}
    .sidebar-logo-img {{
        width: 36px;
        height: 36px;
        object-fit: contain;
        display: block;
    }}
    .sidebar-logo-fallback {{
        color: #111827 !important;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }}
    section[data-testid="stSidebar"] div[data-testid="stFileUploader"] {{
        margin-top: 0.15rem;
    }}
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
        background: rgba(148,163,184,0.14) !important;
        border: 1px solid rgba(255,255,255,0.28) !important;
        border-radius: 14px !important;
        padding: 0.75rem 0.7rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {{
        background: rgba(148,163,184,0.20) !important;
        border-color: rgba(255,255,255,0.42) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] span,
    section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] small {{
        color: #E5E7EB !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stFileUploaderFileName"] {{
        color: #F8FAFC !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {{
        background: rgba(255,255,255,0.10) !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255,255,255,0.26) !important;
        border-radius: 10px !important;
    }}
    .kpi-card {{
        {KPI_FRAME_STYLE}
        min-height: 132px;
        border-radius: 0;
        color: #F8FAFC;
        text-align: center;
        box-shadow: var(--shadow);
        margin-bottom: 14px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }}
    .kpi-card h3 {{
        margin: 0 0 6px 0;
        font-size: 1.7rem;
        line-height: 1.05;
        letter-spacing: 0.3px;
        font-weight: 700;
    }}
    .kpi-card p {{
        margin: 0;
        font-size: 0.82rem;
        letter-spacing: 0.4px;
        opacity: 0.96;
    }}
    .bg-ddp-blue {{
        background-color: #1E293B;
    }}
    .bg-ddp-red {{
        background-color: #991B1B;
    }}
    .main-header {{
        color: var(--text-main);
        font-family: "SF Pro Display", "Helvetica Neue", sans-serif;
        font-weight: 700;
        letter-spacing: 0.2px;
        border-bottom: 1px solid rgba(15, 23, 42, 0.16);
        padding-bottom: 10px;
        margin-bottom: 14px;
    }}
    .soft-card {{
        background: var(--surface);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--stroke);
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 14px;
        box-shadow: var(--shadow);
    }}
    .premium-hero {{
        background:
            linear-gradient(130deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.92) 70%),
            radial-gradient(circle at 85% 20%, rgba(37, 99, 235, 0.35) 0%, rgba(37, 99, 235, 0) 52%);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 20px;
        color: #F8FAFC;
        padding: 16px 20px;
        margin-bottom: 14px;
        box-shadow: 0 16px 40px rgba(2, 6, 23, 0.30);
    }}
    .premium-hero b {{
        color: #FFFFFF;
    }}
    @media (max-width: 768px) {{
        .kpi-card {{ min-height: 116px; border-radius: 0; }}
        .main-header {{ font-size: 1.2rem; }}
        .stats-container {{ font-size: 12px; }}
    }}
    .stats-container {{
        background: var(--surface-strong);
        padding: 22px;
        border-radius: 14px;
        border: 1px solid var(--stroke);
        font-family: "SF Mono", "JetBrains Mono", "Consolas", monospace;
        color: #1F2937;
        line-height: 1.5;
        font-size: 14px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }}
    .explanation-pillar {{
        padding: 20px;
        border-radius: 14px;
        border: 1px solid var(--stroke);
        background: var(--surface-strong);
        min-height: 180px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        margin-bottom: 15px;
    }}
    div[data-testid="stPlotlyChart"] {{
        background: var(--surface-strong);
        border: 1px solid var(--stroke);
        border-radius: 16px;
        padding: 8px 10px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06) !important;
    }}
    .streamlit-expanderHeader {{
        background: var(--surface-strong);
        border-radius: 14px;
        border: 1px solid var(--stroke);
        padding: 0.2rem 0.4rem;
        font-weight: 700;
        color: var(--text-main);
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.06);
        border: 1px solid rgba(15, 23, 42, 0.12);
        padding: 7px 14px;
    }}
    .stTabs [aria-selected="true"] {{
        background: #0F172A !important;
        color: #F8FAFC !important;
        border-color: #0F172A !important;
    }}
    div[data-testid="stMetric"] {{
        background: var(--surface);
        border: 1px solid var(--stroke);
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }}
    </style>
    """, unsafe_allow_html=True)

BUILDER_GRAPH_COLS = ("ipm_mikro", "dusun", "organisasi_num")
EDGE_REKAP_COLS = (
    "f_a_dari_rekap_kk",
    "f_b_dari_rekap_kk",
    "f_c_dari_rekap_kk",
    "f_d_dari_rekap_kk",
    "f_e_dari_rekap_kk",
)
IKR_DIMENSION_MAP = (
    ("F_A (Sandang, Pangan, Papan)", "f_a_dari_rekap_kk"),
    ("F_B (Pendidikan)", "f_b_dari_rekap_kk"),
    ("F_C (Sosial, Hukum, HAM)", "f_c_dari_rekap_kk"),
    ("F_D (Kesehatan & Pekerjaan)", "f_d_dari_rekap_kk"),
    ("F_E (Lingkungan & Infrastruktur)", "f_e_dari_rekap_kk"),
)
IKR_OVERALL_METRIC = ("F_IKR Agregat (Keseluruhan)", "f_ikr_dari_rekap_kk")
DRILLDOWN_DIMENSIONS = {
    "A": {
        "label": "Dimensi A (Sandang, Pangan, Papan)",
        "aggregate_col": "f_a_dari_rekap_kk",
        "variables": [
            {
                "code": "A1",
                "label": "A1 - Sandang",
                "description": "Seberapa sering keluarga membeli pakaian baru (indikator gaya hidup).",
                "candidates": ["a1_sandang", "a1", "f_a1", "f_a_1", "sandang"],
            },
            {
                "code": "A2",
                "label": "A2 - Pangan",
                "description": "Frekuensi makan dan gizi menu harian (indikator ketahanan pangan mikro).",
                "candidates": ["a2_pangan", "a2", "f_a2", "f_a_2", "pangan"],
            },
            {
                "code": "A3",
                "label": "A3 - Papan",
                "description": "Kualitas lantai, dinding, atap, dan sanitasi rumah (indikator aset fisik).",
                "candidates": ["a3_papan", "a3", "f_a3", "f_a_3", "papan"],
            },
        ],
    },
    "B": {
        "label": "Dimensi B (Pendidikan)",
        "aggregate_col": "f_b_dari_rekap_kk",
        "variables": [
            {
                "code": "B1",
                "label": "B1 - Lama Sekolah",
                "description": "Capaian ijazah KK (indikator modal intelektual).",
                "candidates": ["b1_lama_sekolah", "b1", "f_b1", "f_b_1", "lama_sekolah"],
            },
            {
                "code": "B2",
                "label": "B2 - Partisipasi",
                "description": "Status sekolah anggota keluarga (indikator keberlanjutan pendidikan).",
                "candidates": ["b2_partisipasi", "b2", "f_b2", "f_b_2", "partisipasi_sekolah"],
            },
        ],
    },
    "C": {
        "label": "Dimensi C (Sosial & Hukum)",
        "aggregate_col": "f_c_dari_rekap_kk",
        "variables": [
            {
                "code": "C1",
                "label": "C1 - Kehidupan Sosial",
                "description": "Akses bansos dan partisipasi organisasi (indikator inklusi kebijakan).",
                "candidates": ["c1_kehidupan_sosial", "c1", "f_c1", "f_c_1", "kehidupan_sosial"],
            },
            {
                "code": "C2",
                "label": "C2 - Hukum & HAM",
                "description": "Pengalaman kriminalitas dan bantuan hukum (indikator keamanan).",
                "candidates": ["c2_hukum_ham", "c2", "f_c2", "f_c_2", "hukum_ham"],
            },
        ],
    },
    "D": {
        "label": "Dimensi D (Kesehatan & Pekerjaan)",
        "aggregate_col": "f_d_dari_rekap_kk",
        "variables": [
            {
                "code": "D1",
                "label": "D1 - Kesehatan",
                "description": "Riwayat penyakit berat dan disabilitas (indikator kerentanan fisik).",
                "candidates": ["d1_kesehatan", "d1", "f_d1", "f_d_1", "kesehatan"],
            },
            {
                "code": "D2",
                "label": "D2 - Pekerjaan",
                "description": "Status bekerja dan keterampilan (indikator produktivitas ekonomi).",
                "candidates": ["d2_pekerjaan", "d2", "f_d2", "f_d_2", "pekerjaan"],
            },
            {
                "code": "D3",
                "label": "D3 - Jaminan Sosial",
                "description": "Kepesertaan BPJS/JKN (indikator jaring pengaman).",
                "candidates": ["d3_jaminan_sosial", "d3", "f_d3", "f_d_3", "jaminan_sosial", "bpjs"],
            },
        ],
    },
    "E": {
        "label": "Dimensi E (Lingkungan & Infrastruktur)",
        "aggregate_col": "f_e_dari_rekap_kk",
        "variables": [
            {
                "code": "E1",
                "label": "E1 - Lingkungan",
                "description": "Sumber air bersih dan pengelolaan sampah (indikator sanitasi lingkungan).",
                "candidates": ["e1_lingkungan", "e1", "f_e1", "f_e_1", "lingkungan"],
            },
            {
                "code": "E2",
                "label": "E2 - Infrastruktur",
                "description": "Akses listrik, ponsel, dan transportasi (indikator konektivitas digital).",
                "candidates": ["e2_infrastruktur", "e2", "f_e2", "f_e_2", "infrastruktur"],
            },
        ],
    },
}
def _normalize_text(val):
    return str(val).strip().lower() if pd.notnull(val) else ""


def to_binary_presence(val):
    v = _normalize_text(val)
    if v in {"0", "0.0", "tidak", "tidak ada", "none", "nan", ""}:
        return 0
    return 1


def to_binary_phone(val):
    v = _normalize_text(val)
    if v in {"ya", "yes", "1", "1.0", "true"}:
        return 1
    if v in {"tidak", "no", "0", "0.0", "false", "tidak ada", "none", "nan", ""}:
        return 0
    return 0


def _safe_float_metric(val, default=0.0):
    try:
        fval = float(val)
        return fval if np.isfinite(fval) else float(default)
    except Exception:
        return float(default)


def resolve_basis_column(df_in, preferred_col):
    if preferred_col in df_in.columns:
        return preferred_col
    numeric_candidates = []
    for c in df_in.columns:
        if c in {"family_id", "cluster", "bansos_num", "digital_num", "organisasi_num"}:
            continue
        s = pd.to_numeric(df_in[c], errors="coerce")
        if s.notna().sum() >= max(3, int(0.2 * len(df_in))):
            numeric_candidates.append(c)
    priority = ["f_ikr_dari_rekap_kk", "ipm_mikro", "indeks_pengeluaran", "indeks_kesehatan", "indeks_pendidikan"]
    for p in priority:
        if p in numeric_candidates:
            return p
    return numeric_candidates[0] if numeric_candidates else None


def build_onehot_feature_matrix(df_builder, feature_cols, rounding_decimals=2):
    if not feature_cols:
        return pd.DataFrame(np.zeros((len(df_builder), 1)), columns=["__no_feature_cols__"], index=df_builder.index)
    rounding_decimals = int(rounding_decimals) if pd.notnull(rounding_decimals) else 2
    rounding_decimals = 2 if rounding_decimals not in {0, 1, 2} else rounding_decimals
    feat_df = df_builder[list(feature_cols)].copy()
    for col in feature_cols:
        # Jika numerik, bulatkan dulu sesuai opsi desimal agar kategori one-hot lebih stabil.
        raw_col = feat_df[col].replace(["", "nan", "None", "none"], np.nan)
        num_col = pd.to_numeric(raw_col, errors="coerce")
        if num_col.notna().any():
            fmt_num = num_col.round(rounding_decimals).map(
                lambda x: f"{x:.{rounding_decimals}f}" if pd.notnull(x) else "__MISSING__"
            )
            fmt_raw = raw_col.astype("string").fillna("__MISSING__")
            feat_df[col] = np.where(num_col.notna(), fmt_num, fmt_raw)
        else:
            feat_df[col] = raw_col.astype("string").fillna("__MISSING__")
    dummies = pd.get_dummies(
        feat_df,
        columns=list(feature_cols),
        prefix=list(feature_cols),
        prefix_sep="=",
        dummy_na=False,
        dtype=float,
    )
    if dummies.empty:
        return pd.DataFrame(np.zeros((len(df_builder), 1)), columns=["__all_missing__"], index=df_builder.index)
    return dummies

def compute_cosine_similarity(vec_i, vec_j):
    denom = float(np.linalg.norm(vec_i) * np.linalg.norm(vec_j))
    if denom <= 1e-12:
        return 0.0
    return float(np.clip(np.dot(vec_i, vec_j) / denom, 0.0, 1.0))


def compute_jaccard_similarity(vec_i, vec_j):
    b_i = vec_i > 0
    b_j = vec_j > 0
    union = int(np.logical_or(b_i, b_j).sum())
    if union == 0:
        return 0.0
    inter = int(np.logical_and(b_i, b_j).sum())
    return float(inter / union)


def compute_pearson_similarity(vec_i, vec_j):
    std_i = float(np.std(vec_i))
    std_j = float(np.std(vec_j))
    if std_i <= 1e-12 or std_j <= 1e-12:
        return 0.0
    corr = float(np.corrcoef(vec_i, vec_j)[0, 1])
    if not np.isfinite(corr):
        return 0.0
    return float(corr)


def compute_auto_threshold_from_distribution(sim_values, threshold_grid=None):
    if threshold_grid is None:
        threshold_grid = [round(x, 1) for x in np.arange(0.1, 1.0, 0.1)]
    sim_series = pd.Series(sim_values, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    if sim_series.empty:
        n_candidates = max(len(threshold_grid), 1)
        table = [
            {
                "threshold": float(t),
                "edge_count": 0,
                "total_edge_kumulatif": 0,
                "rata2_edge_umum_total_bagi_kandidat": 0.0,
                "jumlah_kandidat_threshold": int(n_candidates),
            }
            for t in threshold_grid
        ]
        return 0.4, table
    counts = []
    for t in threshold_grid:
        counts.append(int((sim_series >= float(t)).sum()))
    n_candidates = max(len(threshold_grid), 1)
    total_edge_kumulatif = int(np.sum(counts))
    target_count = float(total_edge_kumulatif / n_candidates)
    best_idx = min(range(len(threshold_grid)), key=lambda i: (abs(counts[i] - target_count), abs(threshold_grid[i] - 0.5)))
    table = [
        {
            "threshold": float(threshold_grid[i]),
            "edge_count": int(counts[i]),
            "jarak_ke_rata2_edge": float(abs(counts[i] - target_count)),
            "total_edge_kumulatif": int(total_edge_kumulatif),
            "rata2_edge_umum_total_bagi_kandidat": float(target_count),
            "jumlah_kandidat_threshold": int(n_candidates),
        }
        for i in range(len(threshold_grid))
    ]
    return float(threshold_grid[best_idx]), table


def safe_numeric_assortativity(graph_obj, attr_name, default=0.0):
    if graph_obj is None or graph_obj.number_of_nodes() < 2 or graph_obj.number_of_edges() == 0:
        return float(default)
    raw_series = pd.Series({n: graph_obj.nodes[n].get(attr_name) for n in graph_obj.nodes()})
    num_series = pd.to_numeric(raw_series, errors="coerce")
    valid_nodes = [n for n in graph_obj.nodes() if pd.notnull(num_series.get(n))]
    if len(valid_nodes) < 2:
        return float(default)
    g_sub = graph_obj.subgraph(valid_nodes).copy()
    if g_sub.number_of_edges() == 0:
        return float(default)
    for n in g_sub.nodes():
        g_sub.nodes[n][attr_name] = float(num_series.get(n))
    vals = pd.Series([g_sub.nodes[n].get(attr_name) for n in g_sub.nodes()], dtype=float)
    if vals.nunique() <= 1:
        return float(default)
    try:
        return _safe_float_metric(nx.numeric_assortativity_coefficient(g_sub, attr_name), default=default)
    except Exception:
        return float(default)


def interpret_assortativity_value(r_val):
    r = _safe_float_metric(r_val, default=0.0)
    abs_r = abs(r)
    if abs_r < 0.10:
        level = "Sangat lemah"
    elif abs_r < 0.30:
        level = "Lemah"
    elif abs_r < 0.50:
        level = "Sedang"
    else:
        level = "Kuat"
    direction = "Asortatif" if r > 0 else "Disasortatif" if r < 0 else "Campuran/Acak"
    return direction, level


def safe_attribute_assortativity(graph_obj, attr_name, default=0.0):
    if graph_obj is None or graph_obj.number_of_nodes() < 2 or graph_obj.number_of_edges() == 0:
        return float(default)
    valid_nodes = [n for n in graph_obj.nodes() if pd.notnull(graph_obj.nodes[n].get(attr_name))]
    if len(valid_nodes) < 2:
        return float(default)
    g_sub = graph_obj.subgraph(valid_nodes).copy()
    if g_sub.number_of_edges() == 0:
        return float(default)
    vals = pd.Series([g_sub.nodes[n].get(attr_name) for n in g_sub.nodes()])
    if vals.nunique() <= 1:
        return float(default)
    try:
        return _safe_float_metric(nx.attribute_assortativity_coefficient(g_sub, attr_name), default=default)
    except Exception:
        return float(default)


def steinley_segregation_label(r_val):
    r_abs = abs(_safe_float_metric(r_val, default=0.0))
    if r_abs < 0.10:
        return "Low Segregation"
    if r_abs < 0.30:
        return "Moderate Segregation"
    return "High Segregation"


def interpret_q_strength(q_val):
    q = _safe_float_metric(q_val, default=0.0)
    a = abs(q)
    if a < 0.10:
        return "lemah"
    if a < 0.30:
        return "cukup"
    if a < 0.50:
        return "sedang"
    return "kuat"


def build_audit_auto_narrative(df_audit):
    if df_audit is None or df_audit.empty:
        return "Narasi audit belum dapat dibuat karena tabel audit kosong."
    lines = []
    for _, row in df_audit.iterrows():
        metric = row.get("Metrik", "-")
        r_val = _safe_float_metric(row.get("r"), default=0.0)
        qw_val = _safe_float_metric(row.get("Qw*"), default=0.0)
        qb_val = _safe_float_metric(row.get("Qb*"), default=0.0)
        dir_r, lvl_r = interpret_assortativity_value(r_val)
        if qw_val >= 0.10:
            intra_note = f"intra-klaster {interpret_q_strength(qw_val)} homogen"
        elif qw_val <= -0.10:
            intra_note = "intra-klaster cenderung lintas kategori"
        else:
            intra_note = "intra-klaster campuran/netral"
        if qb_val >= 0.10:
            inter_note = f"antar-klaster {interpret_q_strength(qb_val)} homogen"
        elif qb_val <= -0.10:
            inter_note = "antar-klaster cenderung berbeda kategori"
        else:
            inter_note = "antar-klaster campuran/netral"
        lines.append(
            f"- <b>{metric}</b>: r=<b>{r_val:.3f}</b> ({dir_r}, {lvl_r}); Qw*=<b>{qw_val:.3f}</b> ({intra_note}); Qb*=<b>{qb_val:.3f}</b> ({inter_note})."
        )
    return "<br>".join(lines)


def resolve_first_existing_column(df_columns, candidates):
    lookup = {str(c).lower().strip(): c for c in df_columns}
    for cand in candidates:
        key = str(cand).lower().strip()
        if key in lookup:
            return lookup[key]
    return None


def compute_assortativity_for_column(graph_obj, col_name):
    node_vals = [graph_obj.nodes[n].get(col_name) for n in graph_obj.nodes()]
    num_series = pd.to_numeric(pd.Series(node_vals), errors="coerce")
    if num_series.notna().sum() >= 3 and num_series.nunique(dropna=True) > 1:
        return safe_numeric_assortativity(graph_obj, col_name, default=0.0), "numeric"
    return safe_attribute_assortativity(graph_obj, col_name, default=0.0), "attribute"


def centrality_help_text(metric_key):
    mapping = {
        "degree": "Degree: seberapa banyak dan seberapa kuat koneksi langsung node.",
        "betweenness": "Betweenness: seberapa sering node menjadi jembatan jalur terpendek antar-node.",
        "closeness": "Closeness: seberapa dekat node ke node lain (rata-rata jarak paling pendek).",
        "eigenvector": "Eigenvector: node penting jika terhubung ke node penting lainnya.",
    }
    return mapping.get(metric_key, "-")


def compute_centrality_on_similarity_graph(graph_obj, metric_key):
    if graph_obj is None or graph_obj.number_of_nodes() == 0:
        return {}
    metric_key = str(metric_key).strip().lower()
    if metric_key == "degree":
        return {n: float(graph_obj.degree(n, weight="weight")) for n in graph_obj.nodes()}

    # Untuk metrik shortest-path, similarity diubah jadi jarak: distance = 1 / similarity.
    graph_dist = graph_obj.copy()
    for u, v, d in graph_dist.edges(data=True):
        w = _safe_float_metric(d.get("weight"), default=0.0)
        d["distance"] = 1.0 / max(w, 1e-9)

    if metric_key == "betweenness":
        return nx.betweenness_centrality(graph_dist, weight="distance", normalized=True)
    if metric_key == "closeness":
        return nx.closeness_centrality(graph_dist, distance="distance")
    if metric_key == "eigenvector":
        try:
            return nx.eigenvector_centrality_numpy(graph_obj, weight="weight")
        except Exception:
            return nx.eigenvector_centrality(graph_obj, weight="weight", max_iter=2000, tol=1e-6)
    return {}


def detect_lat_lon_columns(columns):
    lower_map = {str(c).lower().strip(): c for c in columns}
    lat_candidates = ["lat", "latitude", "lintang", "y", "coord_lat"]
    lon_candidates = ["lon", "lng", "long", "longitude", "bujur", "x", "coord_lon"]
    lat_col = next((lower_map[k] for k in lat_candidates if k in lower_map), None)
    lon_col = next((lower_map[k] for k in lon_candidates if k in lower_map), None)
    return lat_col, lon_col


def build_spatial_node_figure(
    graph_obj,
    node_ids,
    node_color_vals,
    node_hover_text,
    title,
    spatial_mode="Spasial OSM",
    marker_size=11,
    colorscale="Turbo",
    colorbar=None,
    cmin=None,
    cmax=None,
    line_color="#0f172a",
    line_width=0.6,
):
    if graph_obj is None or graph_obj.number_of_nodes() == 0:
        return None
    sample_cols = set()
    for n in graph_obj.nodes():
        sample_cols.update(graph_obj.nodes[n].keys())
        break
    lat_col, lon_col = detect_lat_lon_columns(sample_cols)
    if not lat_col or not lon_col:
        return None

    lats, lons, colors, hovers = [], [], [], []
    for idx, n in enumerate(node_ids):
        if n not in graph_obj.nodes():
            continue
        lat_v = _safe_float_metric(graph_obj.nodes[n].get(lat_col), default=np.nan)
        lon_v = _safe_float_metric(graph_obj.nodes[n].get(lon_col), default=np.nan)
        if not (np.isfinite(lat_v) and np.isfinite(lon_v)):
            continue
        lats.append(float(lat_v))
        lons.append(float(lon_v))
        colors.append(node_color_vals[idx] if idx < len(node_color_vals) else 0.0)
        hovers.append(node_hover_text[idx] if idx < len(node_hover_text) else f"Node: {n}")
    if len(lats) == 0:
        return None

    marker_cfg = dict(
        size=marker_size,
        color=colors,
        colorscale=colorscale,
        showscale=True,
    )
    if colorbar is not None:
        marker_cfg["colorbar"] = colorbar
    if cmin is not None:
        marker_cfg["cmin"] = cmin
    if cmax is not None:
        marker_cfg["cmax"] = cmax

    fig = go.Figure(
        go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode="markers",
            marker=marker_cfg,
            text=hovers,
            hoverinfo="text",
            showlegend=False,
        )
    )
    center_lat = float(np.mean(lats))
    center_lon = float(np.mean(lons))
    mapbox_cfg = dict(
        zoom=12,
        center=dict(lat=center_lat, lon=center_lon),
    )
    if spatial_mode == "Spasial ArcGIS":
        mapbox_cfg["style"] = "white-bg"
        mapbox_cfg["layers"] = [
            {
                "sourcetype": "raster",
                "source": ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                "below": "traces",
            }
        ]
    else:
        mapbox_cfg["style"] = "open-street-map"
    fig.update_layout(
        title=title,
        height=560,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        mapbox=mapbox_cfg,
    )
    return fig


def categorize_ikr_bps(score):
    s = _safe_float_metric(score, default=np.nan)
    if not np.isfinite(s):
        return ("Tidak Valid", 0)
    # Referensi BPS (2014): kategori capaian skor (skala 0-100).
    if s >= 80.0:
        return ("Sangat Tinggi", 4)
    if s >= 70.0:
        return ("Tinggi", 3)
    if s >= 60.0:
        return ("Sedang", 2)
    return ("Rendah", 1)


def add_bps_ikr_category(df_in, ikr_col="f_ikr_dari_rekap_kk"):
    if ikr_col not in df_in.columns:
        return df_in.copy()
    df_out = df_in.copy()
    mapped = df_out[ikr_col].apply(categorize_ikr_bps)
    df_out["kategori_ikr"] = mapped.apply(lambda x: x[0])
    df_out["kategori_ikr_code"] = mapped.apply(lambda x: int(x[1]))
    return df_out


def compute_montes_within_between_assortativity(
    graph_obj,
    category_attr="kategori_ikr_code",
    group_attr="cluster",
    invalid_category_values=None,
):
    # Referensi Montes et al. (2018): dekomposisi within-between berbasis delta kategorikal.
    if graph_obj is None or graph_obj.number_of_nodes() < 2 or graph_obj.number_of_edges() == 0:
        return {
            "q_w_star": 0.0,
            "q_b_star": 0.0,
            "m_w": 0.0,
            "m_b": 0.0,
            "n_nodes": int(graph_obj.number_of_nodes() if graph_obj is not None else 0),
            "n_edges": int(graph_obj.number_of_edges() if graph_obj is not None else 0),
        }

    nodes = list(graph_obj.nodes())
    k = {n: _safe_float_metric(graph_obj.degree(n, weight="weight"), default=0.0) for n in nodes}
    two_m = float(sum(k.values()))
    if two_m <= 1e-12:
        return {
            "q_w_star": 0.0,
            "q_b_star": 0.0,
            "m_w": 0.0,
            "m_b": 0.0,
            "n_nodes": int(graph_obj.number_of_nodes()),
            "n_edges": int(graph_obj.number_of_edges()),
        }

    m_w = 0.0
    m_b = 0.0
    k_w = {n: 0.0 for n in nodes}
    k_b = {n: 0.0 for n in nodes}
    for u, v, d in graph_obj.edges(data=True):
        w = _safe_float_metric(d.get("weight"), default=0.0)
        if graph_obj.nodes[u].get(group_attr) == graph_obj.nodes[v].get(group_attr):
            m_w += w
            k_w[u] += w
            k_w[v] += w
        else:
            m_b += w
            k_b[u] += w
            k_b[v] += w

    two_m_w = 2.0 * m_w
    two_m_b = 2.0 * m_b
    sum_w = 0.0
    sum_b = 0.0
    exp_w_masked = 0.0
    exp_b_masked = 0.0
    invalid_set = set() if invalid_category_values is None else set(invalid_category_values)
    for i in nodes:
        xi = graph_obj.nodes[i].get(category_attr, 0)
        hi = graph_obj.nodes[i].get(group_attr, None)
        for j in nodes:
            xj = graph_obj.nodes[j].get(category_attr, 0)
            hj = graph_obj.nodes[j].get(group_attr, None)
            xi_valid = pd.notnull(xi) and xi not in invalid_set
            xj_valid = pd.notnull(xj) and xj not in invalid_set
            delta_x = 1.0 if xi_valid and xj_valid and xi == xj else 0.0
            delta_h = 1.0 if hi == hj else 0.0
            a_ij = _safe_float_metric(graph_obj[i][j].get("weight"), default=0.0) if graph_obj.has_edge(i, j) else 0.0
            expected_w = (k_w[i] * k_w[j] / two_m_w) if two_m_w > 1e-12 else 0.0
            expected_b = (k_b[i] * k_b[j] / two_m_b) if two_m_b > 1e-12 else 0.0
            mask_w = delta_x * delta_h
            mask_b = delta_x * (1.0 - delta_h)
            sum_w += (a_ij - expected_w) * mask_w
            sum_b += (a_ij - expected_b) * mask_b
            exp_w_masked += expected_w * mask_w
            exp_b_masked += expected_b * mask_b

    # Qw dan Qb raw sesuai pembagi 2m_w / 2m_b.
    q_w_raw = (sum_w / two_m_w) if two_m_w > 1e-12 else 0.0
    q_b_raw = (sum_b / two_m_b) if two_m_b > 1e-12 else 0.0

    # Normalisasi Montes (Pers. 6-7): Q* = Q / Qmax.
    # Qmax numerik dihitung dari: (2m - sum(expected_term_masked)).
    q_w_max_num = (two_m_w - exp_w_masked) if two_m_w > 1e-12 else 0.0
    q_b_max_num = (two_m_b - exp_b_masked) if two_m_b > 1e-12 else 0.0
    q_w_max = (q_w_max_num / two_m_w) if two_m_w > 1e-12 else 0.0
    q_b_max = (q_b_max_num / two_m_b) if two_m_b > 1e-12 else 0.0
    q_w_star = (q_w_raw / q_w_max) if abs(q_w_max) > 1e-12 else 0.0
    q_b_star = (q_b_raw / q_b_max) if abs(q_b_max) > 1e-12 else 0.0
    q_w_star = float(np.clip(q_w_star, -1.0, 1.0))
    q_b_star = float(np.clip(q_b_star, -1.0, 1.0))
    return {
        "q_w_star": float(q_w_star),
        "q_b_star": float(q_b_star),
        "q_w_raw": float(q_w_raw),
        "q_b_raw": float(q_b_raw),
        "q_w_max": float(q_w_max),
        "q_b_max": float(q_b_max),
        "m_w": float(m_w),
        "m_b": float(m_b),
        "n_nodes": int(graph_obj.number_of_nodes()),
        "n_edges": int(graph_obj.number_of_edges()),
    }


def build_category_connection_breakdown(
    graph_obj,
    category_attr="kategori_ikr",
    group_attr="cluster",
    category_order=None,
    invalid_label="Tidak Valid",
):
    if graph_obj is None or graph_obj.number_of_edges() == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    category_order = list(category_order or [])
    order_map = {str(cat): idx for idx, cat in enumerate(category_order)}

    def normalize_cat(val):
        if pd.isna(val):
            return invalid_label
        txt = str(val).strip()
        return txt if txt else invalid_label

    def sort_pair(cat_a, cat_b):
        idx_a = order_map.get(cat_a, len(order_map))
        idx_b = order_map.get(cat_b, len(order_map))
        return (cat_a, cat_b) if (idx_a, cat_a) <= (idx_b, cat_b) else (cat_b, cat_a)

    rows = []
    for u, v, d in graph_obj.edges(data=True):
        cat_u = normalize_cat(graph_obj.nodes[u].get(category_attr, invalid_label))
        cat_v = normalize_cat(graph_obj.nodes[v].get(category_attr, invalid_label))
        cat_a, cat_b = sort_pair(cat_u, cat_v)
        scope = "Within" if graph_obj.nodes[u].get(group_attr) == graph_obj.nodes[v].get(group_attr) else "Between"
        weight = _safe_float_metric(d.get("weight"), default=0.0)
        rows.append(
            {
                "Ruang": scope,
                "Kategori 1": cat_a,
                "Kategori 2": cat_b,
                "Pasangan": f"{cat_a} - {cat_b}",
                "Jenis Pasangan": "Sama" if cat_a == cat_b else "Beda",
                "Bobot Edge": weight,
                "Jumlah Edge": 1,
            }
        )

    if not rows:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_pairs = pd.DataFrame(rows)
    df_summary = (
        df_pairs.groupby(["Ruang", "Kategori 1", "Kategori 2", "Pasangan", "Jenis Pasangan"], as_index=False)
        .agg({"Bobot Edge": "sum", "Jumlah Edge": "sum"})
    )
    scope_weight = df_summary.groupby("Ruang")["Bobot Edge"].transform("sum")
    scope_edge = df_summary.groupby("Ruang")["Jumlah Edge"].transform("sum")
    df_summary["Persentase Bobot (%)"] = np.where(scope_weight > 0, (df_summary["Bobot Edge"] / scope_weight) * 100.0, 0.0)
    df_summary["Persentase Edge (%)"] = np.where(scope_edge > 0, (df_summary["Jumlah Edge"] / scope_edge) * 100.0, 0.0)
    df_summary["Urut 1"] = df_summary["Kategori 1"].map(lambda x: order_map.get(str(x), len(order_map)))
    df_summary["Urut 2"] = df_summary["Kategori 2"].map(lambda x: order_map.get(str(x), len(order_map)))
    df_summary = df_summary.sort_values(["Ruang", "Urut 1", "Urut 2", "Pasangan"]).reset_index(drop=True)

    matrix_rows = []
    for _, row in df_summary.iterrows():
        matrix_rows.append(
            {
                "Ruang": row["Ruang"],
                "Kategori Baris": row["Kategori 1"],
                "Kategori Kolom": row["Kategori 2"],
                "Persentase Bobot (%)": float(row["Persentase Bobot (%)"]),
            }
        )
        if row["Kategori 1"] != row["Kategori 2"]:
            matrix_rows.append(
                {
                    "Ruang": row["Ruang"],
                    "Kategori Baris": row["Kategori 2"],
                    "Kategori Kolom": row["Kategori 1"],
                    "Persentase Bobot (%)": float(row["Persentase Bobot (%)"]),
                }
            )
    df_matrix_long = pd.DataFrame(matrix_rows)
    return df_pairs, df_summary, df_matrix_long


def build_spatial_category_figure(
    df_map,
    lat_col,
    lon_col,
    category_col,
    hover_col,
    title,
    spatial_mode="Spasial ArcGIS",
    category_order=None,
    category_colors=None,
    marker_size=12,
):
    if df_map is None or df_map.empty or lat_col not in df_map.columns or lon_col not in df_map.columns:
        return None

    plot_df = df_map.copy()
    plot_df[category_col] = plot_df[category_col].fillna("Tidak Valid").astype(str)
    plot_df[lat_col] = pd.to_numeric(plot_df[lat_col], errors="coerce")
    plot_df[lon_col] = pd.to_numeric(plot_df[lon_col], errors="coerce")
    plot_df = plot_df[plot_df[lat_col].notna() & plot_df[lon_col].notna()].copy()
    if plot_df.empty:
        return None

    uniq = plot_df[category_col].unique().tolist()
    category_order = list(category_order or [])
    ordered_categories = [cat for cat in category_order if cat in uniq]
    ordered_categories += sorted([cat for cat in uniq if cat not in ordered_categories])
    category_colors = category_colors or {}

    fig = go.Figure()
    for idx, category in enumerate(ordered_categories):
        sub = plot_df[plot_df[category_col] == category]
        if sub.empty:
            continue
        fig.add_trace(
            go.Scattermapbox(
                lat=sub[lat_col],
                lon=sub[lon_col],
                mode="markers",
                marker=dict(
                    size=marker_size,
                    color=category_colors.get(category, CONTRAST_COLORS[idx % len(CONTRAST_COLORS)]),
                    opacity=0.90,
                ),
                name=category,
                text=sub[hover_col],
                hoverinfo="text",
            )
        )

    mapbox_cfg = dict(
        zoom=12,
        center=dict(
            lat=float(plot_df[lat_col].mean()),
            lon=float(plot_df[lon_col].mean()),
        ),
    )
    if spatial_mode == "Spasial ArcGIS":
        mapbox_cfg["style"] = "white-bg"
        mapbox_cfg["layers"] = [
            {
                "sourcetype": "raster",
                "source": ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                "below": "traces",
            }
        ]
    else:
        mapbox_cfg["style"] = "open-street-map"

    fig.update_layout(
        title=title,
        height=620,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            title=dict(text=category_col),
            orientation="h",
            yanchor="bottom",
            y=0.01,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.85)",
        ),
        mapbox=mapbox_cfg,
    )
    return fig


def build_spatial_numeric_figure(
    df_map,
    lat_col,
    lon_col,
    value_col,
    hover_col,
    title,
    spatial_mode="Spasial ArcGIS",
    marker_size_col=None,
    colorscale="RdYlGn",
    colorbar_title="Nilai",
):
    if df_map is None or df_map.empty or lat_col not in df_map.columns or lon_col not in df_map.columns:
        return None

    plot_df = df_map.copy()
    plot_df[lat_col] = pd.to_numeric(plot_df[lat_col], errors="coerce")
    plot_df[lon_col] = pd.to_numeric(plot_df[lon_col], errors="coerce")
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce")
    plot_df = plot_df[plot_df[lat_col].notna() & plot_df[lon_col].notna()].copy()
    if plot_df.empty:
        return None

    marker_size = 12
    if marker_size_col and marker_size_col in plot_df.columns:
        size_vals = pd.to_numeric(plot_df[marker_size_col], errors="coerce").fillna(0)
        marker_size = (size_vals.clip(lower=0) * 3) + 10

    fig = go.Figure(
        go.Scattermapbox(
            lat=plot_df[lat_col],
            lon=plot_df[lon_col],
            mode="markers",
            marker=dict(
                size=marker_size,
                color=plot_df[value_col],
                colorscale=colorscale,
                showscale=True,
                colorbar=dict(title=colorbar_title),
                cmin=float(plot_df[value_col].min()) if plot_df[value_col].notna().any() else 0.0,
                cmax=float(plot_df[value_col].max()) if plot_df[value_col].notna().any() else 100.0,
                opacity=0.92,
            ),
            text=plot_df[hover_col],
            hoverinfo="text",
            showlegend=False,
        )
    )

    mapbox_cfg = dict(
        zoom=12,
        center=dict(
            lat=float(plot_df[lat_col].mean()),
            lon=float(plot_df[lon_col].mean()),
        ),
    )
    if spatial_mode == "Spasial ArcGIS":
        mapbox_cfg["style"] = "white-bg"
        mapbox_cfg["layers"] = [
            {
                "sourcetype": "raster",
                "source": ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                "below": "traces",
            }
        ]
    else:
        mapbox_cfg["style"] = "open-street-map"

    fig.update_layout(
        title=title,
        height=620,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        mapbox=mapbox_cfg,
    )
    return fig


def render_bansos_spatial_analysis_page(
    df_v,
    graph_obj,
    partition,
    spatial_mode="Spasial ArcGIS",
    selected_dimension_col="f_a_dari_rekap_kk",
    map_color_mode="F_IKR Agregat",
    filter_mode="Semua KK",
    dim_thresholds=None,
):
    st.markdown("<h1 class='main-header'>Analisis Bansos Spasial</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='premium-hero'><b>Fokus Halaman:</b> memetakan penerima bansos berdasarkan "
        "dimensi IKR yang dipilih. Warna node selalu mengikuti <b>F_IKR agregat</b> sebagai tingkat "
        "kesejahteraan ekonomi, sedangkan detail hover menampilkan skor dimensi dan jenis bansos yang diterima.</div>",
        unsafe_allow_html=True,
    )

    if graph_obj is None or graph_obj.number_of_nodes() == 0:
        st.warning("Graf analisis belum tersedia.")
        return

    dim_thresholds = dim_thresholds or {}
    node_ids = list(graph_obj.nodes())
    df_nodes = (
        df_v[df_v["family_id"].isin(node_ids)]
        .drop_duplicates("family_id")
        .copy()
    )
    if df_nodes.empty:
        st.warning("Tidak ada node graf yang cocok dengan data desa terpilih.")
        return

    lat_col, lon_col = detect_lat_lon_columns(df_nodes.columns)
    raw_bansos_col = resolve_first_existing_column(df_nodes.columns, ["bansos", "keikutsertaan program bantuan", "program bantuan", "bantuan sosial", "bansos bantuan"])
    df_nodes["cluster"] = df_nodes["family_id"].map(lambda fid: int(partition.get(fid, -1)))
    df_nodes["Cluster Louvain"] = df_nodes["cluster"].map(lambda x: f"Klaster {x}" if x >= 0 else "Tidak Terklaster")
    df_nodes["Status Bansos"] = df_nodes["bansos_num"].apply(lambda x: "Penerima" if int(_safe_float_metric(x, default=0.0) > 0) == 1 else "Non-Penerima")
    df_nodes["F_IKR"] = pd.to_numeric(df_nodes.get("f_ikr_dari_rekap_kk"), errors="coerce")
    df_nodes["Jenis Bansos"] = (
        df_nodes[raw_bansos_col].astype(str).replace({"nan": "-", "None": "-", "none": "-", "": "-"}).fillna("-")
        if raw_bansos_col
        else "-"
    )

    dim_lookup = {col: label for label, col in IKR_DIMENSION_MAP}
    selected_dimension_label = dim_lookup.get(selected_dimension_col, selected_dimension_col)
    df_nodes["Skor Dimensi Pilihan"] = pd.to_numeric(df_nodes.get(selected_dimension_col), errors="coerce")
    selected_threshold = float(dim_thresholds.get(selected_dimension_col, 60.0))
    df_nodes["Status Dimensi Pilihan"] = np.where(
        df_nodes["Skor Dimensi Pilihan"].le(selected_threshold).fillna(False),
        f"Rentan {selected_dimension_label}",
        f"Tidak Rentan {selected_dimension_label}",
    )

    weak_dim_labels = []
    weak_dim_count = np.zeros(len(df_nodes), dtype=int)
    for dim_label, col_name in IKR_DIMENSION_MAP:
        thr = float(dim_thresholds.get(col_name, 60.0))
        dim_vals = pd.to_numeric(df_nodes.get(col_name), errors="coerce")
        weak_flag = (dim_vals <= thr).fillna(False)
        weak_dim_count += weak_flag.astype(int).to_numpy()
        weak_dim_labels.append(
            weak_flag.map(lambda x, lbl=dim_label: lbl if bool(x) else None)
        )
    weak_dim_df = pd.concat(weak_dim_labels, axis=1) if weak_dim_labels else pd.DataFrame(index=df_nodes.index)
    df_nodes["Jumlah Dimensi Rentan"] = weak_dim_count.astype(int)
    df_nodes["Dimensi Rentan"] = weak_dim_df.apply(
        lambda row: ", ".join([str(v) for v in row.tolist() if pd.notnull(v)]) if len(row) else "-",
        axis=1,
    )
    def classify_bps_bansos(row):
        kategori = str(row.get("kategori_ikr", "Tidak Valid"))
        status = str(row.get("Status Bansos", "Non-Penerima"))
        if kategori not in {"Rendah", "Sedang", "Tinggi", "Sangat Tinggi"}:
            return "Tidak Valid"
        return f"{kategori} - {'Penerima' if status == 'Penerima' else 'Belum Menerima'}"

    df_nodes["Status BPS-Bansos"] = df_nodes.apply(classify_bps_bansos, axis=1)
    df_nodes["Label Dimensi Rentan"] = df_nodes["Jumlah Dimensi Rentan"].map(lambda x: f"{int(x)} dimensi rentan")

    nx.set_node_attributes(
        graph_obj,
        df_nodes.set_index("family_id")[["kategori_ikr", "kategori_ikr_code"]].to_dict("index"),
    )
    montes_res = compute_montes_within_between_assortativity(
        graph_obj,
        category_attr="kategori_ikr_code",
        group_attr="cluster",
        invalid_category_values={0},
    )
    q_w_star = float(montes_res["q_w_star"])
    q_b_star = float(montes_res["q_b_star"])

    total_nodes = int(len(df_nodes))
    total_receiver = int((df_nodes["Status Bansos"] == "Penerima").sum())
    total_selected_dim_vulnerable = int(df_nodes["Status Dimensi Pilihan"].eq(f"Rentan {selected_dimension_label}").sum())
    total_rendah_terima = int((df_nodes["Status BPS-Bansos"] == "Rendah - Penerima").sum())
    total_rendah_belum = int((df_nodes["Status BPS-Bansos"] == "Rendah - Belum Menerima").sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Node Tersedia", total_nodes)
    k2.metric("Penerima Bansos", total_receiver)
    k3.metric(f"Rentan {selected_dimension_label}", total_selected_dim_vulnerable)
    k4.metric("Rendah - Penerima", total_rendah_terima)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Qw*", f"{q_w_star:.4f}")
    m2.metric("Qb*", f"{q_b_star:.4f}")
    m3.metric("Rendah - Belum Menerima", total_rendah_belum)
    m4.metric("Rata-rata Dimensi Rentan", f"{float(df_nodes['Jumlah Dimensi Rentan'].mean()):.2f}")

    st.markdown(
        f"<div class='soft-card'><b>Interpretasi Cepat:</b><br>"
        f"Qw* = <b>{q_w_star:.3f}</b> menunjukkan kekompakan kategori BPS di dalam klaster, "
        f"sedangkan Qb* = <b>{q_b_star:.3f}</b> membaca kemiripan strata BPS antar-klaster. "
        f"Pada page ini, <b>warna node memakai F_IKR agregat</b> sebagai base kesejahteraan ekonomi, "
        f"sedangkan analisis bansos dibaca dari dimensi terpilih <b>{selected_dimension_label}</b> "
        f"dengan ambang <b>{selected_threshold:.1f}</b>.</div>",
        unsafe_allow_html=True,
    )

    map_df = df_nodes.copy()
    if filter_mode == "Penerima Bansos":
        map_df = map_df[map_df["Status Bansos"] == "Penerima"].copy()
    elif filter_mode == "Rendah - Penerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Rendah - Penerima"].copy()
    elif filter_mode == "Rendah - Belum Menerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Rendah - Belum Menerima"].copy()
    elif filter_mode == "Sedang - Penerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Sedang - Penerima"].copy()
    elif filter_mode == "Sedang - Belum Menerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Sedang - Belum Menerima"].copy()
    elif filter_mode == "Tinggi - Penerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Tinggi - Penerima"].copy()
    elif filter_mode == "Tinggi - Belum Menerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Tinggi - Belum Menerima"].copy()
    elif filter_mode == "Sangat Tinggi - Penerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Sangat Tinggi - Penerima"].copy()
    elif filter_mode == "Sangat Tinggi - Belum Menerima":
        map_df = map_df[map_df["Status BPS-Bansos"] == "Sangat Tinggi - Belum Menerima"].copy()
    elif filter_mode == "Rentan Dimensi Terpilih":
        map_df = map_df[map_df["Status Dimensi Pilihan"] == f"Rentan {selected_dimension_label}"].copy()
    elif filter_mode == "Penerima pada Dimensi Terpilih":
        map_df = map_df[
            (map_df["Status Bansos"] == "Penerima")
            & (map_df["Status Dimensi Pilihan"] == f"Rentan {selected_dimension_label}")
        ].copy()

    df_nodes["nama"] = df_nodes.get("nama", df_nodes["family_id"]).astype(str)
    hover_text = []
    for _, row in map_df.iterrows():
        dim_lines = []
        for dim_label, col_name in IKR_DIMENSION_MAP:
            dim_lines.append(f"{dim_label}: {_safe_float_metric(row.get(col_name), default=np.nan):.2f}")
        hover_text.append(
            f"Nama: {row.get('nama', row.get('family_id', '-'))}"
            f"<br>Family ID: {row.get('family_id', '-')}"
            f"<br>Status Bansos: {row.get('Status Bansos', '-')}"
            f"<br>Jenis Bansos: {row.get('Jenis Bansos', '-')}"
            f"<br>Status BPS-Bansos: {row.get('Status BPS-Bansos', '-')}"
            f"<br>Kategori BPS: {row.get('kategori_ikr', '-')}"
            f"<br>F_IKR: {_safe_float_metric(row.get('F_IKR'), default=np.nan):.2f}"
            f"<br>{selected_dimension_label}: {_safe_float_metric(row.get('Skor Dimensi Pilihan'), default=np.nan):.2f}"
            f"<br>Status Dimensi: {row.get('Status Dimensi Pilihan', '-')}"
            f"<br>Cluster: {row.get('Cluster Louvain', '-')}"
            f"<br>Dimensi Rentan: {row.get('Dimensi Rentan', '-')}"
            f"<br>{'<br>'.join(dim_lines)}"
        )
    map_df["__hover_text__"] = hover_text

    c_map, c_table = st.columns([1.6, 1.0], gap="large")
    with c_map:
        st.markdown("### Peta Spasial Bansos")
        if not lat_col or not lon_col:
            st.warning("Kolom lat/lon belum ditemukan sehingga peta spasial belum bisa ditampilkan.")
        elif map_df.empty:
            st.info("Tidak ada node yang cocok dengan filter peta saat ini.")
        else:
            if map_color_mode == "Status Bansos (YA/TIDAK)":
                fig_map = build_spatial_category_figure(
                    map_df,
                    lat_col=lat_col,
                    lon_col=lon_col,
                    category_col="Status Bansos",
                    hover_col="__hover_text__",
                    title=f"Peta Persebaran Bansos berdasarkan {selected_dimension_label} ({filter_mode})",
                    spatial_mode=spatial_mode,
                    category_order=["Penerima", "Non-Penerima"],
                    category_colors={"Penerima": "#0f766e", "Non-Penerima": "#b91c1c"},
                    marker_size=12,
                )
            elif map_color_mode == "Status BPS-Bansos":
                fig_map = build_spatial_category_figure(
                    map_df,
                    lat_col=lat_col,
                    lon_col=lon_col,
                    category_col="Status BPS-Bansos",
                    hover_col="__hover_text__",
                    title=f"Peta Persebaran Bansos berdasarkan {selected_dimension_label} ({filter_mode})",
                    spatial_mode=spatial_mode,
                    category_order=list(BANSOS_TARGETING_COLORS.keys()),
                    category_colors=BANSOS_TARGETING_COLORS,
                    marker_size=12,
                )
            else:
                fig_map = build_spatial_numeric_figure(
                    map_df,
                    lat_col=lat_col,
                    lon_col=lon_col,
                    value_col="F_IKR",
                    hover_col="__hover_text__",
                    title=f"Peta Persebaran Bansos berdasarkan {selected_dimension_label} ({filter_mode})",
                    spatial_mode=spatial_mode,
                    marker_size_col="bansos_num",
                    colorscale="RdYlGn",
                    colorbar_title="F_IKR Agregat",
                )
            if fig_map is not None:
                st.plotly_chart(fig_map, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
            else:
                st.warning("Koordinat belum valid untuk divisualisasikan di peta.")

    with c_table:
        st.markdown(f"### Ringkasan {selected_dimension_label}")
        summary_cols = [
            "Status Dimensi Pilihan",
            "Status BPS-Bansos",
            "Status Bansos",
            "kategori_ikr",
            "Jenis Bansos",
        ]
        df_summary = (
            df_nodes.groupby(summary_cols, dropna=False)
            .size()
            .reset_index(name="Jumlah KK")
            .sort_values(["Jumlah KK", "Status Dimensi Pilihan"], ascending=[False, True])
        )
        st.dataframe(df_summary, use_container_width=True)

        jenis_summary = (
            df_nodes[df_nodes["Status Bansos"] == "Penerima"]
            .groupby(["Status Dimensi Pilihan", "Jenis Bansos"], dropna=False)
            .size()
            .reset_index(name="Jumlah KK")
            .sort_values(["Status Dimensi Pilihan", "Jumlah KK"], ascending=[True, False])
        )
        st.markdown("#### Jenis Bansos pada Dimensi Terpilih")
        st.dataframe(jenis_summary, use_container_width=True)

    dim_priority_cols = [col for _, col in IKR_DIMENSION_MAP if col in df_nodes.columns]
    if dim_priority_cols:
        dim_long = (
            df_nodes.melt(
                id_vars=["Status Bansos"],
                value_vars=dim_priority_cols,
                var_name="Dimensi",
                value_name="Skor",
            )
        )
        dim_label_map = {col: label for label, col in IKR_DIMENSION_MAP}
        dim_long["Dimensi"] = dim_long["Dimensi"].map(lambda c: dim_label_map.get(c, c))
        dim_long["Skor"] = pd.to_numeric(dim_long["Skor"], errors="coerce")
        dim_long = dim_long.dropna(subset=["Skor"])
        if not dim_long.empty:
            fig_dim = px.box(
                dim_long,
                x="Dimensi",
                y="Skor",
                color="Status Bansos",
                color_discrete_map={"Penerima": "#0f766e", "Non-Penerima": "#b91c1c"},
                title="Sebaran Skor Tiap Dimensi menurut Status Penerimaan Bansos",
            )
            fig_dim.update_layout(template="plotly_white", height=460, xaxis_title="", yaxis_title="Skor")
            st.plotly_chart(fig_dim, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    bansos_dim_focus = df_nodes[["family_id", "nama", "Status Bansos", "Jenis Bansos", "kategori_ikr", "F_IKR", "Skor Dimensi Pilihan", "Status Dimensi Pilihan", "Cluster Louvain"]].copy()
    fig_focus = px.scatter(
        bansos_dim_focus,
        x="Skor Dimensi Pilihan",
        y="F_IKR",
        color="Status Bansos",
        symbol="kategori_ikr",
        hover_data=["nama", "family_id", "Jenis Bansos", "Cluster Louvain"],
        color_discrete_map={"Penerima": "#0f766e", "Non-Penerima": "#b91c1c"},
        title=f"Relasi {selected_dimension_label} terhadap F_IKR dan Penerimaan Bansos",
    )
    fig_focus.add_vline(x=selected_threshold, line_dash="dash", line_color="#475569")
    fig_focus.update_layout(template="plotly_white", height=460, xaxis_title=selected_dimension_label, yaxis_title="F_IKR")
    st.plotly_chart(fig_focus, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    detail_cols = [
        "family_id",
        "nama",
        "Status Bansos",
        "Jenis Bansos",
        "Status Dimensi Pilihan",
        "Skor Dimensi Pilihan",
        "Status BPS-Bansos",
        "kategori_ikr",
        "F_IKR",
        "Cluster Louvain",
        "Jumlah Dimensi Rentan",
        "Dimensi Rentan",
    ] + [col for _, col in IKR_DIMENSION_MAP if col in df_nodes.columns]
    if lat_col and lon_col:
        detail_cols += [lat_col, lon_col]
    detail_cols = [col for col in detail_cols if col in df_nodes.columns]
    st.markdown("### Detail Rumah Tangga")
    st.dataframe(
        df_nodes[detail_cols].sort_values(
            ["Status Dimensi Pilihan", "Status Bansos", "F_IKR"],
            ascending=[True, True, True],
        ),
        use_container_width=True,
    )


def build_labeled_attribute_connection_breakdown(
    graph_obj,
    attr_name,
    value_map=None,
    group_attr="cluster",
    category_order=None,
    invalid_label="Tidak Valid",
):
    if graph_obj is None or graph_obj.number_of_edges() == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    value_map = value_map or {}

    def map_value(val):
        if pd.isna(val):
            return invalid_label
        key = val
        if isinstance(val, str):
            key = val.strip()
        mapped = value_map.get(key, value_map.get(str(key), key))
        mapped_txt = str(mapped).strip()
        return mapped_txt if mapped_txt else invalid_label

    graph_tmp = graph_obj.copy()
    for n in graph_tmp.nodes():
        graph_tmp.nodes[n]["__mapped_attr__"] = map_value(graph_tmp.nodes[n].get(attr_name, invalid_label))
    return build_category_connection_breakdown(
        graph_tmp,
        category_attr="__mapped_attr__",
        group_attr=group_attr,
        category_order=category_order,
        invalid_label=invalid_label,
    )


def build_spatial_indicator_profile(
    graph_obj,
    dusun_attr,
    indicator_specs,
):
    if graph_obj is None or graph_obj.number_of_nodes() == 0 or not dusun_attr:
        return pd.DataFrame()

    rows = []
    dusun_vals = pd.Series([graph_obj.nodes[n].get(dusun_attr) for n in graph_obj.nodes()]).fillna("Tidak Valid").astype(str)
    dusun_order = sorted(dusun_vals.unique().tolist())
    for dusun_name in dusun_order:
        dusun_nodes = [n for n in graph_obj.nodes() if str(graph_obj.nodes[n].get(dusun_attr, "Tidak Valid")) == dusun_name]
        if not dusun_nodes:
            continue
        sub_g = graph_obj.subgraph(dusun_nodes).copy()
        row = {
            "Dusun": dusun_name,
            "Jumlah KK": int(len(dusun_nodes)),
            "Jumlah Edge Internal": int(sub_g.number_of_edges()),
            "Total Bobot Edge Internal": float(sum(_safe_float_metric(d.get("weight"), default=0.0) for _, _, d in sub_g.edges(data=True))),
        }
        for spec in indicator_specs:
            label = spec["label"]
            col = spec["col"]
            bin_vals = [int(_safe_float_metric(graph_obj.nodes[n].get(col), default=0.0) > 0) for n in dusun_nodes]
            yes_count = int(sum(bin_vals))
            row[f"{label} - Jumlah YA"] = yes_count
            row[f"{label} - Persentase YA (%)"] = float((yes_count / len(dusun_nodes)) * 100.0) if dusun_nodes else 0.0

            yy_weight = 0.0
            yn_weight = 0.0
            nn_weight = 0.0
            yy_edges = 0
            yn_edges = 0
            nn_edges = 0
            total_weight = 0.0
            total_edges = 0
            for u, v, d in sub_g.edges(data=True):
                u_yes = int(_safe_float_metric(sub_g.nodes[u].get(col), default=0.0) > 0)
                v_yes = int(_safe_float_metric(sub_g.nodes[v].get(col), default=0.0) > 0)
                weight = _safe_float_metric(d.get("weight"), default=0.0)
                total_weight += weight
                total_edges += 1
                if u_yes == 1 and v_yes == 1:
                    yy_weight += weight
                    yy_edges += 1
                elif u_yes == 0 and v_yes == 0:
                    nn_weight += weight
                    nn_edges += 1
                else:
                    yn_weight += weight
                    yn_edges += 1

            row[f"{label} - YA-YA Bobot (%)"] = float((yy_weight / total_weight) * 100.0) if total_weight > 0 else 0.0
            row[f"{label} - YA-TIDAK Bobot (%)"] = float((yn_weight / total_weight) * 100.0) if total_weight > 0 else 0.0
            row[f"{label} - TIDAK-TIDAK Bobot (%)"] = float((nn_weight / total_weight) * 100.0) if total_weight > 0 else 0.0
            row[f"{label} - YA-YA Edge (%)"] = float((yy_edges / total_edges) * 100.0) if total_edges > 0 else 0.0
            row[f"{label} - YA-TIDAK Edge (%)"] = float((yn_edges / total_edges) * 100.0) if total_edges > 0 else 0.0
            row[f"{label} - TIDAK-TIDAK Edge (%)"] = float((nn_edges / total_edges) * 100.0) if total_edges > 0 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def build_ikr_assortativity_table(graph_obj, dimension_map=None):
    dimension_map = dimension_map or IKR_DIMENSION_MAP
    rows = []
    overall_label, overall_col = IKR_OVERALL_METRIC
    r_overall = safe_numeric_assortativity(graph_obj, overall_col, default=0.0)
    dir_overall, lvl_overall = interpret_assortativity_value(r_overall)
    rows.append(
        {
            "Dimensi IKR": overall_label,
            "Kolom Database": overall_col,
            "Assortativity r": float(r_overall),
            "Arah": dir_overall,
            "Kekuatan": lvl_overall,
            "Jenis": "Agregat",
        }
    )
    for dim_label, col_name in dimension_map:
        r_val = safe_numeric_assortativity(graph_obj, col_name, default=0.0)
        direction, strength = interpret_assortativity_value(r_val)
        rows.append(
            {
                "Dimensi IKR": dim_label,
                "Kolom Database": col_name,
                "Assortativity r": float(r_val),
                "Arah": direction,
                "Kekuatan": strength,
                "Jenis": "Dimensi",
            }
        )
    return pd.DataFrame(rows)


def compute_base_five_dimension_summary(df_assort):
    if df_assort is None or df_assort.empty:
        return None
    df_dims = df_assort[df_assort["Kolom Database"].isin(EDGE_REKAP_COLS)].copy()
    if df_dims.empty:
        return None
    r_mean = float(df_dims["Assortativity r"].mean())
    direction, strength = interpret_assortativity_value(r_mean)
    return {
        "Dimensi IKR": "Ringkasan 5 Dimensi Base Graph (Rata-rata r F_A..F_E)",
        "Kolom Database": "f_a..f_e (summary)",
        "Assortativity r": r_mean,
        "Arah": direction,
        "Kekuatan": strength,
        "Jenis": "Ringkasan",
    }

# =========================================================
# 2. CORE ANALYTICS ENGINE
# =========================================================

@st.cache_data
def load_and_clean_ddp(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            xls = pd.ExcelFile(file)
            sheet_name = next(
                (s for s in xls.sheet_names if str(s).lower() == "database"),
                next((s for s in xls.sheet_names if str(s).lower() == "dataset"), xls.sheet_names[0])
            )
            df = xls.parse(sheet_name)
        df.columns = [
            str(c).lower().strip().replace("\u00a0", " ").replace("\n", " ")
            for c in df.columns
        ]
        df.columns = [c.replace("  ", " ").strip() for c in df.columns]

        def pick_col(candidates):
            for cand in candidates:
                if cand in df.columns:
                    return cand
            return None

        subjek_col = pick_col(["subjek", "subyek", "subject"])
        if subjek_col is None:
            subjek_candidates = [c for c in df.columns if "subjek" in c]
            if subjek_candidates:
                subjek_col = subjek_candidates[0]
        if subjek_col is None:
            st.error("Kolom wajib `subjek` tidak ditemukan pada file upload.")
            return pd.DataFrame()

        family_src = pick_col([
            "family_id", "nomor kartu keluarga", "nomor_kartu_keluarga", "no_kk", "nokk", "kk"
        ])
        if family_src is None:
            st.warning("Kolom ID keluarga tidak ditemukan, `family_id` dibuat otomatis dari nomor baris.")
            df["family_id"] = [f"AUTO_FID_{i+1}" for i in range(len(df))]
        else:
            df["family_id"] = df[family_src].astype(str).str.strip()
            bad_fid = df["family_id"].isin(["", "nan", "none"])
            if bad_fid.any():
                df.loc[bad_fid, "family_id"] = [f"AUTO_FID_{i+1}" for i in range(int(bad_fid.sum()))]

        if "deskel" not in df.columns:
            nama_deskel_col = pick_col(["nama deskel", "desa", "nama desa"])
            if nama_deskel_col is not None:
                df["deskel"] = df[nama_deskel_col]
        if "desa" not in df.columns and "deskel" in df.columns:
            df["desa"] = df["deskel"]

        if "par_organisa" not in df.columns and "partisipasi organisasi" in df.columns:
            df["par_organisa"] = df["partisipasi organisasi"]
        if "bansos" not in df.columns and "keikutsertaan program bantuan" in df.columns:
            df["bansos"] = df["keikutsertaan program bantuan"]

        df['subjek_clean'] = df[subjek_col].astype(str).str.lower().str.strip()
        df_kk = df[df['subjek_clean'].str.contains('kepala keluarga', na=False)].drop_duplicates('family_id').copy()
        if df_kk.empty:
            st.error("Tidak ada baris dengan `subjek` berisi 'kepala keluarga'.")
            return pd.DataFrame()

        bansos_col = pick_col(["bansos", "keikutsertaan program bantuan", "program bantuan", "bantuan sosial", "bansos bantuan"])
        media_info_col = pick_col(["media informasi", "media_informasi", "akses informasi", "sumber informasi", "media info"])
        ponsel_col = pick_col(["kepemilikan ponsel", "kepemilikan_ponsel", "memiliki ponsel", "ponsel", "hp"])

        bansos_src = df_kk[bansos_col] if bansos_col in df_kk.columns else pd.Series(["0"] * len(df_kk), index=df_kk.index)
        df_kk['bansos_num'] = bansos_src.apply(to_binary_presence).astype(int)

        if media_info_col in df_kk.columns:
            df_kk['internet_num'] = df_kk[media_info_col].apply(to_binary_presence).astype(int)
        else:
            # Fallback: legacy digital indicator dari wifi/medsos bila kolom media informasi tidak tersedia.
            df_kk['internet_num'] = df_kk.apply(
                lambda r: 1 if (pd.notnull(r.get('wifi')) and _normalize_text(r.get('wifi')) not in {'tidak ada', '0', '0.0', 'nan', 'none', ''})
                or (pd.notnull(r.get('medsos')) and _normalize_text(r.get('medsos')) not in {'tidak ada', '0', '0.0', 'nan', 'none', ''})
                else 0,
                axis=1
            ).astype(int)

        if ponsel_col in df_kk.columns:
            df_kk['ponsel_num'] = df_kk[ponsel_col].apply(to_binary_phone).astype(int)
        else:
            df_kk['ponsel_num'] = 0

        # Backward compatibility untuk bagian dashboard lama yang masih memakai nama digital_num.
        df_kk['digital_num'] = df_kk['internet_num']
        df_kk['organisasi_num'] = df_kk.apply(lambda r: 1 if (pd.notnull(r.get('par_organisa')) or pd.notnull(r.get('par_organisasi'))) and 
                                           str(r.get('par_organisa') if pd.notnull(r.get('par_organisa')) else r.get('par_organisasi')).lower() not in ['0','tidak','tidak ada','nan',''] else 0, axis=1)
        return df_kk
    except Exception as e:
        st.error(f"Gagal memproses file: {e}")
        return None

def build_sna_network(
    df_v,
    basis_col,
    threshold_val=None,
    lcc_only=True,
    similarity_method="cosine",
    force_louvain_lcc=False,
    threshold_grid=None,
    edge_feature_cols=None,
    onehot_round_decimals=2,
):
    if len(df_v) < 5:
        return None
    method_norm = str(similarity_method or "cosine").lower().strip()
    if method_norm not in {"cosine", "jaccard", "pearson"}:
        method_norm = "cosine"
    if threshold_grid is None:
        threshold_grid = [round(x, 1) for x in np.arange(0.1, 1.0, 0.1)]

    G = nx.Graph()
    threshold_used = 0.4
    threshold_distribution = []
    pairwise_similarity_values = []
    if not edge_feature_cols:
        st.error("Kolom fitur edge belum ditentukan.")
        return None
    col_lookup = {str(c).lower().strip(): c for c in df_v.columns}
    resolved_feature_cols = []
    missing_cols = []
    for c in edge_feature_cols:
        key = str(c).lower().strip()
        if key in col_lookup:
            resolved_feature_cols.append(col_lookup[key])
        else:
            missing_cols.append(c)
    feature_cols = tuple(resolved_feature_cols)
    required_cols = {"family_id", *feature_cols}
    missing_cols += [c for c in required_cols if c not in df_v.columns]
    if missing_cols:
        st.error(f"Kolom fitur edge belum lengkap: {', '.join(missing_cols)}")
        return None
    df_builder = df_v.copy()
    df_builder = df_builder[df_builder["family_id"].notna()].drop_duplicates("family_id").copy()
    if len(df_builder) < 5:
        return None
    node_data = df_builder.set_index("family_id").to_dict("index")
    for nid, attr in node_data.items():
        G.add_node(nid, **attr)
    ids = list(node_data.keys())
    feature_matrix = build_onehot_feature_matrix(
        df_builder,
        feature_cols,
        rounding_decimals=onehot_round_decimals,
    ).astype(float)
    feature_vectors = {
        fid: feature_matrix.iloc[idx].to_numpy(dtype=float)
        for idx, fid in enumerate(df_builder["family_id"].tolist())
    }
    candidate_edges = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            vec_i = feature_vectors[ids[i]]
            vec_j = feature_vectors[ids[j]]
            if method_norm == "cosine":
                sim_weight = compute_cosine_similarity(vec_i, vec_j)
            elif method_norm == "jaccard":
                sim_weight = compute_jaccard_similarity(vec_i, vec_j)
            else:
                sim_weight = compute_pearson_similarity(vec_i, vec_j)
            pairwise_similarity_values.append(float(sim_weight))
            candidate_edges.append((ids[i], ids[j], float(sim_weight)))
    threshold_used, threshold_distribution = compute_auto_threshold_from_distribution(
        pairwise_similarity_values,
        threshold_grid=threshold_grid,
    )
    for u, v, sim_weight in candidate_edges:
        if sim_weight >= threshold_used:
            G.add_edge(u, v, weight=sim_weight)

    if G.number_of_edges() == 0:
        return None
    G_lcc = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    G_target = G_lcc if lcc_only else G.copy()
    partition_graph = G_lcc if force_louvain_lcc else G_target

    partition_raw = community_louvain.best_partition(partition_graph, weight='weight', random_state=42)
    basis_for_cluster_order = resolve_basis_column(df_v, basis_col)
    if basis_for_cluster_order:
        cluster_means = {
            cid: np.mean(
                [
                    _safe_float_metric(G_target.nodes[n].get(basis_for_cluster_order), default=0.0)
                    for n, c in partition_raw.items()
                    if c == cid
                ]
            )
            for cid in set(partition_raw.values())
        }
    else:
        cluster_means = {
            cid: float(
                np.mean([G_target.degree(n, weight="weight") for n, c in partition_raw.items() if c == cid])
            )
            for cid in set(partition_raw.values())
        }
    reorder_map = {old: new for new, (old, _) in enumerate(sorted(cluster_means.items(), key=lambda x: x[1]))}
    partition = {node: reorder_map[cid] for node, cid in partition_raw.items()}
    if not lcc_only and force_louvain_lcc:
        for n in G_target.nodes():
            if n not in partition:
                partition[n] = -1
    nx.set_node_attributes(G_target, partition, 'cluster')

    meta = {
        "raw_nodes": G.number_of_nodes(),
        "raw_edges": G.number_of_edges(),
        "lcc_nodes": G_lcc.number_of_nodes(),
        "lcc_edges": G_lcc.number_of_edges(),
        "similarity_method": method_norm,
        "threshold_selected": threshold_used,
        "threshold_auto": True,
        "threshold_distribution": threshold_distribution,
        "pairwise_similarity_values": pairwise_similarity_values,
        "mode": "LCC only" if lcc_only else "Semua komponen",
        "onehot_round_decimals": int(onehot_round_decimals),
    }
    return G_target, partition, sorted(list(set(reorder_map.values()))), meta


def render_weighting_methods_page(
    df_v,
    edge_feature_cols,
    rounding_decimals=2,
    threshold_grid=None,
    sample_max_nodes=120,
):
    threshold_grid = threshold_grid or [round(x, 1) for x in np.arange(0.1, 1.0, 0.1)]
    demo_threshold = 0.30
    st.markdown("<h1 class='main-header'>Halaman Metode Pembobotan: Cosine Similarity</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='premium-hero'><b>Fokus Halaman:</b> Simulasi data pseudo untuk menjelaskan pembobotan edge "
        "dengan <b>Cosine Similarity</b> pada representasi one-hot dari 5 dimensi IKR.</div>",
        unsafe_allow_html=True,
    )
    feature_cols = ("F_A", "F_B", "F_C", "F_D", "F_E")
    pseudo_two_nodes = pd.DataFrame(
        [
            {"family_id": "KK_A", "F_A": 33, "F_B": 70, "F_C": 55, "F_D": 80, "F_E": 61},
            {"family_id": "KK_B", "F_A": 33, "F_B": 70, "F_C": 55, "F_D": 79, "F_E": 62},
        ]
    )
    pseudo_for_onehot = pseudo_two_nodes.copy()
    onehot_two = build_onehot_feature_matrix(
        pseudo_for_onehot,
        feature_cols,
        rounding_decimals=rounding_decimals,
    )

    tab_alur, tab_rumus, tab_sim, tab_dist = st.tabs(
        ["Alur Metode", "Rumus Matematis", "Simulasi 2 Node (Pseudo)", "Distribusi Cosine (Pseudo)"]
    )

    with tab_alur:
        st.markdown(
            "<div class='soft-card'><b>Alur Pembentukan Bobot Edge</b><br>"
            "Input dimensi: <b>F_A (Sandang/Pangan/Papan), F_B (Pendidikan), F_C (Sosial/Hukum), "
            "F_D (Kesehatan/Pekerjaan), F_E (Lingkungan/Infrastruktur)</b>.<br>"
            "Setiap <b>kepala keluarga (KK)</b> didefinisikan sebagai satu node.<br>"
            "Pembuatan edge dimulai dari pembobotan similarity antar-node (Cosine).<br>"
            "Aturan keputusan threshold:<br>"
            "- Jika similarity <b>&ge; threshold rata-rata</b> -> edge dibuat.<br>"
            "- Jika similarity <b>&lt; threshold rata-rata</b> -> edge tidak dibuat.<br>"
            "Output akhir: <b>graf base siap diproses algoritma Louvain</b>."
            "</div>",
            unsafe_allow_html=True,
        )
        flow_df = pd.DataFrame(
            [
                {"Tahap": "Mulai", "Deskripsi": "Inisialisasi pembentukan graf base."},
                {
                    "Tahap": "Input 5 Dimensi",
                    "Deskripsi": "Masukkan F_A, F_B, F_C, F_D, F_E per KK (masing-masing dari rekap dimensi IKR).",
                },
                {"Tahap": "Definisi Node", "Deskripsi": "Setiap kepala keluarga (KK) didefinisikan sebagai 1 node."},
                {
                    "Tahap": "Transformasi One-Hot",
                    "Deskripsi": (
                        "Nilai dibulatkan ke bilangan bulat lalu di-encode menjadi vektor biner 0/1."
                        if int(rounding_decimals) == 0
                        else f"Nilai dibulatkan {rounding_decimals} desimal lalu di-encode menjadi vektor biner 0/1."
                    ),
                },
                {
                    "Tahap": "Pembobotan Edge",
                    "Deskripsi": "Hitung similarity antar pasangan node dengan Cosine Similarity: s_ij.",
                },
                {
                    "Tahap": "Rule Threshold",
                    "Deskripsi": "Jika s_ij >= threshold rata-rata -> buat edge (w_ij = s_ij). Jika s_ij < threshold -> edge tidak dibuat.",
                },
                {"Tahap": "Output", "Deskripsi": "Graf base berbobot siap diproses algoritma Louvain."},
            ]
        )
        fig_flow = px.funnel(
            flow_df,
            y="Tahap",
            x=[1] * len(flow_df),
            title="Tahapan Pembobotan Graf Base",
        )
        fig_flow.update_traces(
            marker_color="#1d4ed8",
            text=flow_df["Deskripsi"],
            textposition="inside",
            texttemplate="<b>%{y}</b><br>%{text}",
            insidetextfont=dict(size=12, color="#ffffff"),
        )
        fig_flow.update_layout(
            showlegend=False,
            yaxis_title="",
            xaxis_title="",
            height=640,
            template="plotly_white",
        )
        st.plotly_chart(fig_flow, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(flow_df, use_container_width=True)

    with tab_rumus:
        st.markdown("#### Cosine Similarity")
        st.latex(r"s_{ij}^{(\cos)} = \frac{\mathbf{x}_i^\top \mathbf{x}_j}{\|\mathbf{x}_i\|_2 \, \|\mathbf{x}_j\|_2}")
        st.latex(r"\mathbf{x}_i^\top \mathbf{x}_j = \sum_{k=1}^{p} x_{ik}x_{jk}")
        st.latex(r"\|\mathbf{x}_i\|_2 = \sqrt{\sum_{k=1}^{p} x_{ik}^2}")
        st.latex(r"w_{ij} = s_{ij}^{(\cos)} \;\;\text{dan edge terbentuk jika}\;\; s_{ij}^{(\cos)} \ge 0.30")
        st.caption(
            "x_i adalah vektor one-hot node i, x_j adalah vektor one-hot node j, "
            "dan s_ij menjadi bobot edge saat lolos threshold."
        )
        st.markdown("#### Notasi Matematis")
        notation_rows = [
            (r"\mathbf{x}_i = [x_{i1},\ldots,x_{ip}]", "Vektor one-hot node i."),
            (r"\mathbf{x}_j = [x_{j1},\ldots,x_{jp}]", "Vektor one-hot node j."),
            (r"x_{ik}\in\{0,1\}", "Komponen ke-k dari node i (aktif/tidak aktif)."),
            (r"\mathbf{x}_i^\top \mathbf{x}_j=\sum_{k=1}^{p}x_{ik}x_{jk}", "Dot product (jumlah kecocokan komponen aktif)."),
            (r"\|\mathbf{x}_i\|_2=\sqrt{\sum_{k=1}^{p}x_{ik}^2}", "Panjang vektor node i."),
            (r"s_{ij}^{(\cos)}=\frac{\mathbf{x}_i^\top \mathbf{x}_j}{\|\mathbf{x}_i\|_2\|\mathbf{x}_j\|_2}", "Skor cosine similarity."),
            (r"w_{ij}=s_{ij}^{(\cos)}", "Bobot edge yang dipakai di graf."),
        ]
        for expr, meaning in notation_rows:
            st.latex(expr)
            st.caption(meaning)

    with tab_sim:
        st.markdown("#### Data 2 Node Terpilih")
        st.dataframe(pseudo_two_nodes, use_container_width=True)
        active_cols = onehot_two.columns[(onehot_two.sum(axis=0) > 0)].tolist()
        onehot_view = onehot_two[active_cols].copy() if active_cols else onehot_two.copy()
        onehot_view.index = pseudo_two_nodes["family_id"].astype(str).tolist()
        st.markdown("#### Hasil One-Hot (kolom aktif)")
        st.dataframe(onehot_view, use_container_width=True)

        vec_a = onehot_two.iloc[0].to_numpy(dtype=float)
        vec_b = onehot_two.iloc[1].to_numpy(dtype=float)
        dot_val = float(np.dot(vec_a, vec_b))
        norm_a = float(np.linalg.norm(vec_a))
        norm_b = float(np.linalg.norm(vec_b))
        cos_val = compute_cosine_similarity(vec_a, vec_b)
        edge_decision = "TERBENTUK" if cos_val >= demo_threshold else "TIDAK TERBENTUK"
        c1, c2 = st.columns(2)
        c1.metric("Cosine", f"{cos_val:.4f}")
        c2.metric("Dot Product", f"{dot_val:.4f}")
        c3, c4 = st.columns(2)
        c3.metric("Threshold Contoh", f"{demo_threshold:.2f}")
        c4.metric("Status Edge", edge_decision)
        st.caption("Contoh 2 node ini disusun agar tingkat kemiripan lolos threshold 0,30.")
        st.markdown("#### Detail Hitung Cosine (2 Node)")
        st.latex(r"\mathbf{x}_i^\top \mathbf{x}_j = \sum_{k=1}^{p}x_{ik}x_{jk}")
        st.latex(rf"\mathbf{{x}}_i^\top \mathbf{{x}}_j = {dot_val:.4f}")
        st.latex(r"\|\mathbf{x}_i\|_2=\sqrt{\sum_{k=1}^{p}x_{ik}^2},\quad \|\mathbf{x}_j\|_2=\sqrt{\sum_{k=1}^{p}x_{jk}^2}")
        st.latex(rf"\|\mathbf{{x}}_i\|_2 = {norm_a:.4f},\quad \|\mathbf{{x}}_j\|_2 = {norm_b:.4f}")
        st.latex(r"s_{ij}^{(\cos)}=\frac{\mathbf{x}_i^\top \mathbf{x}_j}{\|\mathbf{x}_i\|_2\|\mathbf{x}_j\|_2}")
        st.markdown("#### Substitusi Angka ke Persamaan")
        st.latex(rf"s_{{ij}}^{{(\cos)}}=\frac{{{dot_val:.4f}}}{{{norm_a:.4f}\times {norm_b:.4f}}}={cos_val:.4f}")
        st.latex(rf"w_{{ij}} = s_{{ij}}^{{(\cos)}} = {cos_val:.4f}")
        st.latex(rf"\text{{Edge terbentuk jika }} s_{{ij}}^{{(\cos)}} \ge {demo_threshold:.2f}")
        st.latex(rf"{cos_val:.4f} \; {'\\ge' if cos_val >= demo_threshold else '<'} \; {demo_threshold:.2f} \Rightarrow \text{{{edge_decision}}}")
        st.caption(
            "Dot product adalah jumlah hasil kali komponen seposisi pada dua vektor. "
            "Pada one-hot, dot product merepresentasikan jumlah kategori yang sama-sama aktif."
        )

    with tab_dist:
        st.markdown("#### Distribusi Cosine dari Sampel Pseudo")
        rng = np.random.default_rng(42)
        value_pool = {
            "F_A": [33.40, 33.50, 33.60, 34.00],
            "F_B": [70.00, 70.50, 71.00, 71.50],
            "F_C": [55.00, 55.20, 55.40, 55.60],
            "F_D": [79.50, 80.00, 80.50, 81.00],
            "F_E": [61.20, 61.30, 61.40, 61.50],
        }
        n_nodes = int(max(20, sample_max_nodes))
        pseudo_nodes = []
        for idx in range(n_nodes):
            row = {"family_id": f"PS_{idx+1:03d}"}
            for c in feature_cols:
                row[c] = float(rng.choice(value_pool[c]))
            pseudo_nodes.append(row)
        pseudo_df = pd.DataFrame(pseudo_nodes)
        onehot_sample = build_onehot_feature_matrix(pseudo_df, feature_cols, rounding_decimals=rounding_decimals)
        ids = pseudo_df["family_id"].tolist()
        vectors = onehot_sample.to_numpy(dtype=float)
        cos_values = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                vec_i = vectors[i]
                vec_j = vectors[j]
                cos_values.append(float(compute_cosine_similarity(vec_i, vec_j)))
        if not cos_values:
            st.warning("Pasangan node pseudo belum cukup.")
            return

        fig_hist = px.histogram(
            x=cos_values,
            nbins=24,
            title="Histogram Cosine Similarity (Data Pseudo)",
        )
        fig_hist.update_layout(xaxis_title="Cosine Similarity", yaxis_title="Frekuensi")
        st.plotly_chart(fig_hist, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

        edge_at_demo = int(np.sum(np.array(cos_values) >= demo_threshold))
        summary_df = pd.DataFrame(
            [
                {
                    "Metode": "Cosine",
                    "Similarity Rata-rata": float(np.mean(cos_values)),
                    "Similarity Median": float(np.median(cos_values)),
                    "Threshold (Contoh)": float(demo_threshold),
                    "Edge Count @ Threshold": int(edge_at_demo),
                }
            ]
        )
        st.dataframe(summary_df, use_container_width=True)
        st.caption(
            f"Pada halaman metode ini, keputusan edge didemokan dengan threshold tetap {demo_threshold:.2f}."
        )


def render_louvain_methods_page(
    n_nodes=60,
    rounding_decimals=2,
    threshold=0.30,
    seed=42,
):
    st.markdown("<h1 class='main-header'>Halaman Metode Louvain (Simulasi Pseudo)</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='premium-hero'><b>Fokus Halaman:</b> Menjelaskan logika penerapan Louvain dari graf base berbobot "
        "yang dibangun dari data pseudo 5 dimensi IKR.</div>",
        unsafe_allow_html=True,
    )
    tab_alur, tab_rumus, tab_sim, tab_out = st.tabs(
        ["Alur Louvain", "Rumus Modularity", "Simulasi dari Graf Base Pseudo", "Output Komunitas"]
    )

    with tab_alur:
        louvain_flow = pd.DataFrame(
            [
                {"Tahap": "Input Graf Base", "Deskripsi": "Gunakan graf berbobot hasil similarity antar node."},
                {"Tahap": "Inisialisasi", "Deskripsi": "Setiap node mulai sebagai komunitas sendiri."},
                {"Tahap": "Local Moving", "Deskripsi": "Pindahkan node ke komunitas tetangga jika modularity naik."},
                {"Tahap": "Agregasi", "Deskripsi": "Gabungkan komunitas jadi super-node (graf baru)."},
                {"Tahap": "Iterasi", "Deskripsi": "Ulangi Local Moving + Agregasi sampai Q tidak naik lagi."},
                {"Tahap": "Output", "Deskripsi": "Partisi komunitas final Louvain."},
            ]
        )
        fig_louvain_flow = px.funnel(
            louvain_flow,
            y="Tahap",
            x=[1] * len(louvain_flow),
            title="Tahapan Penerapan Louvain dari Graf Base",
        )
        fig_louvain_flow.update_traces(
            marker_color="#1d4ed8",
            text=louvain_flow["Deskripsi"],
            textposition="inside",
            texttemplate="<b>%{y}</b><br>%{text}",
            insidetextfont=dict(size=12, color="#ffffff"),
        )
        fig_louvain_flow.update_layout(height=560, template="plotly_white", xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_louvain_flow, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(louvain_flow, use_container_width=True)

    with tab_rumus:
        st.markdown("#### Fungsi Modularity (Q)")
        st.latex(
            r"Q = \frac{1}{2m}\sum_{i,j}\left(A_{ij} - \frac{k_i k_j}{2m}\right)\delta(c_i, c_j)"
        )
        st.markdown("#### Arti Simbol")
        st.latex(r"A_{ij}: \text{bobot edge antara node } i \text{ dan } j")
        st.latex(r"k_i: \text{weighted degree node } i,\;\; k_i=\sum_j A_{ij}")
        st.latex(r"2m: \sum_{i,j} A_{ij}")
        st.latex(r"c_i: \text{komunitas node } i")
        st.latex(r"\delta(c_i,c_j)=1 \text{ jika sama komunitas, selain itu }0")
        st.caption(
            "Louvain mencari partisi komunitas yang memaksimalkan Q. "
            "Node dipindahkan lokal jika meningkatkan modularity."
        )

    # Bangun graf base pseudo dari 5 dimensi, lalu jalankan Louvain.
    rng = np.random.default_rng(int(seed))
    pools = {
        "F_A": [33.40, 33.50, 33.60, 34.00],
        "F_B": [70.00, 70.50, 71.00, 71.50],
        "F_C": [55.00, 55.20, 55.40, 55.60],
        "F_D": [79.50, 80.00, 80.50, 81.00],
        "F_E": [61.20, 61.30, 61.40, 61.50],
    }
    pseudo_rows = []
    for i in range(int(max(20, n_nodes))):
        row = {"family_id": f"LV_{i+1:03d}"}
        for c in ["F_A", "F_B", "F_C", "F_D", "F_E"]:
            row[c] = float(rng.choice(pools[c]))
        pseudo_rows.append(row)
    pseudo_df = pd.DataFrame(pseudo_rows)
    onehot = build_onehot_feature_matrix(
        pseudo_df,
        ("F_A", "F_B", "F_C", "F_D", "F_E"),
        rounding_decimals=rounding_decimals,
    )

    G = nx.Graph()
    for _, r in pseudo_df.iterrows():
        G.add_node(r["family_id"], **r.to_dict())
    ids = pseudo_df["family_id"].tolist()
    vecs = onehot.to_numpy(dtype=float)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            sim = float(compute_cosine_similarity(vecs[i], vecs[j]))
            if sim >= float(threshold):
                G.add_edge(ids[i], ids[j], weight=sim)

    if G.number_of_edges() == 0:
        # fallback agar simulasi tetap jalan jika threshold terlalu tinggi.
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = float(compute_cosine_similarity(vecs[i], vecs[j]))
                if sim >= 0.20:
                    G.add_edge(ids[i], ids[j], weight=sim)

    if G.number_of_edges() > 0:
        init_partition = {n: idx for idx, n in enumerate(G.nodes())}
        q_init = _safe_float_metric(community_louvain.modularity(init_partition, G, weight="weight"), default=0.0)
        final_partition = community_louvain.best_partition(G, weight="weight", random_state=int(seed))
        q_final = _safe_float_metric(community_louvain.modularity(final_partition, G, weight="weight"), default=0.0)
    else:
        init_partition = {n: 0 for n in G.nodes()}
        final_partition = init_partition.copy()
        q_init = 0.0
        q_final = 0.0

    with tab_sim:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Node", G.number_of_nodes())
        c2.metric("Edge", G.number_of_edges())
        c3.metric("Q Awal", f"{q_init:.5f}")
        c4.metric("Q Final Louvain", f"{q_final:.5f}", f"ΔQ = {q_final - q_init:.5f}")

        if G.number_of_edges() > 0:
            pos = nx.spring_layout(G, seed=int(seed), weight="weight")
            nodes = list(G.nodes())
            comm_ids = [final_partition.get(n, 0) for n in nodes]
            fig_graph = go.Figure()
            for u, v, d in G.edges(data=True):
                fig_graph.add_trace(
                    go.Scatter(
                        x=[pos[u][0], pos[v][0], None],
                        y=[pos[u][1], pos[v][1], None],
                        mode="lines",
                        line=dict(width=1.0 + 1.6 * _safe_float_metric(d.get("weight"), 0.0), color="rgba(51,65,85,0.45)"),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )
            fig_graph.add_trace(
                go.Scatter(
                    x=[pos[n][0] for n in nodes],
                    y=[pos[n][1] for n in nodes],
                    mode="markers",
                    marker=dict(
                        size=10,
                        color=comm_ids,
                        colorscale="Blues",
                        showscale=True,
                        colorbar=dict(title="Komunitas"),
                        line=dict(color="#0f172a", width=0.6),
                    ),
                    text=[f"Node: {n}<br>Komunitas: {final_partition.get(n, 0)}" for n in nodes],
                    hoverinfo="text",
                    showlegend=False,
                )
            )
            fig_graph.update_layout(
                title="Graf Base Pseudo setelah Louvain (warna = komunitas)",
                height=560,
                template="plotly_white",
                margin=dict(l=20, r=20, t=60, b=20),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(fig_graph, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        else:
            st.warning("Graf pseudo tidak memiliki edge pada konfigurasi saat ini.")

    with tab_out:
        if G.number_of_nodes() == 0:
            st.warning("Tidak ada node untuk dianalisis.")
        else:
            out_df = pd.DataFrame(
                [{"family_id": n, "Komunitas Louvain": int(final_partition.get(n, 0))} for n in G.nodes()]
            )
            degree_map = {n: float(G.degree(n, weight="weight")) for n in G.nodes()}
            pseudo_profile = pseudo_df.copy()
            pseudo_profile["Komunitas Louvain"] = pseudo_profile["family_id"].map(
                lambda n: int(final_partition.get(n, -1))
            )
            pseudo_profile["Weighted Degree"] = pseudo_profile["family_id"].map(
                lambda n: float(degree_map.get(n, 0.0))
            )
            size_df = (
                out_df["Komunitas Louvain"]
                .value_counts()
                .rename_axis("Komunitas Louvain")
                .reset_index(name="Jumlah Node")
                .sort_values("Komunitas Louvain")
                .reset_index(drop=True)
            )
            total_clusters = int(size_df["Komunitas Louvain"].nunique())
            st.markdown("#### Ringkasan Komunitas Louvain")
            csum1, csum2 = st.columns(2)
            csum1.metric("Jumlah Klaster Terbentuk", f"{total_clusters}")
            csum2.metric("Total Node Terpartisi", f"{int(size_df['Jumlah Node'].sum())}")
            st.dataframe(size_df, use_container_width=True)

            cluster_desc = (
                pseudo_profile.groupby("Komunitas Louvain", as_index=False)
                .agg(
                    Jumlah_Node=("family_id", "count"),
                    Rerata_F_A=("F_A", "mean"),
                    Rerata_F_B=("F_B", "mean"),
                    Rerata_F_C=("F_C", "mean"),
                    Rerata_F_D=("F_D", "mean"),
                    Rerata_F_E=("F_E", "mean"),
                    Rerata_Weighted_Degree=("Weighted Degree", "mean"),
                )
                .sort_values("Komunitas Louvain")
                .reset_index(drop=True)
            )
            cluster_desc["Rerata_F_IKR"] = cluster_desc[
                ["Rerata_F_A", "Rerata_F_B", "Rerata_F_C", "Rerata_F_D", "Rerata_F_E"]
            ].mean(axis=1)
            st.markdown("#### Statistik Deskriptif per Klaster")
            st.dataframe(
                cluster_desc.style.format(
                    {
                        "Rerata_F_A": "{:.2f}",
                        "Rerata_F_B": "{:.2f}",
                        "Rerata_F_C": "{:.2f}",
                        "Rerata_F_D": "{:.2f}",
                        "Rerata_F_E": "{:.2f}",
                        "Rerata_F_IKR": "{:.2f}",
                        "Rerata_Weighted_Degree": "{:.2f}",
                    }
                ),
                use_container_width=True,
            )

            fig_cluster_profile = px.bar(
                cluster_desc.melt(
                    id_vars=["Komunitas Louvain"],
                    value_vars=["Rerata_F_A", "Rerata_F_B", "Rerata_F_C", "Rerata_F_D", "Rerata_F_E", "Rerata_F_IKR"],
                    var_name="Indikator",
                    value_name="Rerata Nilai",
                ),
                x="Komunitas Louvain",
                y="Rerata Nilai",
                color="Indikator",
                barmode="group",
                title="Profil Rerata Dimensi per Klaster Louvain",
            )
            st.plotly_chart(fig_cluster_profile, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

            st.markdown("#### Narasi Otomatis Karakter Tiap Klaster")
            for _, row in cluster_desc.iterrows():
                cid = int(row["Komunitas Louvain"])
                n_k = int(row["Jumlah_Node"])
                avg_ikr = float(row["Rerata_F_IKR"])
                ikr_lbl, _ = categorize_ikr_bps(avg_ikr)
                if avg_ikr >= 75:
                    tone = "klaster relatif kuat secara skor dimensi"
                elif avg_ikr >= 65:
                    tone = "klaster menengah dengan kapasitas campuran"
                else:
                    tone = "klaster dengan kerentanan dimensi yang perlu prioritas"
                st.markdown(
                    f"<div class='soft-card'><b>Klaster {cid}</b> berisi <b>{n_k}</b> node, "
                    f"rerata F_IKR simulasi <b>{avg_ikr:.2f}</b> (kategori <b>{ikr_lbl}</b>), "
                    f"dengan rerata weighted degree <b>{float(row['Rerata_Weighted_Degree']):.2f}</b>. "
                    f"Interpretasi cepat: {tone}.</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("#### Sampel Hasil Partisi Node")
            st.dataframe(out_df.head(30), use_container_width=True)
            st.caption(
                "Logika penerapan: graf base pseudo -> optimasi modularity (Louvain) -> partisi komunitas final."
            )


def render_assortativity_methods_page(
    n_nodes=90,
    seed=42,
):
    st.markdown("<h1 class='main-header'>Halaman Metode Assortativity (Komprehensif)</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='premium-hero'><b>Fokus Halaman:</b> Membahas semua jenis assortativity pada kode ini: "
        "numeric assortativity, attribute assortativity (biner/kategorikal), dan within-between assortativity (Montes).</div>",
        unsafe_allow_html=True,
    )

    rng = np.random.default_rng(int(seed))
    n_nodes = int(max(30, n_nodes))
    cluster_count = 3
    cluster_ids = [int(i % cluster_count) for i in range(n_nodes)]
    node_ids = [f"AS_{i+1:03d}" for i in range(n_nodes)]

    G = nx.Graph()
    rows = []
    for idx, nid in enumerate(node_ids):
        c = int(cluster_ids[idx])
        base = 62 + (c * 7)
        f_a = float(np.clip(rng.normal(base + 1.5, 2.2), 45, 95))
        f_b = float(np.clip(rng.normal(base + 0.8, 2.5), 45, 95))
        f_c = float(np.clip(rng.normal(base - 0.5, 2.4), 45, 95))
        f_d = float(np.clip(rng.normal(base + 1.2, 2.6), 45, 95))
        f_e = float(np.clip(rng.normal(base + 0.2, 2.7), 45, 95))
        f_ikr = float(np.mean([f_a, f_b, f_c, f_d, f_e]))

        bansos_num = int(rng.random() < (0.70 if c == 0 else 0.40 if c == 1 else 0.18))
        internet_num = int(rng.random() < (0.28 if c == 0 else 0.56 if c == 1 else 0.82))
        ponsel_num = int(rng.random() < (0.45 if c == 0 else 0.66 if c == 1 else 0.86))
        dusun = f"Dusun-{c+1}"
        cat_label, cat_code = categorize_ikr_bps(f_ikr)

        attrs = {
            "family_id": nid,
            "cluster": c,
            "f_a_dari_rekap_kk": f_a,
            "f_b_dari_rekap_kk": f_b,
            "f_c_dari_rekap_kk": f_c,
            "f_d_dari_rekap_kk": f_d,
            "f_e_dari_rekap_kk": f_e,
            "f_ikr_dari_rekap_kk": f_ikr,
            "bansos_num": bansos_num,
            "internet_num": internet_num,
            "ponsel_num": ponsel_num,
            "dusun": dusun,
            "kategori_ikr": cat_label,
            "kategori_ikr_code": int(cat_code),
        }
        G.add_node(nid, **attrs)
        rows.append(attrs)

    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            ci = cluster_ids[i]
            cj = cluster_ids[j]
            p_edge = 0.18 if ci == cj else 0.045
            if rng.random() < p_edge:
                si = rows[i]["f_ikr_dari_rekap_kk"]
                sj = rows[j]["f_ikr_dari_rekap_kk"]
                w = float(np.clip(1.0 - (abs(si - sj) / 60.0), 0.05, 1.0))
                G.add_edge(node_ids[i], node_ids[j], weight=w)

    if G.number_of_edges() == 0:
        st.warning("Graf pseudo assortativity belum memiliki edge. Ubah seed/jumlah node.")
        return

    tab_alur, tab_konsep, tab_num, tab_attr, tab_montes, tab_ringkas = st.tabs(
        ["Alur Assortativity", "Konsep & Rumus", "Numeric Assortativity", "Attribute Assortativity", "Within-Between Montes", "Ringkasan Interpretasi"]
    )

    with tab_alur:
        flow_assort = pd.DataFrame(
            [
                {"Tahap": "Input Graf Base", "Deskripsi": "Gunakan graf berbobot beserta atribut node."},
                {"Tahap": "Pilih Jenis Assortativity", "Deskripsi": "Numeric / Attribute / Within-Between (Montes)."},
                {"Tahap": "Hitung Metrik", "Deskripsi": "Dapatkan r (numeric/attribute), Qw*, dan Qb*."},
                {"Tahap": "Bandingkan Hasil", "Deskripsi": "Bandingkan antar dimensi/atribut untuk menemukan yang dominan."},
                {"Tahap": "Interpretasi", "Deskripsi": "Baca arah (asortatif/disasortatif) dan kekuatan pola."},
                {"Tahap": "Output Analitik", "Deskripsi": "Rekomendasi audit sosial-kebijakan berbasis hasil assortativity."},
            ]
        )
        fig_flow_assort = px.funnel(
            flow_assort,
            y="Tahap",
            x=[1] * len(flow_assort),
            title="Tahapan Analisis Assortativity",
        )
        fig_flow_assort.update_traces(
            marker_color="#1d4ed8",
            text=flow_assort["Deskripsi"],
            textposition="inside",
            texttemplate="<b>%{y}</b><br>%{text}",
            insidetextfont=dict(size=12, color="#ffffff"),
        )
        fig_flow_assort.update_layout(height=560, template="plotly_white", xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_flow_assort, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(flow_assort, use_container_width=True)

    with tab_konsep:
        k1, k2, k3 = st.columns(3)
        k1.metric("Jumlah Node (Pseudo)", G.number_of_nodes())
        k2.metric("Jumlah Edge (Pseudo)", G.number_of_edges())
        k3.metric("Jumlah Klaster Simulasi", cluster_count)
        st.markdown(
            "<div class='soft-card'><b>Cara Baca Nilai Assortativity (r):</b><br>"
            "<b>r > 0</b> = cenderung terhubung dengan node yang mirip (asortatif).<br>"
            "<b>r = 0</b> = cenderung acak/campuran.<br>"
            "<b>r < 0</b> = cenderung terhubung dengan node yang berbeda (disasortatif).<br>"
            "Semakin besar |r|, semakin kuat pola pemilahannya.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("#### 1) Numeric Assortativity (Newman)")
        st.latex(r"r = \mathrm{corr}(x_u, x_v)\;\; \text{untuk setiap edge } (u,v)")
        st.markdown("#### 2) Attribute Assortativity (Kategorikal/Biner)")
        st.latex(r"r = \frac{\sum_i e_{ii} - \sum_i a_i b_i}{1 - \sum_i a_i b_i}")
        st.markdown("#### 3) Within-Between Assortativity (Montes)")
        st.latex(r"Q_w^* = \frac{Q_w}{Q_{w,\max}},\quad Q_b^* = \frac{Q_b}{Q_{b,\max}}")
        st.caption(
            "Di kode ini: numeric assortativity untuk F_A..F_E dan F_IKR; attribute assortativity untuk bansos/internet/ponsel/dusun; "
            "Within-Between memakai kategori IKR (BPS) sebagai category_attr dan klaster sebagai group_attr."
        )
        cara_baca_df = pd.DataFrame(
            [
                {"Rentang Nilai": "r >= 0.50", "Interpretasi": "Asortatif kuat (pengelompokan tegas)"},
                {"Rentang Nilai": "0.30 <= r < 0.50", "Interpretasi": "Asortatif sedang"},
                {"Rentang Nilai": "0.10 <= r < 0.30", "Interpretasi": "Asortatif lemah"},
                {"Rentang Nilai": "-0.10 < r < 0.10", "Interpretasi": "Campuran / mendekati acak"},
                {"Rentang Nilai": "r <= -0.10", "Interpretasi": "Disasortatif (lebih sering lintas kategori)"},
            ]
        )
        st.dataframe(cara_baca_df, use_container_width=True)
        st.markdown("#### Kenapa Masuk Jenis Ini?")
        jenis_df = pd.DataFrame(
            [
                {
                    "Objek/Metrik": "F_A, F_B, F_C, F_D, F_E, F_IKR",
                    "Jenis Assortativity": "Numeric Assortativity",
                    "Alasan Metodologis": "Nilai berbentuk skor kontinu, sehingga yang diukur adalah korelasi nilai antar-node pada edge.",
                    "Rumus Inti": "r = corr(x_u, x_v) pada edge (u,v)",
                },
                {
                    "Objek/Metrik": "Bansos, Internet, Ponsel, Dusun",
                    "Jenis Assortativity": "Attribute Assortativity",
                    "Alasan Metodologis": "Nilai berbentuk kategori/biner, sehingga yang diukur adalah kecenderungan edge menghubungkan kategori yang sama.",
                    "Rumus Inti": "r berbasis matriks mixing kategori",
                },
                {
                    "Objek/Metrik": "Kategori IKR BPS + Klaster",
                    "Jenis Assortativity": "Within-Between (Montes)",
                    "Alasan Metodologis": "Tujuannya memisahkan pola homogenitas di dalam klaster vs antar-klaster.",
                    "Rumus Inti": "Qw* (within), Qb* (between)",
                },
            ]
        )
        st.dataframe(jenis_df, use_container_width=True)
        fig_class = px.treemap(
            jenis_df,
            path=["Jenis Assortativity", "Objek/Metrik"],
            values=[1, 1, 1],
            color="Jenis Assortativity",
            color_discrete_sequence=["#1d4ed8", "#2563eb", "#60a5fa"],
            title="Peta Klasifikasi Jenis Assortativity di Dashboard",
        )
        st.plotly_chart(fig_class, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    df_nodes = pd.DataFrame(rows)
    edge_pairs = []
    for u, v, d in G.edges(data=True):
        au = G.nodes[u]
        av = G.nodes[v]
        edge_pairs.append(
            {
                "u": u,
                "v": v,
                "weight": _safe_float_metric(d.get("weight"), 0.0),
                "cluster_u": int(au.get("cluster", -1)),
                "cluster_v": int(av.get("cluster", -1)),
                "f_a_u": _safe_float_metric(au.get("f_a_dari_rekap_kk"), np.nan),
                "f_a_v": _safe_float_metric(av.get("f_a_dari_rekap_kk"), np.nan),
                "f_b_u": _safe_float_metric(au.get("f_b_dari_rekap_kk"), np.nan),
                "f_b_v": _safe_float_metric(av.get("f_b_dari_rekap_kk"), np.nan),
                "f_c_u": _safe_float_metric(au.get("f_c_dari_rekap_kk"), np.nan),
                "f_c_v": _safe_float_metric(av.get("f_c_dari_rekap_kk"), np.nan),
                "f_d_u": _safe_float_metric(au.get("f_d_dari_rekap_kk"), np.nan),
                "f_d_v": _safe_float_metric(av.get("f_d_dari_rekap_kk"), np.nan),
                "f_e_u": _safe_float_metric(au.get("f_e_dari_rekap_kk"), np.nan),
                "f_e_v": _safe_float_metric(av.get("f_e_dari_rekap_kk"), np.nan),
                "f_ikr_u": _safe_float_metric(au.get("f_ikr_dari_rekap_kk"), np.nan),
                "f_ikr_v": _safe_float_metric(av.get("f_ikr_dari_rekap_kk"), np.nan),
                "bansos_u": str(au.get("bansos_num", "NA")),
                "bansos_v": str(av.get("bansos_num", "NA")),
                "internet_u": str(au.get("internet_num", "NA")),
                "internet_v": str(av.get("internet_num", "NA")),
                "ponsel_u": str(au.get("ponsel_num", "NA")),
                "ponsel_v": str(av.get("ponsel_num", "NA")),
                "dusun_u": str(au.get("dusun", "NA")),
                "dusun_v": str(av.get("dusun", "NA")),
            }
        )
    df_edges = pd.DataFrame(edge_pairs)
    numeric_specs = [
        ("F_A", "f_a_dari_rekap_kk"),
        ("F_B", "f_b_dari_rekap_kk"),
        ("F_C", "f_c_dari_rekap_kk"),
        ("F_D", "f_d_dari_rekap_kk"),
        ("F_E", "f_e_dari_rekap_kk"),
        ("F_IKR", "f_ikr_dari_rekap_kk"),
    ]
    numeric_rows = []
    for lbl, col in numeric_specs:
        r_val = safe_numeric_assortativity(G, col, default=0.0)
        direction, strength = interpret_assortativity_value(r_val)
        numeric_rows.append(
            {"Metrik": lbl, "Kolom": col, "r": float(r_val), "Arah": direction, "Kekuatan": strength}
        )
    df_num = pd.DataFrame(numeric_rows)

    with tab_num:
        st.markdown("#### Assortativity Numerik per Dimensi")
        st.caption(
            "Tab ini menjawab: dimensi skor mana yang paling mendorong pemilahan keterhubungan antar node."
        )
        with st.expander("Langkah Hitung Numeric Assortativity (Detail)", expanded=False):
            st.markdown("1. Ambil semua pasangan node yang terhubung (edge).")
            st.markdown("2. Untuk tiap edge, ambil nilai dimensi di node kiri dan kanan.")
            st.markdown("3. Hitung korelasi pasangan nilai tersebut.")
            st.markdown("4. Korelasi itulah nilai `r` numeric assortativity.")
        df_num_sorted = df_num.sort_values("r", ascending=False).reset_index(drop=True)
        fig_num = px.bar(
            df_num_sorted,
            x="r",
            y="Metrik",
            orientation="h",
            color="r",
            color_continuous_scale="Blues",
            range_color=[-1, 1],
            title="Perbandingan Numeric Assortativity",
            hover_data=["Kolom", "Arah", "Kekuatan"],
        )
        fig_num.add_vline(x=0.0, line_dash="dash", line_color="#475569")
        fig_num.update_traces(text=df_num_sorted["r"].map(lambda x: f"{x:.3f}"), textposition="outside")
        st.plotly_chart(fig_num, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(df_num.style.background_gradient(cmap="Blues", subset=["r"]), use_container_width=True)
        top_num_local = df_num.iloc[df_num["r"].abs().idxmax()]
        st.markdown(
            f"<div class='soft-card'><b>Interpretasi Cepat Numeric:</b><br>"
            f"Dimensi paling dominan adalah <b>{top_num_local['Metrik']}</b> dengan r=<b>{float(top_num_local['r']):.4f}</b> "
            f"({top_num_local['Arah']} | {top_num_local['Kekuatan']}).</div>",
            unsafe_allow_html=True,
        )
        numeric_pair_map = {
            "F_A": ("f_a_u", "f_a_v"),
            "F_B": ("f_b_u", "f_b_v"),
            "F_C": ("f_c_u", "f_c_v"),
            "F_D": ("f_d_u", "f_d_v"),
            "F_E": ("f_e_u", "f_e_v"),
            "F_IKR": ("f_ikr_u", "f_ikr_v"),
        }
        chosen_metric = st.selectbox(
            "Visual Pair Nilai per Edge (Numeric)",
            options=list(numeric_pair_map.keys()),
            index=5,
        )
        ux, vx = numeric_pair_map[chosen_metric]
        if not df_edges.empty:
            fig_pair = px.scatter(
                df_edges,
                x=ux,
                y=vx,
                color="weight",
                color_continuous_scale="Blues",
                title=f"Pasangan Nilai pada Setiap Edge - {chosen_metric}",
                labels={ux: f"{chosen_metric} (Node U)", vx: f"{chosen_metric} (Node V)", "weight": "Bobot Edge"},
                hover_data=["u", "v", "cluster_u", "cluster_v"],
            )
            min_xy = float(np.nanmin([df_edges[ux].min(), df_edges[vx].min()]))
            max_xy = float(np.nanmax([df_edges[ux].max(), df_edges[vx].max()]))
            fig_pair.add_trace(
                go.Scatter(
                    x=[min_xy, max_xy],
                    y=[min_xy, max_xy],
                    mode="lines",
                    line=dict(color="#334155", dash="dash"),
                    name="Garis x=y",
                )
            )
            st.plotly_chart(fig_pair, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
            st.caption("Semakin rapat titik di sekitar garis x=y, semakin tinggi kecenderungan asortatif untuk dimensi itu.")

    attr_specs = [
        ("Bansos", "bansos_num"),
        ("Internet", "internet_num"),
        ("Ponsel", "ponsel_num"),
        ("Dusun", "dusun"),
    ]
    attr_rows = []
    for lbl, col in attr_specs:
        r_attr = safe_attribute_assortativity(G, col, default=0.0)
        d_attr, s_attr = interpret_assortativity_value(r_attr)
        montes_attr = compute_montes_within_between_assortativity(
            G,
            category_attr=col,
            group_attr="cluster",
            invalid_category_values=None,
        )
        attr_rows.append(
            {
                "Metrik": lbl,
                "Kolom": col,
                "r": float(r_attr),
                "Qw*": float(montes_attr["q_w_star"]),
                "Qb*": float(montes_attr["q_b_star"]),
                "Arah": d_attr,
                "Kekuatan": s_attr,
                "Label Steinley": steinley_segregation_label(r_attr),
            }
        )
    df_attr = pd.DataFrame(attr_rows)
    audit_qw_mean = float(df_attr["Qw*"].mean()) if not df_attr.empty else 0.0
    audit_qb_mean = float(df_attr["Qb*"].mean()) if not df_attr.empty else 0.0

    with tab_attr:
        st.markdown("#### Assortativity Atribut (Biner/Kategorikal)")
        st.caption(
            "Tab ini menunjukkan atribut kebijakan/spasial mana yang paling homogen dalam jaringan."
        )
        st.markdown(
            "<div class='soft-card'><b>Cara Baca Khusus Audit (Bansos/Internet/Ponsel/Dusun):</b><br>"
            "<b>Nilai r</b> menilai seberapa kuat atribut tersebut mengikuti struktur keterhubungan pada <b>graf base</b> "
            "(semakin besar |r|, semakin kuat keterkaitannya dengan pola graf base).<br>"
            "<b>Nilai Qw*</b> dan <b>Qb*</b> baru dipakai untuk memecah konteks relasi menjadi "
            "<b>intra-klaster (within)</b> dan <b>inter-klaster (between)</b>."
            "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Langkah Hitung Attribute Assortativity (Detail)", expanded=False):
            st.markdown("1. Untuk tiap edge, baca kategori atribut di kedua ujung edge.")
            st.markdown("2. Hitung proporsi edge yang menghubungkan kategori sama vs berbeda.")
            st.markdown("3. Bandingkan dengan proporsi acak yang diharapkan.")
            st.markdown("4. Hasil normalisasinya menjadi nilai `r` attribute assortativity.")
        fig_attr = px.bar(
            df_attr,
            x="Metrik",
            y="r",
            color="r",
            color_continuous_scale="Blues",
            range_color=[-1, 1],
            title="Perbandingan Attribute Assortativity",
            hover_data=["Kolom", "Qw*", "Qb*", "Arah", "Kekuatan", "Label Steinley"],
        )
        fig_attr.add_hline(y=0.0, line_dash="dash", line_color="#475569")
        st.plotly_chart(fig_attr, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(df_attr.style.background_gradient(cmap="Blues", subset=["r"]), use_container_width=True)
        melt_attr = df_attr.melt(
            id_vars=["Metrik"],
            value_vars=["r", "Qw*", "Qb*"],
            var_name="Komponen",
            value_name="Nilai",
        )
        fig_attr_comp = px.bar(
            melt_attr,
            x="Metrik",
            y="Nilai",
            color="Komponen",
            barmode="group",
            title="Perbandingan Komponen r vs Qw* vs Qb*",
            color_discrete_sequence=["#1d4ed8", "#60a5fa", "#93c5fd"],
        )
        fig_attr_comp.add_hline(y=0.0, line_dash="dash", line_color="#475569")
        st.plotly_chart(fig_attr_comp, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        attr_choice = st.selectbox(
            "Detail Matriks Kategori per Edge",
            options=["Bansos", "Internet", "Ponsel", "Dusun"],
            index=0,
        )
        attr_edge_cols = {
            "Bansos": ("bansos_u", "bansos_v"),
            "Internet": ("internet_u", "internet_v"),
            "Ponsel": ("ponsel_u", "ponsel_v"),
            "Dusun": ("dusun_u", "dusun_v"),
        }
        cu, cv = attr_edge_cols[attr_choice]
        if not df_edges.empty:
            ct = pd.crosstab(df_edges[cu], df_edges[cv]).sort_index().sort_index(axis=1)
            heat = go.Figure(
                data=go.Heatmap(
                    z=ct.values,
                    x=[str(x) for x in ct.columns],
                    y=[str(y) for y in ct.index],
                    colorscale="Blues",
                    colorbar=dict(title="Jumlah Edge"),
                    text=ct.values,
                    texttemplate="%{text}",
                )
            )
            heat.update_layout(
                title=f"Matriks Kategori Edge: {attr_choice} (Node U vs Node V)",
                xaxis_title=f"{attr_choice} Node V",
                yaxis_title=f"{attr_choice} Node U",
                height=430,
                template="plotly_white",
            )
            st.plotly_chart(heat, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
            same_ratio = float(np.mean(df_edges[cu].astype(str).values == df_edges[cv].astype(str).values))
            pie_df = pd.DataFrame(
                [
                    {"Kondisi Edge": "Kategori Sama", "Proporsi": same_ratio},
                    {"Kondisi Edge": "Kategori Berbeda", "Proporsi": 1.0 - same_ratio},
                ]
            )
            fig_pie = px.pie(
                pie_df,
                names="Kondisi Edge",
                values="Proporsi",
                color="Kondisi Edge",
                color_discrete_sequence=["#1d4ed8", "#93c5fd"],
                hole=0.55,
                title=f"Komposisi Edge Sama vs Berbeda - {attr_choice}",
            )
            st.plotly_chart(fig_pie, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
            st.caption(
                "Semakin besar porsi 'Kategori Sama', biasanya r attribute cenderung makin positif."
            )

    montes_res = compute_montes_within_between_assortativity(
        G,
        category_attr="kategori_ikr_code",
        group_attr="cluster",
        invalid_category_values={0},
    )
    q_w_star = float(montes_res["q_w_star"])
    q_b_star = float(montes_res["q_b_star"])

    with tab_montes:
        st.markdown("#### Within-Between Assortativity (Montes) dengan Kategori BPS")
        st.markdown(
            "<div class='soft-card'><b>Pembeda Inti Audit vs BPS:</b><br>"
            "<b>Within-Between Audit</b> di sini dihitung per atribut kebijakan/spasial (Bansos, Internet, Ponsel, Dusun). "
            "Artinya category_attr berubah sesuai atribut yang diaudit.<br>"
            "<b>Within-Between BPS</b> dihitung khusus dari kategori IKR BPS (kategori_ikr_code), "
            "sehingga fokusnya stratifikasi kesejahteraan, bukan atribut program tertentu."
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Ringkasnya: pada audit, r = kekuatan keterkaitan atribut dengan graf base; "
            "Qw*/Qb* = pemisahan pola intra vs inter klaster."
        )
        with st.expander("Langkah Hitung Within-Between (Detail)", expanded=False):
            st.markdown("1. Tetapkan `x` = kategori IKR (BPS), dan `h` = klaster.")
            st.markdown("2. Pisahkan kontribusi edge dalam-klaster (within) dan antar-klaster (between).")
            st.markdown("3. Hitung skor mentah Qw, Qb lalu normalisasi jadi Qw*, Qb*.")
            st.markdown("4. Interpretasikan: Qw* tinggi = homogen dalam klaster; Qb* tinggi = homogen antar-klaster.")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Qw*", f"{q_w_star:.5f}")
        m2.metric("Qb*", f"{q_b_star:.5f}")
        m3.metric("m_w", f"{float(montes_res['m_w']):.4f}")
        m4.metric("m_b", f"{float(montes_res['m_b']):.4f}")
        df_montes = pd.DataFrame(
            [
                {"Komponen": "Qw* (Within)", "Nilai": q_w_star},
                {"Komponen": "Qb* (Between)", "Nilai": q_b_star},
            ]
        )
        fig_montes = px.bar(
            df_montes,
            x="Komponen",
            y="Nilai",
            color="Nilai",
            color_continuous_scale="Blues",
            title="Skor Normalized Within-Between Assortativity",
        )
        fig_montes.add_hline(y=0.0, line_dash="dash", line_color="#475569")
        st.plotly_chart(fig_montes, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        wb_compare_df = pd.DataFrame(
            [
                {"Kelompok": "Audit (Rata-rata 4 atribut)", "Komponen": "Qw*", "Nilai": audit_qw_mean},
                {"Kelompok": "Audit (Rata-rata 4 atribut)", "Komponen": "Qb*", "Nilai": audit_qb_mean},
                {"Kelompok": "BPS (Kategori IKR)", "Komponen": "Qw*", "Nilai": q_w_star},
                {"Kelompok": "BPS (Kategori IKR)", "Komponen": "Qb*", "Nilai": q_b_star},
            ]
        )
        fig_wb_cmp = px.bar(
            wb_compare_df,
            x="Kelompok",
            y="Nilai",
            color="Komponen",
            barmode="group",
            color_discrete_sequence=["#1d4ed8", "#93c5fd"],
            title="Perbandingan Within-Between: Audit vs BPS",
        )
        fig_wb_cmp.add_hline(y=0.0, line_dash="dash", line_color="#475569")
        st.plotly_chart(fig_wb_cmp, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(wb_compare_df, use_container_width=True)
        fig_quad = go.Figure()
        fig_quad.add_shape(type="line", x0=-1, x1=1, y0=0, y1=0, line=dict(color="#64748b", dash="dash"))
        fig_quad.add_shape(type="line", x0=0, x1=0, y0=-1, y1=1, line=dict(color="#64748b", dash="dash"))
        fig_quad.add_annotation(x=0.55, y=0.75, text="Within kuat<br>Between kuat", showarrow=False, font=dict(size=11, color="#1e3a8a"))
        fig_quad.add_annotation(x=-0.55, y=0.75, text="Within kuat<br>Between lemah", showarrow=False, font=dict(size=11, color="#1e3a8a"))
        fig_quad.add_annotation(x=0.55, y=-0.75, text="Within lemah<br>Between kuat", showarrow=False, font=dict(size=11, color="#1e3a8a"))
        fig_quad.add_annotation(x=-0.55, y=-0.75, text="Within lemah<br>Between lemah", showarrow=False, font=dict(size=11, color="#1e3a8a"))
        fig_quad.add_trace(
            go.Scatter(
                x=[q_b_star],
                y=[q_w_star],
                mode="markers+text",
                marker=dict(size=14, color="#1d4ed8"),
                text=[f"(Qb*={q_b_star:.3f}, Qw*={q_w_star:.3f})"],
                textposition="top center",
                name="Posisi Hasil",
            )
        )
        fig_quad.update_layout(
            title="Peta Interpretasi Within-Between (sumbu X=Qb*, Y=Qw*)",
            xaxis_title="Qb* (Between)",
            yaxis_title="Qw* (Within)",
            xaxis=dict(range=[-1, 1]),
            yaxis=dict(range=[-1, 1]),
            height=430,
            template="plotly_white",
        )
        st.plotly_chart(fig_quad, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        if q_w_star >= 0.30 and q_b_star >= 0.30:
            montes_note = "Homogenitas kuat baik intra maupun antar-klaster."
        elif q_w_star >= 0.30 and q_b_star < 0.10:
            montes_note = "Homogenitas kuat di dalam klaster, melemah antar-klaster."
        elif q_w_star < 0.10 and q_b_star >= 0.30:
            montes_note = "Dalam klaster campuran, tetapi antar-klaster cenderung mirip."
        else:
            montes_note = "Pola within-between cenderung campuran/netral."
        st.markdown(
            f"<div class='soft-card'><b>Interpretasi Cepat Montes:</b><br>"
            f"Qw* menunjukkan homogenitas kategori dalam klaster; Qb* menunjukkan homogenitas kategori antar-klaster.<br>"
            f"Hasil saat ini: <b>{montes_note}</b></div>",
            unsafe_allow_html=True,
        )

    with tab_ringkas:
        top_num = df_num.iloc[df_num["r"].abs().idxmax()]
        top_attr = df_attr.iloc[df_attr["r"].abs().idxmax()]
        st.markdown(
            f"<div class='soft-card'><b>Ringkasan Otomatis Assortativity:</b><br>"
            f"Numeric paling dominan: <b>{top_num['Metrik']}</b> dengan r=<b>{float(top_num['r']):.4f}</b> "
            f"({top_num['Arah']} | {top_num['Kekuatan']}).<br><br>"
            f"Attribute paling dominan: <b>{top_attr['Metrik']}</b> dengan r=<b>{float(top_attr['r']):.4f}</b> "
            f"({top_attr['Arah']} | {top_attr['Kekuatan']}).<br><br>"
            f"Within-Between BPS: Qw*=<b>{q_w_star:.4f}</b>, Qb*=<b>{q_b_star:.4f}</b>."
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("#### Checklist Membaca Hasil (Praktis)")
        st.markdown(
            "1. Lihat tanda `r`: positif (homogen), negatif (heterogen), sekitar nol (campuran)."
        )
        st.markdown(
            "2. Lihat besar `|r|`: semakin besar semakin kuat pola pemilahannya."
        )
        st.markdown(
            "3. Bandingkan `Qw*` vs `Qb*`: apakah pemilahan dominan di dalam klaster atau juga lintas klaster."
        )
        st.dataframe(df_num, use_container_width=True)
        st.dataframe(df_attr, use_container_width=True)


def render_centrality_methods_page(
    n_nodes=80,
    threshold=0.30,
    seed=42,
):
    st.markdown("<h1 class='main-header'>Halaman Metode Centrality (Simulasi Pseudo)</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='premium-hero'><b>Fokus Halaman:</b> Menjelaskan logika centrality pada graf hasil Louvain: "
        "<b>Degree, Betweenness, Closeness, dan Eigenvector</b>.</div>",
        unsafe_allow_html=True,
    )

    tab_alur, tab_rumus, tab_sim, tab_out = st.tabs(
        ["Alur Centrality", "Rumus Matematis", "Simulasi Graf Pseudo", "Output & Interpretasi"]
    )

    with tab_alur:
        flow_df = pd.DataFrame(
            [
                {"Tahap": "Input Graf Louvain", "Deskripsi": "Gunakan graf berbobot hasil proses pembobotan dan Louvain."},
                {"Tahap": "Pilih Metrik", "Deskripsi": "Pilih Degree / Betweenness / Closeness / Eigenvector."},
                {"Tahap": "Hitung Skor Node", "Deskripsi": "Setiap node mendapat nilai centrality sesuai metrik terpilih."},
                {"Tahap": "Peringkat Node", "Deskripsi": "Urutkan node dari nilai centrality tertinggi ke terendah."},
                {"Tahap": "Analisis Segmentasi", "Deskripsi": "Bandingkan top node per klaster Louvain dan per dusun."},
                {"Tahap": "Output", "Deskripsi": "Graf visual (ukuran/warna node) + tabel top node untuk keputusan audit."},
            ]
        )
        fig_flow = px.funnel(
            flow_df,
            y="Tahap",
            x=[1] * len(flow_df),
            title="Tahapan Analisis Centrality di Graf Hasil Louvain",
        )
        fig_flow.update_traces(
            marker_color="#1d4ed8",
            text=flow_df["Deskripsi"],
            textposition="inside",
            texttemplate="<b>%{y}</b><br>%{text}",
            insidetextfont=dict(size=12, color="#ffffff"),
        )
        fig_flow.update_layout(height=620, template="plotly_white", xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_flow, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        st.dataframe(flow_df, use_container_width=True)

    with tab_rumus:
        st.markdown("#### 1) Degree Centrality (weighted degree)")
        st.latex(r"C_D(i) = \sum_{j=1}^{N} A_{ij}")
        st.caption("Makna praktis: node dengan koneksi langsung paling banyak/kuat akan bernilai tinggi.")

        st.markdown("#### 2) Betweenness Centrality")
        st.latex(r"C_B(i) = \sum_{j\neq k \in V}\frac{\sigma_{jk}(i)}{\sigma_{jk}}")
        st.caption("Makna praktis: node penghubung antarbagian graf (broker/jembatan) akan bernilai tinggi.")

        st.markdown("#### 3) Closeness Centrality")
        st.latex(r"C_C(i)=\frac{1}{\sum_{j\in V}\mathrm{dist}(i,j)}")
        st.caption("Makna praktis: node yang rata-rata jaraknya paling dekat ke node lain akan bernilai tinggi.")

        st.markdown("#### 4) Eigenvector Centrality")
        st.latex(r"\lambda_{\max}\mathbf{E}=A\mathbf{E}, \quad C_E(i)=\frac{E_i}{\|\mathbf{E}\|}")
        st.caption("Makna praktis: node penting jika terhubung ke node-node penting lainnya.")

    rng = np.random.default_rng(int(seed))
    n_nodes = int(max(30, n_nodes))
    cluster_count = 3
    node_ids = [f"CT_{i+1:03d}" for i in range(n_nodes)]
    G = nx.Graph()
    rows = []
    for i, nid in enumerate(node_ids):
        cid = int(i % cluster_count)
        base = 60 + (cid * 8)
        f_a = float(np.clip(rng.normal(base + 1.0, 2.0), 40, 98))
        f_b = float(np.clip(rng.normal(base + 0.6, 2.2), 40, 98))
        f_c = float(np.clip(rng.normal(base - 0.4, 2.3), 40, 98))
        f_d = float(np.clip(rng.normal(base + 0.9, 2.1), 40, 98))
        f_e = float(np.clip(rng.normal(base + 0.2, 2.4), 40, 98))
        f_ikr = float(np.mean([f_a, f_b, f_c, f_d, f_e]))
        dusun = f"Dusun-{cid+1}"
        rows.append(
            {
                "family_id": nid,
                "nama": f"Keluarga {i+1}",
                "f_a_dari_rekap_kk": f_a,
                "f_b_dari_rekap_kk": f_b,
                "f_c_dari_rekap_kk": f_c,
                "f_d_dari_rekap_kk": f_d,
                "f_e_dari_rekap_kk": f_e,
                "f_ikr_dari_rekap_kk": f_ikr,
                "dusun": dusun,
                "cluster": cid,
            }
        )
    pseudo_df = pd.DataFrame(rows)
    for _, r in pseudo_df.iterrows():
        G.add_node(r["family_id"], **r.to_dict())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            ui, uj = node_ids[i], node_ids[j]
            ai, aj = G.nodes[ui], G.nodes[uj]
            vi = np.array(
                [
                    ai["f_a_dari_rekap_kk"],
                    ai["f_b_dari_rekap_kk"],
                    ai["f_c_dari_rekap_kk"],
                    ai["f_d_dari_rekap_kk"],
                    ai["f_e_dari_rekap_kk"],
                ],
                dtype=float,
            )
            vj = np.array(
                [
                    aj["f_a_dari_rekap_kk"],
                    aj["f_b_dari_rekap_kk"],
                    aj["f_c_dari_rekap_kk"],
                    aj["f_d_dari_rekap_kk"],
                    aj["f_e_dari_rekap_kk"],
                ],
                dtype=float,
            )
            sim = float(compute_cosine_similarity(vi, vj))
            if sim >= float(threshold):
                G.add_edge(ui, uj, weight=sim)
    if G.number_of_edges() == 0:
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                ui, uj = node_ids[i], node_ids[j]
                ai, aj = G.nodes[ui], G.nodes[uj]
                vi = np.array(
                    [
                        ai["f_a_dari_rekap_kk"],
                        ai["f_b_dari_rekap_kk"],
                        ai["f_c_dari_rekap_kk"],
                        ai["f_d_dari_rekap_kk"],
                        ai["f_e_dari_rekap_kk"],
                    ],
                    dtype=float,
                )
                vj = np.array(
                    [
                        aj["f_a_dari_rekap_kk"],
                        aj["f_b_dari_rekap_kk"],
                        aj["f_c_dari_rekap_kk"],
                        aj["f_d_dari_rekap_kk"],
                        aj["f_e_dari_rekap_kk"],
                    ],
                    dtype=float,
                )
                sim = float(compute_cosine_similarity(vi, vj))
                if sim >= 0.20:
                    G.add_edge(ui, uj, weight=sim)

    if G.number_of_edges() > 0:
        partition = community_louvain.best_partition(G, weight="weight", random_state=int(seed))
        nx.set_node_attributes(G, partition, "cluster")
    else:
        partition = {n: 0 for n in G.nodes()}
        nx.set_node_attributes(G, partition, "cluster")

    deg_vals = compute_centrality_on_similarity_graph(G, "degree")
    bet_vals = compute_centrality_on_similarity_graph(G, "betweenness")
    clo_vals = compute_centrality_on_similarity_graph(G, "closeness")
    eig_vals = compute_centrality_on_similarity_graph(G, "eigenvector")

    with tab_sim:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Node", f"{int(G.number_of_nodes())}")
        c2.metric("Edge", f"{int(G.number_of_edges())}")
        c3.metric("Threshold Similarity", f"{float(threshold):.2f}")
        c4.metric("Jumlah Klaster Louvain", f"{int(len(set(partition.values())))}")

        pos = nx.spring_layout(G, seed=int(seed), weight="weight")
        nodes = list(G.nodes())
        size_vals = [9.0 + (22.0 * float(deg_vals.get(n, 0.0)) / max(max(deg_vals.values()) if deg_vals else 1.0, 1e-9)) for n in nodes]
        fig_graph = go.Figure()
        for u, v, d in G.edges(data=True):
            fig_graph.add_trace(
                go.Scatter(
                    x=[pos[u][0], pos[v][0], None],
                    y=[pos[u][1], pos[v][1], None],
                    mode="lines",
                    line=dict(width=1.0 + 1.6 * _safe_float_metric(d.get("weight"), 0.0), color="rgba(51,65,85,0.45)"),
                    hoverinfo="none",
                    showlegend=False,
                )
            )
        fig_graph.add_trace(
            go.Scatter(
                x=[pos[n][0] for n in nodes],
                y=[pos[n][1] for n in nodes],
                mode="markers",
                marker=dict(
                    size=size_vals,
                    color=[float(eig_vals.get(n, 0.0)) for n in nodes],
                    colorscale="Turbo",
                    showscale=True,
                    colorbar=dict(title="Eigenvector"),
                    line=dict(color="#0f172a", width=0.6),
                ),
                text=[
                    f"Node: {n}<br>Klaster: {int(partition.get(n, 0))}"
                    f"<br>Degree: {float(deg_vals.get(n, 0.0)):.4f}"
                    f"<br>Betweenness: {float(bet_vals.get(n, 0.0)):.4f}"
                    f"<br>Closeness: {float(clo_vals.get(n, 0.0)):.4f}"
                    f"<br>Eigenvector: {float(eig_vals.get(n, 0.0)):.4f}"
                    for n in nodes
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )
        fig_graph.update_layout(
            title="Graf Pseudo Centrality (ukuran = Degree, warna = Eigenvector)",
            height=560,
            template="plotly_white",
            margin=dict(l=20, r=20, t=60, b=20),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        st.plotly_chart(fig_graph, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    with tab_out:
        df_cent = pd.DataFrame(
            [
                {
                    "family_id": n,
                    "Klaster Louvain": int(partition.get(n, 0)),
                    "Dusun": G.nodes[n].get("dusun", "-"),
                    "Degree": float(deg_vals.get(n, 0.0)),
                    "Betweenness": float(bet_vals.get(n, 0.0)),
                    "Closeness": float(clo_vals.get(n, 0.0)),
                    "Eigenvector": float(eig_vals.get(n, 0.0)),
                }
                for n in G.nodes()
            ]
        ).sort_values("Degree", ascending=False).reset_index(drop=True)
        st.markdown("#### Top 10 Node per Metrik")
        m1, m2 = st.columns(2)
        with m1:
            st.caption("Top 10 Degree")
            st.dataframe(df_cent.sort_values("Degree", ascending=False).head(10), use_container_width=True)
            st.caption("Top 10 Betweenness")
            st.dataframe(df_cent.sort_values("Betweenness", ascending=False).head(10), use_container_width=True)
        with m2:
            st.caption("Top 10 Closeness")
            st.dataframe(df_cent.sort_values("Closeness", ascending=False).head(10), use_container_width=True)
            st.caption("Top 10 Eigenvector")
            st.dataframe(df_cent.sort_values("Eigenvector", ascending=False).head(10), use_container_width=True)

        st.markdown("#### Ringkasan per Klaster")
        df_cluster = (
            df_cent.groupby("Klaster Louvain", as_index=False)
            .agg(
                Jumlah_Node=("family_id", "count"),
                Rerata_Degree=("Degree", "mean"),
                Rerata_Betweenness=("Betweenness", "mean"),
                Rerata_Closeness=("Closeness", "mean"),
                Rerata_Eigenvector=("Eigenvector", "mean"),
            )
            .sort_values("Klaster Louvain")
            .reset_index(drop=True)
        )
        st.dataframe(df_cluster, use_container_width=True)
        st.caption(
            "Cara baca sederhana: Degree tinggi = pusat interaksi lokal; Betweenness tinggi = node jembatan; "
            "Closeness tinggi = cepat menjangkau node lain; Eigenvector tinggi = penting karena terhubung ke node penting."
        )


def summarize_all_methods(df_kk, desa_col, basis_col, onehot_round_decimals, threshold_grid):
    method_specs = [
        ("Cosine Similarity", "cosine"),
        ("Jaccard Index", "jaccard"),
        ("Pearson Correlation", "pearson"),
    ]
    rows = []
    desa_values = sorted(df_kk[desa_col].dropna().astype(str).str.strip().unique().tolist())

    for desa_name in desa_values:
        df_v = df_kk[df_kk[desa_col].astype(str).str.strip() == desa_name].copy()
        total_nodes_desa = int(df_v["family_id"].nunique()) if "family_id" in df_v.columns else 0
        if "f_ikr_dari_rekap_kk" in df_v.columns:
            df_v = add_bps_ikr_category(df_v, ikr_col="f_ikr_dari_rekap_kk")

        for method_label, method_key in method_specs:
            res = build_sna_network(
                df_v,
                basis_col,
                0.40,
                lcc_only=True,
                similarity_method=method_key,
                force_louvain_lcc=True,
                threshold_grid=threshold_grid,
                edge_feature_cols=EDGE_REKAP_COLS,
                onehot_round_decimals=onehot_round_decimals,
            )

            if not res:
                rows.append(
                    {
                        "Desa": desa_name,
                        "Metode": method_label,
                        "Jumlah Node Desa": total_nodes_desa,
                        "Jumlah Node": int(df_v["family_id"].nunique()) if "family_id" in df_v.columns else 0,
                        "Jumlah Edge": 0,
                        "Density": 0.0,
                        "Jumlah Klaster": 0,
                        "Modularity": 0.0,
                        "Threshold": np.nan,
                        "Status": "Data tidak mencukupi untuk graf",
                    }
                )
                continue

            G, partition, _, meta = res
            rows.append(
                    {
                        "Desa": desa_name,
                        "Metode": method_label,
                        "Jumlah Node Desa": total_nodes_desa,
                        "Jumlah Node": int(G.number_of_nodes()),
                        "Jumlah Edge": int(G.number_of_edges()),
                    "Density": float(nx.density(G)) if G.number_of_nodes() > 1 else 0.0,
                    "Jumlah Klaster": int(len(set(partition.values()))),
                    "Modularity": _safe_float_metric(community_louvain.modularity(partition, G, weight="weight"), default=0.0),
                    "Threshold": float(meta.get("threshold_selected", np.nan)),
                    "Status": "OK",
                }
            )

    return pd.DataFrame(rows)


def min_max_scale(series):
    s = pd.Series(series, dtype="float64").replace([np.inf, -np.inf], np.nan)
    if s.dropna().empty:
        return pd.Series([0.0] * len(s), index=s.index)
    s_min = float(s.min())
    s_max = float(s.max())
    if abs(s_max - s_min) <= 1e-12:
        return pd.Series([1.0] * len(s), index=s.index)
    return (s - s_min) / (s_max - s_min)


def build_modularity_pivot_table(result_df):
    valid_df = result_df[result_df["Status"] == "OK"].copy()
    if valid_df.empty:
        return pd.DataFrame()

    method_order = valid_df["Metode"].dropna().astype(str).tolist()
    method_order = list(dict.fromkeys(method_order))

    pivot_df = (
        valid_df.pivot(index="Desa", columns="Metode", values="Modularity")
        .reindex(columns=method_order)
        .sort_index()
        .reset_index()
    )
    pivot_df.columns.name = None
    return pivot_df


def dataframe_to_png_bytes(df, title, subtitle=None):
    if df.empty:
        return None

    try:
        import matplotlib.pyplot as plt
        from matplotlib import cm, colors
    except Exception:
        return None

    render_df = df.copy()
    method_cols = [col for col in render_df.columns if col != "Desa"]
    if not method_cols:
        return None

    for col in method_cols:
        render_df[col] = pd.to_numeric(render_df[col], errors="coerce")

    display_df = render_df.copy()
    for col in method_cols:
        display_df[col] = display_df[col].map(lambda x: "-" if pd.isna(x) else f"{float(x):.4f}")

    valid_values = render_df[method_cols].to_numpy(dtype=float)
    valid_values = valid_values[~np.isnan(valid_values)]
    vmin = float(valid_values.min()) if len(valid_values) else 0.0
    vmax = float(valid_values.max()) if len(valid_values) else 1.0
    if abs(vmax - vmin) <= 1e-12:
        vmax = vmin + 1.0

    cmap = cm.get_cmap("YlGnBu")
    norm = colors.Normalize(vmin=vmin, vmax=vmax)

    n_rows = len(display_df)
    n_cols = len(display_df.columns)
    fig_width = max(8.5, 2.8 + (n_cols * 2.15))
    fig_height = max(2.8, 1.9 + (n_rows * 0.42))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=200)
    fig.patch.set_facecolor("white")
    ax.axis("off")

    title_y = 0.975
    if title:
        fig.text(0.02, title_y, title, ha="left", va="top", fontsize=16, fontweight="bold", color="#0f172a")
    if subtitle:
        fig.text(0.02, title_y - 0.035, subtitle, ha="left", va="top", fontsize=10, color="#475569")

    fig.text(
        0.02,
        0.02,
        "Sel modularity tertinggi di setiap desa diberi penekanan.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#475569",
    )

    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        cellLoc="center",
        colLoc="center",
        bbox=[0.0, 0.06, 1.0, 0.84],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.2)
    table.scale(1.0, 1.35)

    for col_idx in range(n_cols):
        header_cell = table[(0, col_idx)]
        header_cell.set_facecolor("#0f172a")
        header_cell.set_text_props(color="white", weight="bold")
        header_cell.set_edgecolor("#cbd5e1")
        header_cell.set_linewidth(0.8)

    for row_idx in range(1, n_rows + 1):
        raw_row = render_df.iloc[row_idx - 1]
        row_values = pd.to_numeric(raw_row[method_cols], errors="coerce")
        row_max = row_values.max(skipna=True) if row_values.notna().any() else np.nan
        zebra_bg = "#ffffff" if row_idx % 2 else "#f8fafc"

        for col_idx, col_name in enumerate(display_df.columns):
            cell = table[(row_idx, col_idx)]
            cell.set_edgecolor("#e2e8f0")
            cell.set_linewidth(0.8)

            if col_name == "Desa":
                cell.set_facecolor(zebra_bg)
                cell.set_text_props(color="#0f172a", weight="bold", ha="left")
                continue

            raw_value = raw_row[col_name]
            if pd.isna(raw_value):
                cell.set_facecolor("#e2e8f0")
                cell.set_text_props(color="#64748b")
                continue

            rgba = np.array(cmap(norm(float(raw_value)))[:3])
            blended = tuple((0.72 * np.array([1.0, 1.0, 1.0])) + (0.28 * rgba))
            cell.set_facecolor(blended)
            cell.set_text_props(color="#0f172a")

            if pd.notna(row_max) and np.isclose(float(raw_value), float(row_max), atol=1e-9):
                emphasized = tuple((0.52 * np.array([1.0, 1.0, 1.0])) + (0.48 * rgba))
                cell.set_facecolor(emphasized)
                cell.set_text_props(color="#0f172a", weight="bold")
                cell.set_edgecolor("#0f766e")
                cell.set_linewidth(1.6)

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def build_journal_score_summary(result_df):
    df = result_df.copy()
    df["Valid Graph"] = (df["Status"] == "OK").astype(int)
    df["Node Coverage"] = np.where(
        df["Jumlah Node Desa"] > 0,
        df["Jumlah Node"] / df["Jumlah Node Desa"],
        0.0,
    )

    valid_df = df[df["Status"] == "OK"].copy()
    if valid_df.empty:
        return pd.DataFrame(), pd.DataFrame(), None

    max_modularity_per_desa = valid_df.groupby("Desa")["Modularity"].transform("max")
    valid_df["Village Win"] = (
        np.isclose(valid_df["Modularity"], max_modularity_per_desa, atol=1e-9)
    ).astype(int)

    agg_df = (
        valid_df.groupby("Metode", as_index=False)
        .agg(
            Mean_Modularity=("Modularity", "mean"),
            Mean_Node_Coverage=("Node Coverage", "mean"),
            Mean_Clusters=("Jumlah Klaster", "mean"),
            Mean_Density=("Density", "mean"),
            Success_Rate=("Valid Graph", "mean"),
            Village_Win_Rate=("Village Win", "mean"),
        )
    )

    agg_df["Score_Modularity"] = min_max_scale(agg_df["Mean_Modularity"])
    agg_df["Score_Coverage"] = min_max_scale(agg_df["Mean_Node_Coverage"])
    agg_df["Score_Success"] = min_max_scale(agg_df["Success_Rate"])
    agg_df["Score_WinRate"] = min_max_scale(agg_df["Village_Win_Rate"])
    agg_df["Composite_Score"] = (
        0.50 * agg_df["Score_Modularity"]
        + 0.20 * agg_df["Score_Coverage"]
        + 0.15 * agg_df["Score_Success"]
        + 0.15 * agg_df["Score_WinRate"]
    )
    agg_df = agg_df.sort_values(
        ["Composite_Score", "Mean_Modularity", "Village_Win_Rate"],
        ascending=False,
    ).reset_index(drop=True)
    agg_df["Peringkat"] = np.arange(1, len(agg_df) + 1)

    score_long = agg_df.melt(
        id_vars=["Metode"],
        value_vars=["Score_Modularity", "Score_Coverage", "Score_Success", "Score_WinRate"],
        var_name="Komponen",
        value_name="Skor",
    )
    score_long["Komponen"] = score_long["Komponen"].map(
        {
            "Score_Modularity": "Modularity",
            "Score_Coverage": "Coverage Node",
            "Score_Success": "Success Rate",
            "Score_WinRate": "Win Rate Desa",
        }
    )

    winner_method = agg_df.iloc[0]["Metode"] if not agg_df.empty else None
    return agg_df, score_long, winner_method


def render_journal_comparison_section(result_df):
    score_df, radar_df, winner_method = build_journal_score_summary(result_df)
    if score_df.empty or winner_method is None:
        st.warning("Skor komparatif belum dapat dihitung karena belum ada graf valid.")
        return

    winner_row = score_df.iloc[0]
    runner_row = score_df.iloc[1] if len(score_df) > 1 else None
    win_gap = (
        float(winner_row["Composite_Score"] - runner_row["Composite_Score"])
        if runner_row is not None
        else float(winner_row["Composite_Score"])
    )

    st.markdown("### Sintesis Jurnal")
    st.markdown(
        f"""
        <div class="premium-hero">
            <b>Metode unggulan:</b> {winner_method}<br>
            <b>Composite score:</b> {float(winner_row['Composite_Score']):.3f}<br>
            <b>Rata-rata modularity:</b> {float(winner_row['Mean_Modularity']):.4f}<br>
            <b>Rata-rata coverage node:</b> {float(winner_row['Mean_Node_Coverage']):.2%}<br>
            <b>Win rate antar desa:</b> {float(winner_row['Village_Win_Rate']):.2%}
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Metode Terbaik", winner_method)
    m2.metric("Composite Score", f"{float(winner_row['Composite_Score']):.3f}")
    m3.metric("Gap vs Runner-Up", f"{win_gap:.3f}")
    m4.metric("Mean Modularity", f"{float(winner_row['Mean_Modularity']):.4f}")

    st.caption(
        "Skoring jurnal menempatkan modularity sebagai komponen utama (50%) karena Louvain secara langsung mengoptimalkan modularity. "
        "Komponen lain dipakai untuk memastikan metode terbaik tidak hanya unggul secara teoritis, tetapi juga stabil dan representatif di seluruh desa."
    )

    viz1, viz2 = st.columns([1.15, 1.0], gap="large")
    with viz1:
        fig_score = px.bar(
            score_df,
            x="Metode",
            y="Composite_Score",
            color="Metode",
            text=score_df["Composite_Score"].map(lambda x: f"{float(x):.3f}"),
            title="Skor Komposit Metode Pembobotan",
        )
        fig_score.update_layout(
            template="plotly_white",
            showlegend=False,
            yaxis_title="Composite Score",
            xaxis_title="Metode",
        )
        fig_score.update_traces(textposition="outside")
        st.plotly_chart(fig_score, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    with viz2:
        fig_radar = go.Figure()
        for method_name in score_df["Metode"].tolist():
            sub = radar_df[radar_df["Metode"] == method_name]
            categories = sub["Komponen"].tolist()
            values = sub["Skor"].tolist()
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=values + values[:1],
                    theta=categories + categories[:1],
                    fill="toself",
                    name=method_name,
                )
            )
        fig_radar.update_layout(
            template="plotly_white",
            title="Radar Skor Komponen",
            polar=dict(radialaxis=dict(range=[0, 1], tickformat=".1f")),
            showlegend=True,
        )
        st.plotly_chart(fig_radar, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    modularity_table_df = build_modularity_pivot_table(result_df)

    viz3, viz4 = st.columns([1.05, 1.1], gap="large")
    with viz3:
        metric_long = score_df.melt(
            id_vars=["Metode"],
            value_vars=[
                "Mean_Modularity",
                "Mean_Node_Coverage",
                "Success_Rate",
                "Village_Win_Rate",
            ],
            var_name="Metrik",
            value_name="Nilai",
        )
        metric_long["Metrik"] = metric_long["Metrik"].map(
            {
                "Mean_Modularity": "Mean Modularity",
                "Mean_Node_Coverage": "Mean Coverage Node",
                "Success_Rate": "Success Rate",
                "Village_Win_Rate": "Win Rate Desa",
            }
        )
        fig_metric = px.bar(
            metric_long,
            x="Metrik",
            y="Nilai",
            color="Metode",
            barmode="group",
            title="Perbandingan Indikator Inti",
        )
        fig_metric.update_layout(template="plotly_white", yaxis_title="Nilai", xaxis_title="")
        st.plotly_chart(fig_metric, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    with viz4:
        if not modularity_table_df.empty:
            heat_df = modularity_table_df.set_index("Desa")
            fig_heat = px.imshow(
                heat_df,
                text_auto=".3f",
                color_continuous_scale="YlGnBu",
                aspect="auto",
                title="Heatmap Modularity per Desa",
                labels=dict(x="Metode", y="Desa", color="Modularity"),
            )
            fig_heat.update_layout(template="plotly_white")
            st.plotly_chart(fig_heat, use_container_width=True, config=PLOTLY_DRAW_CONFIG)
        else:
            st.info("Heatmap modularity belum tersedia karena belum ada graf valid per desa.")

    if not modularity_table_df.empty:
        modularity_line_df = (
            modularity_table_df
            .melt(id_vars="Desa", var_name="Metode", value_name="Modularity")
            .dropna(subset=["Modularity"])
        )
        desa_order = modularity_table_df["Desa"].astype(str).tolist()
        fig_modularity_line = px.line(
            modularity_line_df,
            x="Desa",
            y="Modularity",
            color="Metode",
            markers=True,
            category_orders={"Desa": desa_order},
            title="Grafik Modularity per Desa",
        )
        fig_modularity_line.update_traces(
            mode="lines+markers",
            line=dict(width=3),
            marker=dict(size=8),
            hovertemplate="Metode=%{fullData.name}<br>Desa=%{x}<br>Modularity=%{y:.4f}<extra></extra>",
        )
        fig_modularity_line.update_layout(
            template="plotly_white",
            height=520,
            xaxis_title="Nama Desa",
            yaxis_title="Nilai Modularity",
            legend_title_text="Metode",
            xaxis=dict(tickangle=-35),
            yaxis=dict(rangemode="tozero"),
            hovermode="x unified",
        )
        st.markdown("#### Grafik Modularity per Desa")
        st.caption("Sumbu X menampilkan nama desa dan sumbu Y menunjukkan nilai modularity untuk setiap metode pembobotan.")
        st.plotly_chart(fig_modularity_line, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

        fig_modularity_bar = px.bar(
            modularity_line_df,
            x="Desa",
            y="Modularity",
            color="Metode",
            barmode="group",
            category_orders={"Desa": desa_order},
            title="Diagram Batang Perbandingan Modularity per Desa",
        )
        fig_modularity_bar.update_traces(
            hovertemplate="Metode=%{fullData.name}<br>Desa=%{x}<br>Modularity=%{y:.4f}<extra></extra>"
        )
        fig_modularity_bar.update_layout(
            template="plotly_white",
            height=540,
            xaxis_title="Nama Desa",
            yaxis_title="Nilai Modularity",
            legend_title_text="Metode",
            xaxis=dict(tickangle=-35),
            yaxis=dict(rangemode="tozero"),
            hovermode="x unified",
            bargap=0.18,
            bargroupgap=0.08,
        )
        st.markdown("#### Diagram Batang Modularity per Desa")
        st.caption("Diagram batang ini memudahkan perbandingan langsung nilai modularity antar metode pada setiap desa.")
        st.plotly_chart(fig_modularity_bar, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

        method_cols = [col for col in modularity_table_df.columns if col != "Desa"]
        modularity_table_png = dataframe_to_png_bytes(
            modularity_table_df,
            title="Tabel Modularity per Desa",
            subtitle="Nilai modularity setiap desa untuk masing-masing pendekatan pembobotan.",
        )

        st.markdown("#### Tabel Modularity per Desa")
        st.caption("Fokus tabel ini hanya pada nilai modularity per desa. Nilai tertinggi di tiap desa diberi highlight.")
        if modularity_table_png:
            st.download_button(
                "Download Tabel PNG",
                data=modularity_table_png,
                file_name="tabel_modularity_per_desa.png",
                mime="image/png",
            )

        modularity_styler = (
            modularity_table_df.style
            .format({col: "{:.4f}" for col in method_cols}, na_rep="-")
            .background_gradient(cmap="YlGnBu", subset=method_cols)
            .highlight_max(
                subset=method_cols,
                axis=1,
                props="font-weight: 700; color: #0f172a; border: 2px solid #0f766e;",
            )
        )
        st.dataframe(modularity_styler, use_container_width=True, hide_index=True)

    plot_df = result_df[result_df["Status"] == "OK"].copy()
    plot_df["Node Coverage"] = np.where(
        plot_df["Jumlah Node Desa"] > 0,
        plot_df["Jumlah Node"] / plot_df["Jumlah Node Desa"],
        0.0,
    )
    fig_scatter = px.scatter(
        plot_df,
        x="Node Coverage",
        y="Modularity",
        size="Jumlah Klaster",
        color="Metode",
        hover_data=["Desa", "Jumlah Node", "Jumlah Edge", "Density"],
        title="Trade-off Coverage Node vs Modularity",
    )
    fig_scatter.update_layout(
        template="plotly_white",
        xaxis_tickformat=".0%",
        xaxis_title="Coverage Node di LCC",
        yaxis_title="Modularity",
    )
    st.plotly_chart(fig_scatter, use_container_width=True, config=PLOTLY_DRAW_CONFIG)

    score_table = score_df.copy()
    score_table["Mean_Modularity"] = score_table["Mean_Modularity"].map(lambda x: f"{float(x):.4f}")
    score_table["Mean_Node_Coverage"] = score_table["Mean_Node_Coverage"].map(lambda x: f"{float(x):.2%}")
    score_table["Success_Rate"] = score_table["Success_Rate"].map(lambda x: f"{float(x):.2%}")
    score_table["Village_Win_Rate"] = score_table["Village_Win_Rate"].map(lambda x: f"{float(x):.2%}")
    score_table["Composite_Score"] = score_table["Composite_Score"].map(lambda x: f"{float(x):.3f}")
    st.markdown("### Tabel Skoring Metode")
    st.dataframe(score_table, use_container_width=True, hide_index=True)

    reasoning_lines = [
        f"Metode dengan skor total tertinggi adalah {winner_method}, sehingga paling layak dijadikan metode pembobotan utama untuk analisis Louvain pada dataset ini.",
        f"{winner_method} unggul terutama pada rata-rata modularity {float(winner_row['Mean_Modularity']):.4f}, yang paling relevan karena Louvain memang mengoptimalkan pemisahan komunitas melalui modularity.",
        f"Coverage node rata-rata {float(winner_row['Mean_Node_Coverage']):.2%} menunjukkan metode ini tidak hanya menghasilkan komunitas yang tajam, tetapi juga tetap merepresentasikan proporsi node desa yang baik pada komponen utama.",
        f"Win rate antar desa sebesar {float(winner_row['Village_Win_Rate']):.2%} memberi argumen bahwa keunggulan metode ini konsisten lintas desa, bukan hanya menang pada satu atau dua kasus.",
    ]
    if runner_row is not None:
        reasoning_lines.append(
            f"Selisih skor {win_gap:.3f} terhadap runner-up {runner_row['Metode']} menunjukkan perbedaan performa yang cukup jelas dalam kerangka evaluasi ini."
        )

    st.markdown("### Narasi Siap Pakai")
    for line in reasoning_lines:
        st.markdown(f"- {line}")


# =========================================================
# 3. HALAMAN RINGKAS PERBANDINGAN
# =========================================================
with st.sidebar:
    logo_col, title_col = st.columns([1, 3], gap="small")
    with logo_col:
        logo_data_uri = get_logo_data_uri(LOGO_PATH)
        logo_inner_html = (
            f"<img src='{logo_data_uri}' class='sidebar-logo-img' alt='Logo SNA' />"
            if logo_data_uri
            else "<div class='sidebar-logo-fallback'>SNA</div>"
        )
        st.markdown(
            f"<div class='sidebar-logo-shell'><div class='sidebar-logo-disc'>{logo_inner_html}</div></div>",
            unsafe_allow_html=True,
        )
    with title_col:
        st.markdown(
            "<div style='padding-top:8px; font-size:1.05rem; font-weight:700; color:#E5E7EB;'>SNA Data Desa Presisi</div>",
            unsafe_allow_html=True,
        )

uploaded_file = st.sidebar.file_uploader("Unggah Database", type=["csv", "xlsx"])
render_global_header()

st.markdown("<h1 class='main-header'>Perbandingan Hasil Metode Pembobotan Semua Desa</h1>", unsafe_allow_html=True)
st.markdown(
    """
    <div class="soft-card">
        Fokus halaman ini hanya pada komparasi hasil evaluasi graf untuk seluruh desa
        dengan metode <b>Cosine Similarity</b>, <b>Jaccard Index</b>, dan <b>Pearson Correlation</b>.
        Alur pembentukan graf, threshold otomatis distribusi, dan algoritma Louvain tetap mengikuti versi sebelumnya.
    </div>
    """,
    unsafe_allow_html=True,
)

if not uploaded_file:
    st.info("Selamat Datang. Silakan unggah database desa untuk menampilkan tabel perbandingan semua metode.")
    st.stop()

df_kk = load_and_clean_ddp(uploaded_file)
if df_kk is None or df_kk.empty:
    st.stop()

col_desa = "deskel" if "deskel" in df_kk.columns else "desa"
basis_candidates = [
    ("IKR Rekap KK", "f_ikr_dari_rekap_kk"),
    ("IPM Mikro", "ipm_mikro"),
    ("Ekonomi", "indeks_pengeluaran"),
    ("Kesehatan", "indeks_kesehatan"),
    ("Pendidikan", "indeks_pendidikan"),
]
available_basis = []
for label, col in basis_candidates:
    if col in df_kk.columns:
        available_basis.append((label, col))
if not available_basis:
    numeric_cols = []
    for c in df_kk.columns:
        s = pd.to_numeric(df_kk[c], errors="coerce")
        if s.notna().sum() >= max(3, int(0.2 * len(df_kk))):
            numeric_cols.append(c)
    available_basis = [(f"Kolom Numerik: {c}", c) for c in numeric_cols[:10]]
if not available_basis:
    st.error("Tidak ada kolom numerik yang bisa dijadikan basis jaringan.")
    st.stop()

with st.sidebar:
    basis_col = st.selectbox("Basis Jaringan", available_basis, format_func=lambda x: x[0])[1]
    onehot_round_decimals = st.selectbox(
        "Pembulatan One-Hot",
        options=[0, 2, 1],
        format_func=lambda d: "Bilangan bulat (tanpa koma)" if d == 0 else f"{d} angka di belakang koma",
        index=0,
    )

threshold_grid = [round(x, 1) for x in np.arange(0.1, 1.0, 0.1)]
result_df = summarize_all_methods(
    df_kk=df_kk,
    desa_col=col_desa,
    basis_col=basis_col,
    onehot_round_decimals=onehot_round_decimals,
    threshold_grid=threshold_grid,
)
if result_df.empty:
    st.warning("Belum ada hasil evaluasi yang bisa ditampilkan.")
    st.stop()

k1, k2, k3 = st.columns(3)
k1.metric("Jumlah Desa", int(result_df["Desa"].nunique()))
k2.metric("Jumlah KK", int(df_kk["family_id"].nunique()) if "family_id" in df_kk.columns else 0)
k3.metric("Jumlah Evaluasi", int(len(result_df)))

render_journal_comparison_section(result_df)

display_df = result_df.copy()
display_df["Density"] = display_df["Density"].map(lambda x: f"{float(x):.4f}")
display_df["Modularity"] = display_df["Modularity"].map(lambda x: f"{float(x):.4f}")
display_df["Threshold"] = display_df["Threshold"].map(lambda x: "-" if pd.isna(x) else f"{float(x):.2f}")

st.markdown("### Tabel Hasil Semua Desa")
st.dataframe(display_df, use_container_width=True, hide_index=True)

pivot_df = result_df.copy()
pivot_df["Ringkasan"] = pivot_df.apply(
    lambda row: (
        f"Node {int(row['Jumlah Node'])} | "
        f"Edge {int(row['Jumlah Edge'])} | "
        f"Density {float(row['Density']):.4f} | "
        f"Klaster {int(row['Jumlah Klaster'])} | "
        f"Modularity {float(row['Modularity']):.4f}"
    ),
    axis=1,
)
pivot_df = pivot_df.pivot(index="Desa", columns="Metode", values="Ringkasan").reset_index()

st.markdown("### Ringkasan Per Desa")
st.dataframe(pivot_df, use_container_width=True, hide_index=True)

with st.expander("Data Kepala Keluarga yang Dipakai", expanded=False):
    preview_cols = [col for col in ["family_id", col_desa, *EDGE_REKAP_COLS] if col in df_kk.columns]
    st.dataframe(df_kk[preview_cols], use_container_width=True, hide_index=True)
