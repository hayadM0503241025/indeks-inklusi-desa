from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

import id as iid_pipeline


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / ".streamlit_runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
OUTPUT_CACHE_DIR = RUNTIME_DIR / "outputs"
DEFAULT_INPUT_CANDIDATES = (
    BASE_DIR / "data_asli.parquet",
    BASE_DIR / "data_asli.csv",
    BASE_DIR / "data_asli.xlsx",
    BASE_DIR / "data_asli.xls",
)

for directory in (RUNTIME_DIR, UPLOAD_DIR, OUTPUT_CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)


TABLE_SPECS: dict[str, dict[str, Any]] = {
    "data_keluarga": {
        "filename": "data_keluarga.csv",
        "required": True,
    },
    "penjelasan_variabel": {
        "filename": "penjelasan_variabel.csv",
        "required": True,
    },
    "indeks_desa": {
        "filename": "indeks_desa.csv",
        "required": False,
    },
}

INDICATOR_LABELS_DEFAULT = {
    "indikator_A": "Kepemilikan HP",
    "indikator_B": "Kecukupan HP",
    "indikator_C": "Perangkat digital produktif",
    "indikator_D": "Akses internet rumah tangga",
    "indikator_E": "Pendidikan kepala keluarga",
    "indikator_F": "Rasio partisipasi sekolah",
    "indikator_G": "Organisasi kepala keluarga",
    "indikator_H": "Organisasi anggota keluarga",
    "indikator_I": "Partisipasi masyarakat kepala",
    "indikator_J": "Partisipasi masyarakat anggota",
    "indikator_K": "Penggunaan media sosial",
    "indikator_L": "Media informasi",
    "indikator_M": "Partisipasi kebijakan",
}

DIMENSION_LABELS_DEFAULT = {
    "dimensi_A": "Akses perangkat",
    "dimensi_B": "Konektivitas internet",
    "dimensi_C": "Kapasitas manusia",
    "dimensi_D": "Penggunaan digital",
    "dimensi_E": "Lingkungan sosial",
}

CATEGORY_COLORS = {
    "sangat rendah": "#9f1239",
    "rendah": "#ea580c",
    "sedang": "#eab308",
    "tinggi": "#14b8a6",
    "sangat tinggi": "#2563eb",
    iid_pipeline.UNSCORED_IID_CATEGORY_LABEL: "#64748b",
}


st.set_page_config(
    page_title="Analisis PCA",
    page_icon="assets/logo-banner2.png" if (BASE_DIR / "assets" / "logo-banner2.png").exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-start: #f6f7f1;
            --bg-end: #eef6f8;
            --card: rgba(255, 255, 255, 0.90);
            --border: rgba(15, 23, 42, 0.08);
            --shadow: 0 20px 45px rgba(15, 23, 42, 0.08);
            --text-main: #163249;
            --text-soft: #5b7083;
            --accent: #0f766e;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 32%),
                radial-gradient(circle at top right, rgba(37, 99, 235, 0.10), transparent 30%),
                linear-gradient(180deg, var(--bg-start) 0%, var(--bg-end) 100%);
        }
        .main .block-container {
            max-width: 1450px;
            padding-top: 1.15rem;
            padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(22, 50, 73, 0.98) 0%, rgba(11, 31, 49, 0.98) 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        section[data-testid="stSidebar"] * {
            color: #f8fafc !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"] > div,
        section[data-testid="stSidebar"] .stSlider {
            background: rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
        }
        .hero-shell {
            padding: 1.6rem 1.7rem;
            border-radius: 26px;
            background:
                linear-gradient(135deg, rgba(22, 50, 73, 0.95) 0%, rgba(15, 118, 110, 0.92) 52%, rgba(21, 128, 61, 0.84) 100%);
            color: white;
            box-shadow: 0 28px 55px rgba(15, 23, 42, 0.16);
            border: 1px solid rgba(255, 255, 255, 0.18);
            overflow: hidden;
        }
        .hero-kicker {
            letter-spacing: 0.16em;
            font-size: 0.75rem;
            text-transform: uppercase;
            opacity: 0.78;
            margin-bottom: 0.35rem;
            font-weight: 700;
        }
        .hero-title {
            font-size: 2.1rem;
            line-height: 1.05;
            font-weight: 800;
            margin: 0;
        }
        .hero-subtitle {
            margin-top: 0.65rem;
            max-width: 980px;
            font-size: 1.02rem;
            line-height: 1.55;
            color: rgba(248, 250, 252, 0.92);
        }
        .badge-row {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        .badge {
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.18);
            padding: 0.42rem 0.75rem;
            border-radius: 999px;
            font-size: 0.85rem;
        }
        div[data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid var(--border);
            padding: 0.9rem 1rem;
            border-radius: 18px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(8px);
        }
        div[data-testid="stMetricLabel"] {
            color: var(--text-soft);
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            color: var(--text-main);
            font-weight: 800;
        }
        .note {
            color: var(--text-soft);
            font-size: 0.95rem;
            line-height: 1.55;
            margin-top: 0.15rem;
            margin-bottom: 0.9rem;
        }
        .pill {
            display: inline-block;
            padding: 0.28rem 0.65rem;
            background: rgba(15, 118, 110, 0.12);
            color: #0f766e;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.82rem;
            margin-bottom: 0.8rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.45rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.82);
            border-radius: 999px;
            padding: 0.55rem 0.95rem;
            border: 1px solid rgba(15, 23, 42, 0.08);
        }
        .stTabs [aria-selected="true"] {
            background: #163249 !important;
            color: white !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def detect_default_output_dir() -> Path:
    candidates = (
        BASE_DIR / "hasil_indeks_digital_uji2",
        BASE_DIR / "hasil_indeks_digital_skema_rekomendasi_codex",
        BASE_DIR / "hasil_indeks_digital",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return BASE_DIR / "hasil_indeks_digital_uji2"


def detect_default_input_path() -> Path | None:
    for candidate in DEFAULT_INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def format_number(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "-"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def format_percent(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def build_file_signature(path: Path) -> str:
    stats = path.stat()
    raw = f"{path.resolve()}|{stats.st_size}|{stats.st_mtime_ns}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def build_folder_signature(output_dir: Path) -> str:
    parts: list[str] = []
    for spec in TABLE_SPECS.values():
        csv_path = output_dir / spec["filename"]
        parquet_path = csv_path.with_suffix(".parquet")
        for file_path in (csv_path, parquet_path):
            if file_path.exists():
                stats = file_path.stat()
                parts.append(f"{file_path.name}|{stats.st_size}|{stats.st_mtime_ns}")
    if not parts:
        return "empty"
    return hashlib.md5("|".join(sorted(parts)).encode("utf-8")).hexdigest()[:12]


def save_uploaded_file(uploaded_file: Any) -> Path:
    content = uploaded_file.getvalue()
    digest = hashlib.md5(content).hexdigest()[:12]
    safe_name = uploaded_file.name.replace(" ", "_")
    target_path = UPLOAD_DIR / f"{digest}_{safe_name}"
    if not target_path.exists():
        target_path.write_bytes(content)
    return target_path


@st.cache_data(show_spinner=False)
def load_output_bundle_cached(output_dir_str: str, folder_signature: str) -> dict[str, Any]:
    del folder_signature
    output_dir = Path(output_dir_str)
    if not output_dir.exists():
        raise FileNotFoundError(f"Folder output tidak ditemukan: {output_dir}")

    tables: dict[str, pd.DataFrame] = {}
    missing_required: list[str] = []
    for key, spec in TABLE_SPECS.items():
        csv_path = output_dir / spec["filename"]
        parquet_path = csv_path.with_suffix(".parquet")
        if csv_path.exists():
            tables[key] = pd.read_csv(csv_path, low_memory=False)
        elif parquet_path.exists():
            tables[key] = pd.read_parquet(parquet_path)
        elif spec["required"]:
            missing_required.append(f"{spec['filename']} atau {parquet_path.name}")

    if missing_required:
        raise FileNotFoundError(f"File inti untuk PCA tidak lengkap: {', '.join(missing_required)}")

    meta = {
        "output_dir": str(output_dir.resolve()),
        "source_label": "Folder hasil siap pakai",
    }
    return {"tables": tables, "meta": meta}


@st.cache_data(show_spinner=False)
def process_input_bundle_cached(
    input_path_str: str,
    input_signature: str,
    scheme: str,
    school_age_min: int,
    school_age_max: int,
    missing_threshold: float,
) -> dict[str, Any]:
    del input_signature
    input_path = Path(input_path_str)
    if not input_path.exists():
        raise FileNotFoundError(f"File input tidak ditemukan: {input_path}")

    output_hash = hashlib.md5(
        f"{input_path.resolve()}|{build_file_signature(input_path)}|{scheme}|{school_age_min}|{school_age_max}|{missing_threshold}".encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    output_dir = OUTPUT_CACHE_DIR / f"{input_path.stem}_{scheme}_{output_hash}"

    expected = [output_dir / TABLE_SPECS[key]["filename"] for key in ("data_keluarga", "penjelasan_variabel")]
    if not all(path.exists() for path in expected):
        if scheme == "rekomendasi":
            iid_pipeline.run_pipeline_recommended(
                input_path=input_path,
                output_dir=output_dir,
                school_age_min=school_age_min,
                school_age_max=school_age_max,
                missing_threshold=missing_threshold,
            )
        else:
            iid_pipeline.run_pipeline(
                input_path=input_path,
                output_dir=output_dir,
                school_age_min=school_age_min,
                school_age_max=school_age_max,
                missing_threshold=missing_threshold,
            )

    bundle = load_output_bundle_cached(str(output_dir), build_folder_signature(output_dir))
    bundle["meta"]["source_label"] = "Olah dari file mentah"
    bundle["meta"]["scheme"] = scheme
    bundle["meta"]["input_path"] = str(input_path.resolve())
    return bundle


def resolve_default_request() -> dict[str, Any]:
    if "pca_request" in st.session_state:
        return dict(st.session_state.pca_request)
    if "dashboard_request" in st.session_state:
        request = dict(st.session_state.dashboard_request)
        if request.get("mode") == "folder_hasil":
            return request
        return {
            "mode": "olah_ulang",
            "input_path": request.get("input_path", str(detect_default_input_path() or BASE_DIR / "data_asli.parquet")),
            "scheme": request.get("scheme", "rekomendasi"),
            "school_age_min": request.get("school_age_min", iid_pipeline.SCHOOL_AGE_MIN),
            "school_age_max": request.get("school_age_max", iid_pipeline.SCHOOL_AGE_MAX),
            "missing_threshold": request.get("missing_threshold", iid_pipeline.MISSING_THRESHOLD),
        }
    return {"mode": "folder_hasil", "output_dir": str(detect_default_output_dir())}


def resolve_bundle_from_request(request: dict[str, Any]) -> dict[str, Any]:
    if request["mode"] == "folder_hasil":
        return load_output_bundle_cached(request["output_dir"], build_folder_signature(Path(request["output_dir"])))
    return process_input_bundle_cached(
        request["input_path"],
        build_file_signature(Path(request["input_path"])),
        request["scheme"],
        int(request["school_age_min"]),
        int(request["school_age_max"]),
        float(request["missing_threshold"]),
    )


def build_variable_label_map(variable_df: pd.DataFrame) -> dict[str, str]:
    label_map: dict[str, str] = {}
    if variable_df.empty:
        return label_map
    if {"nama_variabel", "label_konsep"}.issubset(variable_df.columns):
        subset = variable_df[["nama_variabel", "label_konsep"]].dropna()
        for row in subset.itertuples(index=False):
            label_map[str(row.nama_variabel)] = str(row.label_konsep)
    return label_map


def get_household_rows(keluarga_df: pd.DataFrame) -> pd.DataFrame:
    if keluarga_df.empty:
        return keluarga_df.copy()
    household_df = keluarga_df.copy()
    if "iid_rumah_tangga" in household_df.columns:
        household_df["iid_rumah_tangga"] = pd.to_numeric(household_df["iid_rumah_tangga"], errors="coerce")
        household_df = household_df.loc[household_df["iid_rumah_tangga"].notna()].copy()
    if "family_id" in household_df.columns:
        household_df = household_df.drop_duplicates(subset=["family_id"], keep="first")
    return household_df


def build_analysis_dataframe(
    household_df: pd.DataFrame,
    feature_prefix: str,
    label_map: dict[str, str],
) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    feature_cols = [column for column in household_df.columns if column.startswith(feature_prefix)]
    feature_df = household_df[feature_cols].apply(pd.to_numeric, errors="coerce")
    valid_cols: list[str] = []
    for column in feature_cols:
        if feature_df[column].notna().any() and feature_df[column].nunique(dropna=True) > 1:
            valid_cols.append(column)
    feature_df = feature_df[valid_cols].copy()

    labels = {
        column: label_map.get(column, INDICATOR_LABELS_DEFAULT.get(column, DIMENSION_LABELS_DEFAULT.get(column, column)))
        for column in valid_cols
    }
    return feature_df, valid_cols, labels


def components_for_threshold(explained_ratio: pd.Series, threshold: float = 0.8) -> int:
    cumulative = explained_ratio.cumsum()
    hits = cumulative[cumulative >= threshold]
    return int(hits.index[0].replace("PC", "")) if not hits.empty else int(len(explained_ratio))


@st.cache_data(show_spinner=False)
def compute_pca_results(
    feature_df: pd.DataFrame,
    feature_order: tuple[str, ...],
    labels_map: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    del feature_order
    labels = dict(labels_map)
    working_df = feature_df.copy()

    imputer = SimpleImputer(strategy="median")
    imputed_values = imputer.fit_transform(working_df)
    imputed_df = pd.DataFrame(imputed_values, columns=working_df.columns, index=working_df.index)

    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(imputed_df)

    pca = PCA()
    components = pca.fit_transform(scaled_values)

    pc_names = [f"PC{i}" for i in range(1, pca.n_components_ + 1)]
    explained_ratio = pd.Series(pca.explained_variance_ratio_, index=pc_names, name="explained_variance_ratio")
    explained_df = explained_ratio.reset_index().rename(columns={"index": "komponen"})
    explained_df["explained_variance_percent"] = explained_df["explained_variance_ratio"] * 100
    explained_df["cumulative_percent"] = explained_df["explained_variance_percent"].cumsum()

    loadings = pd.DataFrame(pca.components_.T, index=working_df.columns, columns=pc_names)
    loadings.index.name = "kode_variabel"
    loadings = loadings.reset_index()
    loadings["variabel"] = loadings["kode_variabel"].map(labels)

    missing_rate = working_df.isna().mean().reset_index()
    missing_rate.columns = ["kode_variabel", "missing_rate"]
    missing_rate["variabel"] = missing_rate["kode_variabel"].map(labels)

    scores_df = pd.DataFrame(components[:, : min(5, len(pc_names))], columns=pc_names[: min(5, len(pc_names))], index=working_df.index)

    return {
        "explained_df": explained_df,
        "loadings_df": loadings,
        "scores_df": scores_df,
        "imputed_df": imputed_df,
        "missing_df": missing_rate,
        "labels": labels,
    }


def build_influence_dataframe(pca_result: dict[str, Any], top_components: int) -> pd.DataFrame:
    explained_df = pca_result["explained_df"].copy()
    loadings_df = pca_result["loadings_df"].copy()
    component_names = explained_df["komponen"].head(top_components).tolist()
    weights = (
        explained_df.set_index("komponen").loc[component_names, "explained_variance_ratio"]
    )

    rows: list[dict[str, Any]] = []
    for row in loadings_df.itertuples(index=False):
        influence = 0.0
        for component_name in component_names:
            influence += (float(getattr(row, component_name)) ** 2) * float(weights[component_name])
        rows.append(
            {
                "kode_variabel": row.kode_variabel,
                "variabel": row.variabel,
                "pengaruh_tertimbang": influence,
            }
        )

    influence_df = pd.DataFrame(rows).sort_values("pengaruh_tertimbang", ascending=False)
    total = influence_df["pengaruh_tertimbang"].sum()
    influence_df["pengaruh_persen"] = (influence_df["pengaruh_tertimbang"] / total * 100) if total > 0 else 0.0
    influence_df["peringkat"] = range(1, len(influence_df) + 1)
    return influence_df


def build_scree_figure(explained_df: pd.DataFrame, chart_key: str) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        x=explained_df["komponen"],
        y=explained_df["explained_variance_percent"],
        name="Varian per komponen",
        marker_color="#0f766e",
    )
    fig.add_scatter(
        x=explained_df["komponen"],
        y=explained_df["cumulative_percent"],
        mode="lines+markers",
        name="Kumulatif",
        line=dict(color="#163249", width=3),
        marker=dict(size=8),
        yaxis="y2",
    )
    fig.update_layout(
        title=f"Scree plot {chart_key}",
        xaxis_title="Komponen utama",
        yaxis_title="Varian dijelaskan (%)",
        yaxis2=dict(title="Kumulatif (%)", overlaying="y", side="right", range=[0, 105]),
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def build_influence_bar_figure(influence_df: pd.DataFrame, chart_title: str) -> go.Figure:
    plot_df = influence_df.head(10).sort_values("pengaruh_persen")
    fig = px.bar(
        plot_df,
        x="pengaruh_persen",
        y="variabel",
        orientation="h",
        text_auto=".2f",
        color="pengaruh_persen",
        color_continuous_scale=["#d8f3eb", "#0f766e", "#163249"],
    )
    fig.update_layout(
        title=chart_title,
        xaxis_title="Pengaruh tertimbang (%)",
        yaxis_title="Variabel",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def build_loading_heatmap_figure(loadings_df: pd.DataFrame, top_components: int, chart_title: str) -> go.Figure:
    component_names = [f"PC{i}" for i in range(1, top_components + 1)]
    plot_df = loadings_df[["variabel", *component_names]].copy().set_index("variabel")
    fig = px.imshow(
        plot_df,
        labels=dict(x="Komponen utama", y="Variabel", color="Loading"),
        color_continuous_scale="RdBu_r",
        aspect="auto",
        zmin=-1,
        zmax=1,
    )
    fig.update_layout(title=chart_title, margin=dict(l=20, r=20, t=55, b=20))
    return fig


def build_pc_scatter_figure(scores_df: pd.DataFrame, household_df: pd.DataFrame, chart_title: str) -> go.Figure:
    plot_df = scores_df[["PC1", "PC2"]].copy()
    for column in ("deskel", "kategori_iid_rt", "iid_rumah_tangga"):
        if column in household_df.columns:
            plot_df[column] = household_df[column].values

    fig = px.scatter(
        plot_df.sample(min(8000, len(plot_df)), random_state=42) if len(plot_df) > 8000 else plot_df,
        x="PC1",
        y="PC2",
        color="kategori_iid_rt" if "kategori_iid_rt" in plot_df.columns else None,
        color_discrete_map=CATEGORY_COLORS,
        hover_name="deskel" if "deskel" in plot_df.columns else None,
        hover_data={"iid_rumah_tangga": ":.3f"} if "iid_rumah_tangga" in plot_df.columns else None,
        opacity=0.65,
    )
    fig.update_layout(
        title=chart_title,
        xaxis_title="PC1",
        yaxis_title="PC2",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def render_sidebar() -> dict[str, Any]:
    default_request = resolve_default_request()
    default_mode = "Folder hasil siap pakai" if default_request.get("mode") == "folder_hasil" else "Olah dari file mentah"
    default_input = detect_default_input_path() or BASE_DIR / "data_asli.parquet"

    st.sidebar.markdown("## Sumber data PCA")
    with st.sidebar.form("pca_loader_form"):
        source_mode = st.radio(
            "Mode sumber data",
            options=("Folder hasil siap pakai", "Olah dari file mentah"),
            index=0 if default_mode == "Folder hasil siap pakai" else 1,
        )

        if source_mode == "Folder hasil siap pakai":
            output_dir = st.text_input(
                "Folder output",
                value=default_request.get("output_dir", str(detect_default_output_dir())),
            )
            submit = st.form_submit_button("Muat analisis PCA")
            if submit:
                st.session_state.pca_request = {"mode": "folder_hasil", "output_dir": output_dir}
        else:
            uploaded_file = st.file_uploader("Upload file CSV/XLSX/Parquet", type=["csv", "xlsx", "xls", "parquet"])
            input_path = st.text_input(
                "Atau path file lokal",
                value=default_request.get("input_path", str(default_input)),
            )
            scheme = st.selectbox(
                "Skema perhitungan",
                options=["baseline", "rekomendasi"],
                index=1 if default_request.get("scheme", "rekomendasi") == "rekomendasi" else 0,
            )
            school_age_min = st.number_input(
                "Batas usia sekolah minimum",
                min_value=0,
                max_value=100,
                value=int(default_request.get("school_age_min", iid_pipeline.SCHOOL_AGE_MIN)),
                step=1,
            )
            school_age_max = st.number_input(
                "Batas usia sekolah maksimum",
                min_value=0,
                max_value=100,
                value=int(default_request.get("school_age_max", iid_pipeline.SCHOOL_AGE_MAX)),
                step=1,
            )
            missing_threshold = st.slider(
                "Ambang indikator inti hilang",
                min_value=0.0,
                max_value=1.0,
                value=float(default_request.get("missing_threshold", iid_pipeline.MISSING_THRESHOLD)),
                step=0.01,
            )
            submit = st.form_submit_button("Proses dan muat PCA")
            if submit:
                source_path = save_uploaded_file(uploaded_file) if uploaded_file is not None else Path(input_path)
                st.session_state.pca_request = {
                    "mode": "olah_ulang",
                    "input_path": str(source_path),
                    "scheme": scheme,
                    "school_age_min": int(school_age_min),
                    "school_age_max": int(school_age_max),
                    "missing_threshold": float(missing_threshold),
                }

    if "pca_request" not in st.session_state:
        st.session_state.pca_request = default_request

    st.sidebar.markdown(
        """
        <div class="note">
            PCA dihitung pada tingkat rumah tangga valid. Skor di-standardisasi dulu,
            lalu ranking pengaruh dihitung dari loading kuadrat yang dibobot oleh
            proporsi varian komponen utama terpilih.
        </div>
        """,
        unsafe_allow_html=True,
    )

    return dict(st.session_state.pca_request)


def render_hero(meta: dict[str, Any], household_count: int) -> None:
    badges = [
        f"Sumber: {meta.get('source_label', '-')}",
        f"RT valid: {format_number(household_count, 0)}",
        f"Folder output: {Path(meta.get('output_dir', '-')).name}",
    ]
    if meta.get("scheme"):
        badges.append(f"Skema: {meta['scheme']}")
    if meta.get("input_path"):
        badges.append(f"Input: {Path(meta['input_path']).name}")
    badge_html = "".join(f"<span class='badge'>{item}</span>" for item in badges)
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-kicker">Page Baru</div>
            <h1 class="hero-title">Analisis PCA untuk Indikator dan Dimensi</h1>
            <div class="hero-subtitle">
                Halaman ini membantu melihat indikator dan dimensi yang paling berpengaruh
                berdasarkan Principal Component Analysis. Analisis dilakukan pada rumah tangga
                valid menggunakan skor yang sudah di-standardisasi agar perbandingan antar
                variabel tetap adil.
            </div>
            <div class="badge-row">{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pca_section(
    section_name: str,
    feature_df: pd.DataFrame,
    household_df: pd.DataFrame,
    label_map: dict[str, str],
) -> None:
    if feature_df.empty or feature_df.shape[1] < 2:
        st.warning(f"Kolom {section_name.lower()} tidak cukup untuk menjalankan PCA.")
        return

    pca_result = compute_pca_results(
        feature_df=feature_df,
        feature_order=tuple(feature_df.columns),
        labels_map=tuple(label_map.items()),
    )
    explained_df = pca_result["explained_df"]
    suggested_components = components_for_threshold(explained_df.set_index("komponen")["explained_variance_ratio"], 0.8)
    max_components = len(explained_df)
    selected_components = st.slider(
        f"Jumlah komponen untuk ranking pengaruh {section_name.lower()}",
        min_value=2,
        max_value=max_components,
        value=min(max(2, suggested_components), max_components),
        step=1,
        key=f"{section_name}_top_components",
    )

    influence_df = build_influence_dataframe(pca_result, selected_components)
    coverage = explained_df["explained_variance_percent"].head(selected_components).sum()
    missing_mean = pca_result["missing_df"]["missing_rate"].mean()

    metric_cols = st.columns(4)
    metric_cols[0].metric("Jumlah variabel", format_number(feature_df.shape[1], 0))
    metric_cols[1].metric("RT valid dianalisis", format_number(len(feature_df), 0))
    metric_cols[2].metric(f"Varian dijelaskan PC1-PC{selected_components}", format_percent(coverage / 100))
    metric_cols[3].metric("Rata-rata missing sebelum imputasi", format_percent(missing_mean))

    top_feature = influence_df.iloc[0]
    st.markdown(
        f"<span class='pill'>Variabel paling berpengaruh: {top_feature['variabel']} ({top_feature['pengaruh_persen']:.2f}%)</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='note'>Ranking pengaruh di bawah memakai loading kuadrat yang dibobot oleh varian komponen utama terpilih, jadi nilainya mewakili kontribusi relatif variabel terhadap struktur utama data.</div>",
        unsafe_allow_html=True,
    )

    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(
        build_scree_figure(explained_df, section_name),
        use_container_width=True,
        key=f"{section_name}_scree",
    )
    chart_cols[1].plotly_chart(
        build_influence_bar_figure(influence_df, f"10 {section_name.lower()} paling berpengaruh"),
        use_container_width=True,
        key=f"{section_name}_influence_bar",
    )

    mid_cols = st.columns(2)
    mid_cols[0].plotly_chart(
        build_loading_heatmap_figure(pca_result["loadings_df"], selected_components, f"Heatmap loading {section_name.lower()}"),
        use_container_width=True,
        key=f"{section_name}_loading_heatmap",
    )
    mid_cols[1].plotly_chart(
        build_pc_scatter_figure(pca_result["scores_df"], household_df, f"Sebaran rumah tangga pada ruang PCA {section_name.lower()}"),
        use_container_width=True,
        key=f"{section_name}_pc_scatter",
    )

    table_tabs = st.tabs(["Ranking Pengaruh", "Loading PCA", "Explained Variance", "Missing Value"])
    with table_tabs[0]:
        st.dataframe(influence_df, use_container_width=True, hide_index=True)
    with table_tabs[1]:
        st.dataframe(pca_result["loadings_df"], use_container_width=True, hide_index=True)
    with table_tabs[2]:
        st.dataframe(explained_df, use_container_width=True, hide_index=True)
    with table_tabs[3]:
        st.dataframe(pca_result["missing_df"], use_container_width=True, hide_index=True)


def main() -> None:
    inject_styles()
    request = render_sidebar()

    try:
        with st.spinner("Memuat data PCA..."):
            bundle = resolve_bundle_from_request(request)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    tables = bundle["tables"]
    meta = bundle["meta"]
    household_df = get_household_rows(tables["data_keluarga"])
    variable_df = tables.get("penjelasan_variabel", pd.DataFrame())
    label_map = build_variable_label_map(variable_df)

    indicator_df, indicator_cols, indicator_labels = build_analysis_dataframe(household_df, "indikator_", label_map)
    dimension_df, dimension_cols, dimension_labels = build_analysis_dataframe(household_df, "dimensi_", label_map)

    render_hero(meta, len(household_df))

    st.markdown(
        "<div class='note'>Interpretasi cepat: variabel dengan pengaruh tertimbang lebih tinggi berarti lebih kuat menjelaskan pola variasi utama pada data. Ini bukan kausalitas, tetapi indikator yang paling dominan dalam struktur data.</div>",
        unsafe_allow_html=True,
    )

    overview_cols = st.columns(4)
    overview_cols[0].metric("Indikator dianalisis", format_number(len(indicator_cols), 0))
    overview_cols[1].metric("Dimensi dianalisis", format_number(len(dimension_cols), 0))
    overview_cols[2].metric("Rata-rata IID RT", format_number(pd.to_numeric(household_df["iid_rumah_tangga"], errors="coerce").mean()))
    overview_cols[3].metric("Kategori RT dominan", household_df["kategori_iid_rt"].astype("string").value_counts().index[0] if "kategori_iid_rt" in household_df.columns and not household_df.empty else "-")

    tab_indikator, tab_dimensi = st.tabs(["PCA Indikator", "PCA Dimensi"])

    with tab_indikator:
        render_pca_section(
            section_name="Indikator",
            feature_df=indicator_df,
            household_df=household_df,
            label_map=indicator_labels,
        )

    with tab_dimensi:
        render_pca_section(
            section_name="Dimensi",
            feature_df=dimension_df,
            household_df=household_df,
            label_map=dimension_labels,
        )


if __name__ == "__main__":
    main()
