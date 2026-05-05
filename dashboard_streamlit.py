from __future__ import annotations

import hashlib
import numbers
import re
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import id as iid_pipeline


BASE_DIR = Path(__file__).resolve().parent
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
        "label": "Household Data",
        "description": "Final member- and household-level output. Index scores are generally recorded on the household-head row.",
        "required": True,
    },
    "indeks_desa": {
        "filename": "indeks_desa.csv",
        "label": "Village Index",
        "description": "Summary of indicator scores, dimension scores, village digital inclusion, digital deprivation, and within-village inequality.",
        "required": True,
    },
    "penjelasan_variabel": {
        "filename": "penjelasan_variabel.csv",
        "label": "Variable Documentation",
        "description": "Variable dictionary covering source fields, scoring rules, and notes for each indicator or dimension.",
        "required": True,
    },
    "rumah_tangga_dikeluarkan": {
        "filename": "rumah_tangga_dikeluarkan.csv",
        "label": "Excluded Households",
        "description": "Households excluded from index calculation, including the reason for exclusion.",
        "required": False,
    },
    "sebaran_iid_rt_desa": {
        "filename": "sebaran_iid_rt_desa.csv",
        "label": "Household Index Distribution by Village",
        "description": "Distribution of household digital inclusion categories in each village.",
        "required": False,
    },
    "sebaran_warga_iid_rt": {
        "filename": "sebaran_warga_iid_rt.csv",
        "label": "Resident Distribution by Household Index",
        "description": "Distribution of residents by household digital inclusion category.",
        "required": False,
    },
    "ringkasan_pengolahan": {
        "filename": "ringkasan_pengolahan.csv",
        "label": "Processing Summary",
        "description": "Processing summary from the pipeline, including valid households and school-age parameters.",
        "required": False,
    },
    "ringkasan_ketimpangan": {
        "filename": "ringkasan_ketimpangan.csv",
        "label": "Inequality Summary",
        "description": "Overall and village-level Gini summary, including relative category and leading household contributor.",
        "required": False,
    },
    "kontributor_ketimpangan": {
        "filename": "kontributor_ketimpangan.csv",
        "label": "Inequality Contributors",
        "description": "Household contributors to inequality for the full study area and for individual villages.",
        "required": False,
    },
    "sebaran_gini_desa": {
        "filename": "sebaran_gini_desa.csv",
        "label": "Village Gini Distribution",
        "description": "Tertile-based relative classification of household-index Gini values across sampled villages.",
        "required": False,
    },
    "batas_kategori_iid_rt": {
        "filename": "batas_kategori_iid_rt.csv",
        "label": "Household Index Category Thresholds",
        "description": "Lower and upper bounds for household digital inclusion categories under the recommended scheme.",
        "required": False,
    },
    "perbandingan_skema": {
        "filename": "perbandingan_skema.csv",
        "label": "Scheme Comparison",
        "description": "Statistical and category-distribution comparison between the baseline and recommended schemes.",
        "required": False,
    },
    "skema_rekomendasi": {
        "filename": "skema_rekomendasi.csv",
        "label": "Recommended Scheme",
        "description": "Components, weights, and scoring rules used in the recommended scheme.",
        "required": False,
    },
    "analisis_determinasi_dimensi": {
        "filename": "analisis_determinasi_dimensi.csv",
        "label": "Dimension Determination",
        "description": "Coefficient of determination for each dimension against the village digital inclusion index on the natural-log scale.",
        "required": False,
    },
    "analisis_determinasi_variabel": {
        "filename": "analisis_determinasi_variabel.csv",
        "label": "Indicator Determination",
        "description": "Coefficient of determination for each indicator against its source dimension and the village digital inclusion index.",
        "required": False,
    },
    "analisis_sensitivitas_oat": {
        "filename": "analisis_sensitivitas_oat.csv",
        "label": "OAT Sensitivity",
        "description": "One-at-a-time simulation using a selected dimension increase on the 0-1 index scale to estimate changes in village inclusion and digital deprivation.",
        "required": False,
    },
    "analisis_shapley_variabel": {
        "filename": "analisis_shapley_variabel.csv",
        "label": "Indicator Shapley Contribution",
        "description": "Shapley R-squared contribution of each indicator in explaining its source dimension and the village digital inclusion index.",
        "required": False,
    },
}

CORE_TABLE_KEYS = ("data_keluarga", "indeks_desa", "penjelasan_variabel")

CATEGORY_ORDER = [*iid_pipeline.IID_RT_CATEGORY_ORDER, iid_pipeline.UNSCORED_IID_CATEGORY_LABEL]
VISIBLE_CATEGORY_ORDER = list(iid_pipeline.IID_RT_CATEGORY_ORDER)
CATEGORY_COLORS = {
    "sangat rendah": "#9f1239",
    "rendah": "#ea580c",
    "sedang": "#eab308",
    "tinggi": "#14b8a6",
    "sangat tinggi": "#2563eb",
    iid_pipeline.UNSCORED_IID_CATEGORY_LABEL: "#64748b",
}
IID_CATEGORY_LABELS = {
    "sangat rendah": "Very Low",
    "rendah": "Low",
    "sedang": "Moderate",
    "tinggi": "High",
    "sangat tinggi": "Very High",
    iid_pipeline.UNSCORED_IID_CATEGORY_LABEL: "Not Scored",
}
IID_CATEGORY_ORDER_EN = [IID_CATEGORY_LABELS[category] for category in VISIBLE_CATEGORY_ORDER]
IID_CATEGORY_COLORS = {
    IID_CATEGORY_LABELS[category]: color
    for category, color in CATEGORY_COLORS.items()
    if category in IID_CATEGORY_LABELS
}
RED_RANK_ORDER = ["Rank 1", "Rank 2", "Rank 3", "Other Values"]
RED_RANK_COLORS = {
    "Rank 1": "#7f1d1d",
    "Rank 2": "#b91c1c",
    "Rank 3": "#ef4444",
    "Other Values": "#fecaca",
}
RED_HEATMAP_SCALE = [
    [0.0, "#fff5f5"],
    [0.35, "#fecaca"],
    [0.6, "#f87171"],
    [0.8, "#dc2626"],
    [1.0, "#7f1d1d"],
]
GINI_LABELS = {
    "Rendah": "Low",
    "Sedang": "Moderate",
    "Tinggi": "High",
}
GINI_COLORS = {
    "Low": "#16a34a",
    "Moderate": "#eab308",
    "High": "#dc2626",
}
INEQUALITY_DIRECTION_LABELS = {
    "di bawah rata-rata": "Below Mean",
    "di atas rata-rata": "Above Mean",
    "sama dengan rata-rata": "At Mean",
}
INEQUALITY_DIRECTION_COLORS = {
    "Below Mean": "#b91c1c",
    "Above Mean": "#0f766e",
    "At Mean": "#64748b",
}
IKD_TERTILE_ORDER = ["T1", "T2", "T3"]
IKD_RELATIVE_ORDER = ["Low", "Moderate", "High"]
IKD_TERTILE_TO_RELATIVE = {
    "T1": "Low",
    "T2": "Moderate",
    "T3": "High",
}
IKD_TERTILE_LABELS = {
    "T1": "Tertile 1 - Lowest Relative Digital Deprivation",
    "T2": "Tertile 2 - Moderate Relative Digital Deprivation",
    "T3": "Tertile 3 - Highest Relative Digital Deprivation",
}
IKD_RELATIVE_RANGE_LABELS = {
    "Low": "Tertile 1",
    "Moderate": "Tertile 2",
    "High": "Tertile 3",
}
IKD_RELATIVE_COLORS = {
    "Low": "#16a34a",
    "Moderate": "#eab308",
    "High": "#dc2626",
}
DIMENSION_LABELS = {
    "dimensi_A": "Device Access",
    "dimensi_B": "Internet Connectivity",
    "dimensi_C": "Human Capacity",
    "dimensi_D": "Digital Use",
    "dimensi_E": "Social Enabling Environment",
}
JOURNAL_CATEGORY_LABELS = IID_CATEGORY_LABELS
JOURNAL_CATEGORY_ORDER = ["Very Low", "Low", "Moderate", "High", "Very High"]
JOURNAL_CATEGORY_COLORS = {
    JOURNAL_CATEGORY_LABELS[category]: CATEGORY_COLORS[category]
    for category in VISIBLE_CATEGORY_ORDER
    if category in JOURNAL_CATEGORY_LABELS
}
JOURNAL_GINI_LABELS = {
    **GINI_LABELS,
}
JOURNAL_DIMENSION_LABELS = {
    "dimensi_A": "Device Access",
    "dimensi_B": "Internet Connectivity",
    "dimensi_C": "Human Capacity",
    "dimensi_D": "Digital Use",
    "dimensi_E": "Social Enabling Environment",
}
JOURNAL_INDICATOR_LABELS = {
    "indikator_A": "Mobile Phone Ownership",
    "indikator_B": "Mobile Phone Sufficiency",
    "indikator_C": "Productive Digital Device Ownership",
    "indikator_D": "Household Internet Access",
    "indikator_E": "Household Head Educational Attainment",
    "indikator_F": "School Participation Ratio",
    "indikator_G": "Household Head Organizational Involvement",
    "indikator_H": "Household Member Organizational Involvement",
    "indikator_I": "Household Head Community Participation",
    "indikator_J": "Household Member Community Participation",
    "indikator_K": "Social Media Use",
    "indikator_L": "Information Media Access",
    "indikator_M": "Policy Information Participation",
}
JOURNAL_PROFILE_DOMAINS = {
    "Educational Characteristics": ("indikator_E",),
    "Device Ownership": ("dimensi_A",),
    "Internet Access": ("dimensi_B",),
    "Digital Use": ("dimensi_D",),
    "Social Participation": ("dimensi_E",),
}
JOURNAL_VILLAGE_PAGE_SIZE = 10

ANALYSIS_METRIC_LABELS = {
    "R2 IID Desa": "R-squared for Village Digital Inclusion Index",
    "R2 Dimensi": "R-squared for Dimension Score",
    "Shapley R2 Dimensi": "Shapley R-squared for Dimension Score",
    "Shapley R2 IID Desa": "Shapley R-squared for Village Digital Inclusion Index",
    "Proporsi Shapley Dimensi": "Shapley Share for Dimension Score",
    "Proporsi Shapley IID Desa": "Shapley Share for Village Digital Inclusion Index",
    "Proporsi Shapley IID": "Shapley Share for Digital Inclusion Index",
    "Rata-rata Kenaikan IID Desa (%)": "Mean Increase in Village Digital Inclusion Index (%)",
    "Rata-rata Penurunan Deprivasi Digital (%)": "Mean Reduction in Digital Deprivation (%)",
}

DISPLAY_COLUMN_LABELS = {
    "metrik": "Metric",
    "nilai": "Value",
    "indikator": "Indicator",
    "tipe_imputasi": "Imputation Type",
    "nilai_imputasi": "Imputed Value",
    "jumlah_diimputasi": "Imputed Records",
    "nama_variabel": "Variable Name",
    "level_output": "Output Level",
    "label_konsep": "Concept Label",
    "dimensi": "Dimension",
    "simbol_dimensi": "Dimension Symbol",
    "bobot_dimensi": "Dimension Weight",
    "sumber_nilai": "Source Field",
    "aturan_skoring": "Scoring Rule",
    "catatan": "Note",
    "tampil_pada_baris": "Displayed On",
    "kode_deskel": "Village Code",
    "deskel": "Village",
    "label_desa": "Village",
    "dusun": "Hamlet",
    "rw": "Neighborhood Unit",
    "lat": "Latitude",
    "lng": "Longitude",
    "long": "Longitude",
    "lon": "Longitude",
    "longitude": "Longitude",
    "jumlah_kk": "Households",
    "total_kk_desa": "Village Households",
    "jumlah_rt": "Households",
    "jumlah_warga": "Residents",
    "total_warga": "Total Residents",
    "persentase_kk": "Household Share",
    "persentase_rt": "Household Share",
    "persentase_warga": "Resident Share",
    "persentase_desa": "Village Share",
    "jumlah_desa": "Villages",
    "total_desa": "Total Villages",
    "kategori_iid_rt": "Household Digital Inclusion Category",
    "interpretasi_gini": "Relative Gini Category",
    "interpretasi_gini_cakupan": "Relative Gini Category",
    "rentang_gini": "Gini Range",
    "batas_bawah": "Lower Bound",
    "batas_atas": "Upper Bound",
    "iid_desa": "Village Digital Inclusion Index",
    "ikd_desa": "Village Digital Deprivation Score",
    "iid_rumah_tangga": "Household Digital Inclusion Index",
    "ikd_rt": "Household Digital Deprivation Score",
    "gini_iid_rumah_tangga": "Within-Village Gini",
    "rata_rata_iid_rumah_tangga": "Mean Household Digital Inclusion Index",
    "rata_rata_iid_cakupan": "Mean Index in Selected Scope",
    "cakupan_analisis": "Analysis Scope",
    "family_id": "Household ID",
    "label_kk": "Household Label",
    "nama_kk_subjek": "Household Head or Subject",
    "nama_kontributor_utama": "Leading Contributor Name",
    "family_id_kontributor_utama": "Leading Contributor Household ID",
    "iid_kontributor_utama": "Leading Contributor Index",
    "arah_kontributor_utama": "Leading Contributor Position",
    "porsi_kontributor_utama": "Leading Contributor Share",
    "jumlah_kontributor_non_nol": "Non-Zero Contributors",
    "usia": "Age",
    "suku": "Ethnic Group",
    "subjek": "Subject",
    "nama": "Name",
    "jml_keluarga": "Household Members",
    "jumlah_anggota_rumah_tangga": "Household Members",
    "porsi_kontribusi_gini": "Gini Contribution Share",
    "kontribusi_gini": "Gini Contribution",
    "arah_deviasi": "Position Against Mean",
    "deviasi_iid_cakupan": "Index Deviation from Scope Mean",
    "peringkat_kontribusi": "Contribution Rank",
    "ikd_tertil": "Digital Deprivation Tertile",
    "kategori_tertil": "Relative Digital Deprivation Class",
    "rentang_tertil": "Tertile Range",
    "urutan_desa": "Village Order",
    "kolom": "Column",
    "tipe_data": "Data Type",
    "terisi": "Filled Values",
    "kosong": "Missing Values",
    "persen_kosong": "Missing Share",
    "unik": "Unique Values",
    "contoh_nilai": "Sample Values",
    "statistik": "Statistic",
    "frekuensi": "Frequency",
    "atribut": "Attribute",
    "Dimensi": "Dimension",
    "Variabel": "Indicator",
    "Metrik": "Metric",
    "Metrik Tampilan": "Displayed Metric",
    "Persentase": "Percentage",
    "dimensi_A": "Dimension A - Device Access",
    "dimensi_B": "Dimension B - Internet Connectivity",
    "dimensi_C": "Dimension C - Human Capacity",
    "dimensi_D": "Dimension D - Digital Use",
    "dimensi_E": "Dimension E - Social Enabling Environment",
    "indikator_A": "Indicator A - Mobile Phone Ownership",
    "indikator_B": "Indicator B - Mobile Phone Sufficiency",
    "indikator_C": "Indicator C - Productive Digital Device Ownership",
    "indikator_D": "Indicator D - Household Internet Access",
    "indikator_E": "Indicator E - Household Head Educational Attainment",
    "indikator_F": "Indicator F - School Participation Ratio",
    "indikator_G": "Indicator G - Household Head Organizational Involvement",
    "indikator_H": "Indicator H - Household Member Organizational Involvement",
    "indikator_I": "Indicator I - Household Head Community Participation",
    "indikator_J": "Indicator J - Household Member Community Participation",
    "indikator_K": "Indicator K - Social Media Use",
    "indikator_L": "Indicator L - Information Media Access",
    "indikator_M": "Indicator M - Policy Information Participation",
}

EXACT_DISPLAY_VALUE_LABELS = {
    "jumlah_baris_data_keluarga": "Household Data Rows",
    "jumlah_baris_sumber": "Source Data Rows",
    "jumlah_rumah_tangga_tercatat": "Recorded Households",
    "jumlah_rumah_tangga_teridentifikasi": "Identified Households",
    "jumlah_rumah_tangga_dengan_kepala": "Households with an Identified Head",
    "jumlah_rumah_tangga_valid": "Valid Households",
    "jumlah_rumah_tangga_dikeluarkan": "Excluded Households",
    "jumlah_desa": "Villages",
    "jumlah_kk_agregat": "Aggregate Households",
    "rata_rata_iid_desa": "Mean Village Digital Inclusion Index",
    "batas_usia_sekolah_min": "Minimum School-Age Threshold",
    "batas_usia_sekolah_max": "Maximum School-Age Threshold",
    "cakupan_usia_partisipasi_sekolah": "School Participation Age Coverage",
    "indikator_hp_dimiliki": "Mobile Phone Ownership Indicator",
    "indikator_kecukupan_hp": "Mobile Phone Sufficiency Indicator",
    "indikator_perangkat_produktif": "Productive Digital Device Indicator",
    "indikator_akses_internet": "Internet Access Indicator",
    "indikator_pendidikan_kepala": "Household Head Education Indicator",
    "indikator_organisasi_kepala": "Household Head Organization Indicator",
    "indikator_organisasi_anggota": "Household Member Organization Indicator",
    "indikator_partisipasi_masyarakat_kepala": "Household Head Community Participation Indicator",
    "indikator_partisipasi_masyarakat_anggota": "Household Member Community Participation Indicator",
    "indikator_medsos": "Social Media Indicator",
    "indikator_media_informasi": "Information Media Indicator",
    "indikator_partisipasi_kebijakan": "Policy Information Participation Indicator",
    "modus": "Mode",
    "keluarga": "Household",
    "desa": "Village",
    "keluarga, desa": "Household and Village",
    "keseluruhan": "Overall Study Area",
    "Semua desa": "All Villages",
    "folder_hasil": "Prepared Output Folder",
    "olah_ulang": "Reprocessed Source Data",
    "Folder hasil siap pakai": "Prepared Output Folder",
    "Olah dari file mentah": "Processed from Source Data",
    "rekomendasi": "Recommended",
    "baseline": "Baseline",
    "Kepemilikan HP rumah tangga": "Household Mobile Phone Ownership",
    "Kecukupan HP": "Mobile Phone Sufficiency",
    "Kepemilikan perangkat digital produktif": "Productive Digital Device Ownership",
    "Akses internet rumah tangga": "Household Internet Access",
    "Pendidikan terakhir kepala keluarga": "Household Head Educational Attainment",
    "Rasio partisipasi sekolah": "School Participation Ratio",
    "Keterlibatan organisasi kepala keluarga": "Household Head Organizational Involvement",
    "Keterlibatan organisasi anggota keluarga": "Household Member Organizational Involvement",
    "Partisipasi kepala keluarga pada kegiatan masyarakat": "Household Head Community Participation",
    "Partisipasi anggota keluarga pada kegiatan masyarakat": "Household Member Community Participation",
    "Penggunaan media sosial": "Social Media Use",
    "Akses media informasi": "Information Media Access",
    "Partisipasi informasi/kebijakan": "Policy Information Participation",
    "Indeks Inklusi Digital rumah tangga": "Household Digital Inclusion Index",
    "Indeks Inklusi Digital desa": "Village Digital Inclusion Index",
    "Indeks deprivasi/kesenjangan digital desa": "Village Digital Deprivation Score",
    "Gini IID rumah tangga": "Within-Village Gini of Household Scores",
    "Akses perangkat": "Device Access",
    "Konektivitas internet": "Internet Connectivity",
    "Kapasitas manusia": "Human Capacity",
    "Penggunaan digital": "Digital Use",
    "Lingkungan pendukung sosial": "Social Enabling Environment",
    "gabungan seluruh dimensi": "Composite of All Dimensions",
    "gabungan dimensi_A sampai dimensi_E": "Composite of Dimension A through Dimension E",
    "kepala keluarga saja": "Household head row only",
    "kepala keluarga saja dalam data_keluarga": "Household head row only in household data",
    "anggota usia 7-25 tahun saja": "Members aged 7-25 only",
    "Tidak punya ijazah": "No Diploma",
    "kepala keluarga": "Household Head",
}

DISPLAY_TEXT_REPLACEMENTS = (
    ("SD 7-12 tahun, SMP 13-15 tahun, SMA/SMK 16-18 tahun, Perguruan Tinggi 19-25 tahun", "Primary school 7-12 years, junior secondary 13-15 years, senior secondary or vocational 16-18 years, higher education 19-25 years"),
    ("tidak memiliki", "does not have"),
    ("memiliki minimal satu", "has at least one"),
    ("tidak ada akses", "no access"),
    ("akses publik/gratis/terbatas", "public, free, or limited access"),
    ("paket data seluler/provider HP", "mobile data or cellular provider"),
    ("Wi-Fi/langganan internet rumah tangga", "household Wi-Fi or internet subscription"),
    ("tidak berpartisipasi", "does not participate"),
    ("satu kegiatan/terbatas", "one or limited activity"),
    ("lebih dari satu kegiatan/aktif", "more than one activity or active participation"),
    ("tidak menggunakan", "does not use"),
    ("penggunaan terbatas", "limited use"),
    ("aktif menggunakan media sosial", "active social media use"),
    ("tidak mengakses media informasi", "does not access information media"),
    ("hanya media non-digital", "non-digital media only"),
    ("mengakses media digital/online", "accesses digital or online media"),
    ("tidak pernah terlibat", "never involved"),
    ("pernah/terbatas/satu orang", "ever involved, limited involvement, or one person"),
    ("aktif atau lebih dari satu orang", "active involvement or more than one person"),
    ("rerata", "mean of"),
    ("diabaikan dari penyebut jika NA", "excluded from the denominator when missing"),
    ("jika tidak ada anggota pada rentang usia tersebut maka NA", "returns missing when no member falls in the age range"),
    ("jumlah anggota usia 7-25 tahun yang sedang sekolah / jumlah anggota usia 7-25 tahun", "members aged 7-25 who are currently attending school divided by all members aged 7-25"),
)

MISSING_TEXT_VALUES = {"", "nan", "none", "<na>", "null"}
NAME_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
VILLAGE_DISPLAY_NAME_COLUMNS = {
    "deskel",
    "deskel_cakupan",
    "label_desa",
    "Village",
    "Lowest Village",
    "Highest Village",
}
PERSON_DISPLAY_NAME_COLUMNS = {
    "nama",
    "nama_kk_subjek",
    "label_kk",
    "nama_kontributor_utama",
    "Name",
    "Household Label",
    "Household Head or Subject",
    "Leading Contributor Name",
}
DISPLAY_NAME_COLUMNS = VILLAGE_DISPLAY_NAME_COLUMNS | PERSON_DISPLAY_NAME_COLUMNS


st.set_page_config(
    page_title="Digital Inclusion Dashboard",
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
            --card: rgba(255, 255, 255, 0.88);
            --card-strong: rgba(255, 255, 255, 0.96);
            --border: rgba(15, 23, 42, 0.08);
            --shadow: 0 24px 50px rgba(15, 23, 42, 0.08);
            --text-main: #163249;
            --text-soft: #5b7083;
            --accent: #0f766e;
            --accent-soft: #d8f3eb;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 32%),
                radial-gradient(circle at top right, rgba(37, 99, 235, 0.10), transparent 30%),
                linear-gradient(180deg, var(--bg-start) 0%, var(--bg-end) 100%);
        }
        .main .block-container {
            max-width: 1400px;
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        header[data-testid="stHeader"],
        #MainMenu,
        footer {
            visibility: hidden;
        }
        section[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, #f8fbfb 0%, #eef7f5 52%, #e8f1f6 100%);
            border-right: 1px solid rgba(15, 118, 110, 0.14);
            box-shadow: 10px 0 28px rgba(15, 23, 42, 0.06);
        }
        section[data-testid="stSidebar"] > div {
            padding-top: 1.25rem;
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] small {
            color: #315066 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: #123247 !important;
            letter-spacing: 0;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"] > div,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] .stSlider {
            background: rgba(255, 255, 255, 0.96) !important;
            border-radius: 10px !important;
            border: 1px solid rgba(15, 118, 110, 0.16) !important;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
        }
        section[data-testid="stSidebar"] input {
            color: #123247 !important;
        }
        section[data-testid="stSidebar"] [role="radiogroup"] {
            background: rgba(255, 255, 255, 0.70);
            border: 1px solid rgba(15, 118, 110, 0.12);
            border-radius: 12px;
            padding: 0.45rem 0.55rem;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(15, 118, 110, 0.14);
            border-radius: 12px;
            padding: 0.55rem;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
            background: #ffffff !important;
            border: 1px dashed rgba(15, 118, 110, 0.34) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] small {
            display: none !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
            border-radius: 10px !important;
            border: 0 !important;
            background: linear-gradient(135deg, #0f766e 0%, #2563eb 100%) !important;
            color: #ffffff !important;
            font-weight: 800 !important;
            box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
            width: 100%;
            min-height: 2.75rem;
            margin-top: 0.35rem;
        }
        section[data-testid="stSidebar"] details {
            background: rgba(255, 255, 255, 0.62);
            border: 1px solid rgba(15, 118, 110, 0.12);
            border-radius: 12px;
            padding: 0.25rem 0.55rem;
        }
        .sidebar-brand {
            background:
                linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(37, 99, 235, 0.10));
            border: 1px solid rgba(15, 118, 110, 0.16);
            border-radius: 14px;
            padding: 0.85rem 0.9rem;
            margin: 0.35rem 0 0.95rem 0;
        }
        .sidebar-kicker {
            color: #0f766e;
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        .sidebar-title {
            color: #123247;
            font-size: 1.15rem;
            line-height: 1.22;
            font-weight: 850;
            margin: 0;
        }
        .sidebar-subtitle {
            color: #526b7d;
            font-size: 0.86rem;
            line-height: 1.45;
            margin-top: 0.4rem;
        }
        .sidebar-section-label {
            color: #0f766e;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            margin: 1rem 0 0.25rem 0;
        }
        .sidebar-help {
            background: rgba(15, 118, 110, 0.08);
            border-left: 3px solid #0f766e;
            border-radius: 10px;
            color: #315066;
            font-size: 0.85rem;
            line-height: 1.48;
            margin-top: 0.9rem;
            padding: 0.65rem 0.75rem;
        }
        .sidebar-status {
            background: rgba(255, 255, 255, 0.70);
            border: 1px solid rgba(37, 99, 235, 0.12);
            border-radius: 12px;
            color: #315066;
            font-size: 0.84rem;
            line-height: 1.45;
            margin-top: 0.8rem;
            padding: 0.65rem 0.75rem;
        }
        .hero-shell {
            padding: 1.6rem 1.7rem;
            border-radius: 26px;
            background:
                linear-gradient(135deg, rgba(15, 118, 110, 0.94) 0%, rgba(21, 128, 61, 0.86) 38%, rgba(22, 50, 73, 0.92) 100%);
            color: white;
            box-shadow: 0 28px 55px rgba(15, 23, 42, 0.16);
            border: 1px solid rgba(255, 255, 255, 0.18);
            overflow: hidden;
            position: relative;
        }
        .hero-shell::after {
            content: "";
            position: absolute;
            inset: auto -10% -35% auto;
            width: 280px;
            height: 280px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.10);
            filter: blur(10px);
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
            font-size: 2.15rem;
            line-height: 1.05;
            font-weight: 800;
            margin: 0;
        }
        .hero-subtitle {
            margin-top: 0.65rem;
            max-width: 920px;
            font-size: 1.02rem;
            line-height: 1.55;
            color: rgba(248, 250, 252, 0.92);
        }
        .hero-badges {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        .hero-badge {
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
        .section-card {
            background: var(--card-strong);
            border: 1px solid var(--border);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 0.35rem 0.8rem 0.9rem 0.8rem;
        }
        .section-note {
            color: var(--text-soft);
            font-size: 0.95rem;
            line-height: 1.55;
            margin-top: 0.1rem;
            margin-bottom: 0.9rem;
        }
        .pill-note {
            display: inline-block;
            padding: 0.28rem 0.65rem;
            background: var(--accent-soft);
            color: var(--accent);
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
        .small-muted {
            color: var(--text-soft);
            font-size: 0.9rem;
        }
        .journal-overview-table-wrap {
            background: rgba(255, 255, 255, 0.84);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            box-shadow: 0 18px 34px rgba(15, 23, 42, 0.08);
            margin: 0.25rem 0 1.25rem 0;
            overflow: hidden;
        }
        .journal-overview-table {
            border-collapse: collapse;
            width: 100%;
        }
        .journal-overview-table thead th {
            background: #163249;
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0;
            padding: 0.78rem 1rem;
            text-align: left;
            text-transform: uppercase;
        }
        .journal-overview-table tbody td {
            border-bottom: 1px solid rgba(15, 23, 42, 0.07);
            color: #315066;
            font-size: 0.94rem;
            padding: 0.86rem 1rem;
            vertical-align: middle;
        }
        .journal-overview-table tbody tr:last-child td {
            border-bottom: 0;
        }
        .journal-overview-table tbody tr:nth-child(even) {
            background: rgba(15, 118, 110, 0.045);
        }
        .journal-overview-metric {
            color: #163249;
            font-weight: 800;
            min-width: 14rem;
        }
        .journal-overview-value {
            color: #0f766e !important;
            font-size: 1.32rem !important;
            font-weight: 850;
            white-space: nowrap;
        }
        .journal-overview-note {
            color: var(--text-soft) !important;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def detect_default_output_dir() -> Path:
    candidates = (
        BASE_DIR / "hasil_indeks_digital",
        BASE_DIR / "hasil_indeks_digital_uji2",
        BASE_DIR / "hasil_indeks_digital_skema_rekomendasi_codex",
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
    if isinstance(value, numbers.Integral):
        return f"{int(value):,}"
    if isinstance(value, numbers.Real):
        return f"{float(value):,.{digits}f}"
    return str(value)


def format_percent(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def format_currency(value: Any, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"IDR {float(value):,.{digits}f}"


def format_analysis_metric_label(metric_name: str) -> str:
    return ANALYSIS_METRIC_LABELS.get(metric_name, metric_name.replace("R2", "R-squared"))


def with_analysis_metric_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.rename(columns={column: format_analysis_metric_label(column) for column in df.columns})
    return prepare_display_dataframe(display_df)


def format_iid_category_label(value: Any) -> Any:
    if value is None or pd.isna(value):
        return value
    text = str(value).strip()
    return IID_CATEGORY_LABELS.get(text, text)


def format_gini_label(value: Any) -> Any:
    if value is None or pd.isna(value):
        return value
    text = str(value).strip()
    return GINI_LABELS.get(text, text)


def format_inequality_direction_label(value: Any) -> Any:
    if value is None or pd.isna(value):
        return value
    text = str(value).strip()
    return INEQUALITY_DIRECTION_LABELS.get(text, text)


def _is_missing_display_value(value: Any) -> bool:
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    if not isinstance(value, str):
        return False
    return value.strip().lower() in MISSING_TEXT_VALUES


def _format_name_word(match: re.Match[str]) -> str:
    word = match.group(0)
    if word.isupper() and len(word) <= 3:
        return word
    return word[:1].upper() + word[1:].lower()


def format_title_case_display_name(value: Any) -> Any:
    if _is_missing_display_value(value):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    return NAME_WORD_PATTERN.sub(_format_name_word, text)


def format_person_display_name(value: Any) -> Any:
    formatted_value = format_title_case_display_name(value)
    if not isinstance(formatted_value, str):
        return formatted_value
    if " | " not in formatted_value:
        return formatted_value
    name_part, id_part = str(value).strip().split(" | ", 1)
    formatted_name = format_title_case_display_name(name_part)
    return f"{formatted_name} | {id_part.strip()}"


def format_display_name_value(value: Any, column_name: str | None = None) -> Any:
    if column_name in PERSON_DISPLAY_NAME_COLUMNS:
        return format_person_display_name(value)
    if column_name in VILLAGE_DISPLAY_NAME_COLUMNS:
        return format_title_case_display_name(value)
    return value


def apply_display_name_casing(df: pd.DataFrame) -> pd.DataFrame:
    cased_df = df.copy()
    for column in DISPLAY_NAME_COLUMNS.intersection(cased_df.columns):
        cased_df[column] = cased_df[column].map(lambda value, col=column: format_display_name_value(value, col))
    return cased_df


def translate_display_text(value: Any, column_name: str | None = None) -> Any:
    if value is None or pd.isna(value):
        return value
    if not isinstance(value, str):
        return value

    text = value.strip()
    if column_name in DISPLAY_NAME_COLUMNS:
        return format_display_name_value(text, column_name)
    if column_name in {"kategori_iid_rt", "Digital Inclusion Category"}:
        return format_iid_category_label(text)
    if column_name in {"interpretasi_gini", "interpretasi_gini_cakupan"}:
        return format_gini_label(text)
    if column_name in {"arah_deviasi", "arah_kontributor_utama"}:
        return format_inequality_direction_label(text)
    if text in EXACT_DISPLAY_VALUE_LABELS:
        return EXACT_DISPLAY_VALUE_LABELS[text]
    if text in DISPLAY_COLUMN_LABELS:
        return DISPLAY_COLUMN_LABELS[text]
    if text in DIMENSION_LABELS:
        return DIMENSION_LABELS[text]
    if text in JOURNAL_INDICATOR_LABELS:
        return JOURNAL_INDICATOR_LABELS[text]
    if text in ANALYSIS_METRIC_LABELS:
        return ANALYSIS_METRIC_LABELS[text]

    translated_text = text
    for source_text, replacement_text in DISPLAY_TEXT_REPLACEMENTS:
        translated_text = translated_text.replace(source_text, replacement_text)
    return translated_text


def format_display_cell(value: Any) -> str:
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def prepare_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    for column in display_df.columns:
        if (
            column in DISPLAY_COLUMN_LABELS
            or column in {"kategori_iid_rt", "interpretasi_gini", "interpretasi_gini_cakupan", "arah_deviasi", "arah_kontributor_utama"}
            or pd.api.types.is_object_dtype(display_df[column])
            or pd.api.types.is_string_dtype(display_df[column])
            or isinstance(display_df[column].dtype, pd.CategoricalDtype)
        ):
            display_df[column] = display_df[column].map(lambda value, col=column: translate_display_text(value, col))
    display_df = display_df.rename(columns={column: DISPLAY_COLUMN_LABELS.get(column, column) for column in display_df.columns})
    for column in display_df.columns:
        if (
            pd.api.types.is_object_dtype(display_df[column])
            or pd.api.types.is_string_dtype(display_df[column])
            or isinstance(display_df[column].dtype, pd.CategoricalDtype)
        ):
            display_df[column] = display_df[column].map(format_display_cell)
    return display_df


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
    workbook_path = output_dir / "hasil_olahdata.xlsx"
    if workbook_path.exists():
        stats = workbook_path.stat()
        parts.append(f"{workbook_path.name}|{stats.st_size}|{stats.st_mtime_ns}")
    if not parts:
        return "empty"
    raw = "|".join(sorted(parts))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def save_uploaded_file(uploaded_file: Any) -> Path:
    content = uploaded_file.getvalue()
    digest = hashlib.md5(content).hexdigest()[:12]
    safe_name = uploaded_file.name.replace(" ", "_")
    target_path = UPLOAD_DIR / f"{digest}_{safe_name}"
    if not target_path.exists():
        target_path.write_bytes(content)
    return target_path


def derive_processing_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    keluarga_df = tables.get("data_keluarga", pd.DataFrame())
    desa_df = tables.get("indeks_desa", pd.DataFrame())
    excluded_df = tables.get("rumah_tangga_dikeluarkan", pd.DataFrame())
    rows: list[dict[str, Any]] = []

    if not keluarga_df.empty:
        rows.append({"metrik": "jumlah_baris_data_keluarga", "nilai": int(len(keluarga_df))})
        if "family_id" in keluarga_df.columns:
            rows.append(
                {
                    "metrik": "jumlah_rumah_tangga_tercatat",
                    "nilai": int(keluarga_df["family_id"].astype("string").nunique(dropna=True)),
                }
            )
        if "iid_rumah_tangga" in keluarga_df.columns and "family_id" in keluarga_df.columns:
            valid_households = keluarga_df.loc[keluarga_df["iid_rumah_tangga"].notna(), "family_id"]
            rows.append({"metrik": "jumlah_rumah_tangga_valid", "nilai": int(valid_households.nunique(dropna=True))})

    if not excluded_df.empty and "family_id" in excluded_df.columns:
        rows.append(
            {
                "metrik": "jumlah_rumah_tangga_dikeluarkan",
                "nilai": int(excluded_df["family_id"].astype("string").nunique(dropna=True)),
            }
        )

    if not desa_df.empty:
        rows.append({"metrik": "jumlah_desa", "nilai": int(len(desa_df))})
        if "jumlah_kk" in desa_df.columns:
            rows.append({"metrik": "jumlah_kk_agregat", "nilai": int(pd.to_numeric(desa_df["jumlah_kk"], errors="coerce").sum())})
        if "iid_desa" in desa_df.columns:
            rows.append({"metrik": "rata_rata_iid_desa", "nilai": float(pd.to_numeric(desa_df["iid_desa"], errors="coerce").mean())})

    if not rows:
        return pd.DataFrame(columns=["metrik", "nilai"])
    return pd.DataFrame(rows)


def normalize_desa_gini_table(desa_df: pd.DataFrame) -> pd.DataFrame:
    if desa_df.empty or "gini_iid_rumah_tangga" not in desa_df.columns:
        return desa_df.copy()
    normalized_df, _ = iid_pipeline.apply_relative_gini_classification(desa_df.copy())
    return normalized_df


def normalize_gini_distribution_table(
    distribution_df: pd.DataFrame,
    desa_df: pd.DataFrame,
) -> pd.DataFrame:
    if not distribution_df.empty and {"interpretasi_gini", "rentang_gini", "jumlah_desa"}.issubset(distribution_df.columns):
        normalized_df = distribution_df.copy()
        for column in ("jumlah_desa", "persentase_desa", "total_desa", "batas_bawah", "batas_atas"):
            if column in normalized_df.columns:
                normalized_df[column] = pd.to_numeric(normalized_df[column], errors="coerce")
        return normalized_df
    _, derived_df = iid_pipeline.apply_relative_gini_classification(desa_df.copy())
    return derived_df


def normalize_variable_explanation_table(variable_df: pd.DataFrame) -> pd.DataFrame:
    if variable_df.empty or "nama_variabel" not in variable_df.columns or "aturan_skoring" not in variable_df.columns:
        return variable_df.copy()
    normalized_df = variable_df.copy()
    mask = normalized_df["nama_variabel"].astype("string").eq("interpretasi_gini")
    normalized_df.loc[mask, "aturan_skoring"] = iid_pipeline.GINI_INTERPRETATION_RULE_TEXT
    return normalized_df


def ensure_advanced_analysis_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    analysis_keys = (
        "analisis_determinasi_dimensi",
        "analisis_determinasi_variabel",
        "analisis_sensitivitas_oat",
        "analisis_shapley_variabel",
    )
    if all(key in tables and not tables[key].empty for key in analysis_keys):
        return tables

    desa_df = tables.get("indeks_desa", pd.DataFrame())
    variable_df = tables.get("penjelasan_variabel", pd.DataFrame())
    derived_tables = iid_pipeline.build_advanced_analysis_tables(desa_df, variable_df)
    enriched_tables = tables.copy()
    for key in analysis_keys:
        if key not in enriched_tables or enriched_tables[key].empty:
            enriched_tables[key] = derived_tables.get(key, pd.DataFrame())
    return enriched_tables


@st.cache_data(show_spinner=False)
def load_output_bundle_cached(output_dir_str: str, folder_signature: str) -> dict[str, Any]:
    del folder_signature
    output_dir = Path(output_dir_str)
    if not output_dir.exists():
        raise FileNotFoundError(f"Output folder was not found: {output_dir}")

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
            missing_required.append(f"{spec['filename']} or {parquet_path.name}")

    if missing_required:
        joined = ", ".join(missing_required)
        raise FileNotFoundError(f"Required output files are incomplete in the selected folder: {joined}")

    if "ringkasan_pengolahan" not in tables:
        tables["ringkasan_pengolahan"] = derive_processing_summary(tables)
    if "indeks_desa" in tables:
        tables["indeks_desa"] = normalize_desa_gini_table(tables["indeks_desa"])
        tables["sebaran_gini_desa"] = normalize_gini_distribution_table(
            tables.get("sebaran_gini_desa", pd.DataFrame()),
            tables["indeks_desa"],
        )
    if "penjelasan_variabel" in tables:
        tables["penjelasan_variabel"] = normalize_variable_explanation_table(tables["penjelasan_variabel"])
    tables = ensure_advanced_analysis_tables(tables)
    tables = {key: apply_display_name_casing(df) for key, df in tables.items()}

    workbook_path = output_dir / "hasil_olahdata.xlsx"
    meta = {
        "output_dir": str(output_dir.resolve()),
        "workbook_path": str(workbook_path.resolve()) if workbook_path.exists() else None,
        "available_tables": [key for key in TABLE_SPECS if key in tables],
    }
    return {"tables": tables, "meta": meta}


def load_output_bundle(output_dir: Path) -> dict[str, Any]:
    signature = build_folder_signature(output_dir)
    bundle = load_output_bundle_cached(str(output_dir), signature)
    bundle["meta"]["source_mode"] = "folder_hasil"
    bundle["meta"]["source_label"] = "Prepared Output Folder"
    return bundle


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
        raise FileNotFoundError(f"Input file was not found: {input_path}")

    output_hash = hashlib.md5(
        f"{input_path.resolve()}|{build_file_signature(input_path)}|{scheme}|{school_age_min}|{school_age_max}|{missing_threshold}".encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    output_dir = OUTPUT_CACHE_DIR / f"{input_path.stem}_{scheme}_{output_hash}"

    expected_paths = [output_dir / TABLE_SPECS[key]["filename"] for key in CORE_TABLE_KEYS]
    if not all(path.exists() for path in expected_paths):
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
    bundle["meta"]["source_mode"] = "olah_ulang"
    bundle["meta"]["source_label"] = "Processed from Source Data"
    bundle["meta"]["scheme"] = scheme
    bundle["meta"]["input_path"] = str(input_path.resolve())
    bundle["meta"]["school_age_min"] = school_age_min
    bundle["meta"]["school_age_max"] = school_age_max
    bundle["meta"]["missing_threshold"] = missing_threshold
    return bundle


def process_input_bundle(
    input_path: Path,
    scheme: str,
    school_age_min: int,
    school_age_max: int,
    missing_threshold: float,
) -> dict[str, Any]:
    signature = build_file_signature(input_path)
    return process_input_bundle_cached(
        str(input_path),
        signature,
        scheme,
        school_age_min,
        school_age_max,
        missing_threshold,
    )


def ensure_request_state() -> None:
    if "dashboard_request" not in st.session_state:
        st.session_state.dashboard_request = {
            "mode": "folder_hasil",
            "output_dir": str(detect_default_output_dir()),
        }


@st.cache_data(show_spinner=False)
def load_household_detail_cached(
    input_path_str: str,
    input_signature: str,
    school_age_min: int,
    school_age_max: int,
    missing_threshold: float,
) -> pd.DataFrame:
    del input_signature
    input_path = Path(input_path_str)
    person_df = iid_pipeline.load_source_data(input_path)
    valid_df, _, _ = iid_pipeline.build_household_index(
        person_df,
        school_age_min=school_age_min,
        school_age_max=school_age_max,
        missing_threshold=missing_threshold,
    )
    keep_columns = [
        "family_id",
        "kode_deskel",
        "deskel",
        "dusun",
        "rw",
        "lat",
        "lng",
        "subjek",
        "nama",
        "usia",
        "suku",
        "jml_keluarga",
        "jumlah_anggota_rumah_tangga",
        "hp_punya",
        "hp_jumlah",
        "hp_jumlah_num",
        "hp_jumlah_terstandar",
        "elektronik_rumah",
        "jumlah_perangkat_produktif_rumah_tangga",
        "wifi",
        "hp_provider",
        "wifi_teragregasi",
        "hp_provider_teragregasi",
        "rp_komunikasi_tertinggi",
        "ijazah",
        "partisipasi_sekolah",
        "jumlah_anggota_usia_sekolah",
        "jumlah_status_sekolah_terisi",
        "jumlah_anggota_sedang_sekolah",
        "par_organisasi",
        "organisasi_nama",
        "par_masyarakat",
        "medsos",
        "media_informasi",
        "par_kebijakan",
        "jumlah_organisasi_kepala",
        "jumlah_organisasi_anggota",
        "jumlah_partisipasi_masyarakat_kepala",
        "jumlah_partisipasi_masyarakat_anggota",
        "jumlah_partisipasi_kebijakan",
        "iid_rt",
        "ikd_rt",
    ]
    existing_columns = [column for column in keep_columns if column in valid_df.columns]
    detail_df = valid_df[existing_columns].copy()
    for column in (
        "jml_keluarga",
        "jumlah_anggota_rumah_tangga",
        "hp_jumlah",
        "hp_jumlah_num",
        "hp_jumlah_terstandar",
        "jumlah_perangkat_produktif_rumah_tangga",
        "rp_komunikasi_tertinggi",
        "jumlah_anggota_usia_sekolah",
        "jumlah_status_sekolah_terisi",
        "jumlah_anggota_sedang_sekolah",
        "jumlah_organisasi_kepala",
        "jumlah_organisasi_anggota",
        "jumlah_partisipasi_masyarakat_kepala",
        "jumlah_partisipasi_masyarakat_anggota",
        "jumlah_partisipasi_kebijakan",
        "iid_rt",
        "ikd_rt",
        "lat",
        "lng",
        "usia",
    ):
        if column in detail_df.columns:
            detail_df[column] = pd.to_numeric(detail_df[column], errors="coerce")
    return apply_display_name_casing(detail_df)


def resolve_household_detail_df(meta: dict[str, Any], tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    input_path_value = meta.get("input_path")
    input_path = Path(input_path_value) if input_path_value else detect_default_input_path()
    if input_path is None or not input_path.exists():
        return pd.DataFrame()

    school_age_min = int(meta.get("school_age_min", iid_pipeline.SCHOOL_AGE_MIN))
    school_age_max = int(meta.get("school_age_max", iid_pipeline.SCHOOL_AGE_MAX))
    missing_threshold = float(meta.get("missing_threshold", iid_pipeline.MISSING_THRESHOLD))

    detail_df = load_household_detail_cached(
        str(input_path),
        build_file_signature(input_path),
        school_age_min,
        school_age_max,
        missing_threshold,
    )
    if detail_df.empty:
        return detail_df

    household_df = get_household_rows(tables.get("data_keluarga", pd.DataFrame()))
    if not household_df.empty and {"family_id", "kategori_iid_rt"}.issubset(household_df.columns):
        category_df = household_df[["family_id", "kategori_iid_rt"]].drop_duplicates(subset=["family_id"])
        detail_df = detail_df.merge(category_df, on="family_id", how="left")
    else:
        detail_df["kategori_iid_rt"] = detail_df["iid_rt"].apply(iid_pipeline.classify_iid_rt)

    return detail_df


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


def build_household_profile_lookup(household_df: pd.DataFrame, detail_df: pd.DataFrame) -> pd.DataFrame:
    profile_df = household_df.copy()
    if profile_df.empty:
        return profile_df

    if not detail_df.empty and "family_id" in detail_df.columns:
        detail_columns = [column for column in ("family_id", "subjek", "nama", "usia", "suku") if column in detail_df.columns]
        if len(detail_columns) > 1:
            detail_profile_df = detail_df[detail_columns].drop_duplicates(subset=["family_id"]).copy()
            profile_df = profile_df.merge(detail_profile_df, on="family_id", how="left", suffixes=("", "_detail"))

    for column in ("subjek", "nama", "suku"):
        if column not in profile_df.columns:
            profile_df[column] = pd.NA
        base_series = profile_df[column].astype("string").str.strip()
        base_series = base_series.mask(base_series.isna() | base_series.eq("") | base_series.str.lower().eq("nan"))
        if column in PERSON_DISPLAY_NAME_COLUMNS:
            base_series = base_series.map(lambda value, col=column: format_display_name_value(value, col))
        detail_column = f"{column}_detail"
        if detail_column in profile_df.columns:
            detail_series = profile_df[detail_column].astype("string").str.strip()
            detail_series = detail_series.mask(detail_series.isna() | detail_series.eq("") | detail_series.str.lower().eq("nan"))
            if column in PERSON_DISPLAY_NAME_COLUMNS:
                detail_series = detail_series.map(lambda value, col=column: format_display_name_value(value, col))
            profile_df[column] = base_series.fillna(detail_series)
        else:
            profile_df[column] = base_series

    if "usia" not in profile_df.columns:
        profile_df["usia"] = pd.NA
    usia_series = pd.to_numeric(profile_df["usia"], errors="coerce")
    if "usia_detail" in profile_df.columns:
        usia_detail_series = pd.to_numeric(profile_df["usia_detail"], errors="coerce")
        profile_df["usia"] = usia_series.fillna(usia_detail_series)
    else:
        profile_df["usia"] = usia_series

    fallback_label = profile_df["family_id"].astype("string")
    subjek_series = profile_df["subjek"].astype("string").str.strip()
    subjek_series = subjek_series.mask(subjek_series.isna() | subjek_series.eq("") | subjek_series.str.lower().eq("nan"))
    subjek_series = subjek_series.mask(subjek_series.str.lower().eq("kepala keluarga"))
    subjek_series = subjek_series.map(format_person_display_name).fillna(fallback_label)

    nama_series = profile_df["nama"].astype("string").str.strip()
    nama_series = nama_series.mask(nama_series.isna() | nama_series.eq("") | nama_series.str.lower().eq("nan"))
    nama_series = nama_series.map(format_person_display_name)
    profile_df["nama_kk_subjek"] = nama_series.fillna(subjek_series).fillna(fallback_label)
    profile_df["label_kk"] = profile_df["nama_kk_subjek"].astype("string")

    duplicated_label_mask = profile_df["label_kk"].duplicated(keep=False)
    profile_df.loc[duplicated_label_mask, "label_kk"] = (
        profile_df.loc[duplicated_label_mask, "label_kk"].astype("string")
        + " | "
        + profile_df.loc[duplicated_label_mask, "family_id"].astype("string")
    )

    drop_columns = [column for column in profile_df.columns if column.endswith("_detail")]
    if drop_columns:
        profile_df = profile_df.drop(columns=drop_columns)
    return profile_df


def exclude_unscored_iid_category(df: pd.DataFrame, category_column: str = "kategori_iid_rt") -> pd.DataFrame:
    if df.empty or category_column not in df.columns:
        return df.copy()
    filtered_df = df.copy()
    filtered_df[category_column] = filtered_df[category_column].astype("string")
    return filtered_df.loc[
        filtered_df[category_column].notna()
        & filtered_df[category_column].ne(iid_pipeline.UNSCORED_IID_CATEGORY_LABEL)
    ].copy()


def add_desa_label(
    df: pd.DataFrame,
    label_column: str = "label_desa",
    name_column: str = "deskel",
    code_column: str = "kode_deskel",
) -> pd.DataFrame:
    labeled_df = df.copy()
    if labeled_df.empty:
        labeled_df[label_column] = pd.Series(dtype="string")
        return labeled_df
    if name_column not in labeled_df.columns:
        labeled_df[label_column] = labeled_df.index.astype("string")
        return labeled_df

    name_series = (
        labeled_df[name_column]
        .map(lambda value: format_display_name_value(value, name_column))
        .astype("string")
        .fillna("-")
        .str.strip()
    )
    labeled_df[label_column] = name_series
    if code_column in labeled_df.columns:
        code_series = labeled_df[code_column].astype("string")
        has_code = code_series.notna() & code_series.str.strip().ne("") & code_series.str.strip().str.lower().ne("nan")
        labeled_df.loc[has_code, label_column] = (
            name_series.loc[has_code] + " (" + code_series.loc[has_code].str.strip() + ")"
        )
    return labeled_df


def add_top_rank_highlight(
    df: pd.DataFrame,
    value_column: str,
    group_column: str | None = None,
    highlight_column: str = "_rank_highlight",
) -> pd.DataFrame:
    highlighted_df = df.copy()
    highlighted_df[value_column] = pd.to_numeric(highlighted_df[value_column], errors="coerce")
    highlighted_df = highlighted_df.dropna(subset=[value_column]).copy()
    if group_column and group_column in highlighted_df.columns:
        highlighted_df["_rank_number"] = highlighted_df.groupby(group_column)[value_column].rank(
            method="first",
            ascending=False,
        )
    else:
        highlighted_df["_rank_number"] = highlighted_df[value_column].rank(method="first", ascending=False)
    highlighted_df[highlight_column] = highlighted_df["_rank_number"].map(
        {
            1.0: "Rank 1",
            2.0: "Rank 2",
            3.0: "Rank 3",
        }
    ).fillna("Other Values")
    return highlighted_df


def build_ranked_red_bar_figure(
    df: pd.DataFrame,
    value_column: str,
    label_column: str,
    title: str,
    xaxis_title: str,
    yaxis_title: str,
    text_auto: str = ".3f",
    orientation: str = "v",
) -> go.Figure:
    plot_df = add_top_rank_highlight(df, value_column).sort_values(value_column, ascending=False, kind="mergesort")
    fig = px.bar(
        plot_df,
        x=label_column if orientation == "v" else value_column,
        y=value_column if orientation == "v" else label_column,
        orientation=orientation,
        color="_rank_highlight",
        color_discrete_map=RED_RANK_COLORS,
        category_orders={"_rank_highlight": RED_RANK_ORDER},
        text_auto=text_auto,
        hover_data={"_rank_highlight": True, "_rank_number": ":.0f"},
    )
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        margin=dict(l=10, r=10, t=60, b=10),
        legend_title_text="Value Rank",
    )
    fig.update_traces(marker_line_color="#7f1d1d", marker_line_width=0.8)
    if orientation == "v":
        fig.update_xaxes(tickangle=-22)
    return apply_publication_figure_style(fig)


def resolve_inequality_tables(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_df = tables.get("ringkasan_ketimpangan", pd.DataFrame()).copy()
    contributor_df = tables.get("kontributor_ketimpangan", pd.DataFrame()).copy()
    valid_gini_labels = set(iid_pipeline.GINI_CATEGORY_ORDER)
    summary_labels = set(summary_df.get("interpretasi_gini", pd.Series(dtype="string")).dropna().astype("string").tolist())
    contributor_labels = set(
        contributor_df.get("interpretasi_gini_cakupan", pd.Series(dtype="string")).dropna().astype("string").tolist()
    )
    uses_relative_labels = (
        (not summary_labels or summary_labels.issubset(valid_gini_labels))
        and (not contributor_labels or contributor_labels.issubset(valid_gini_labels))
    )

    if summary_df.empty or contributor_df.empty or not uses_relative_labels:
        household_df = get_household_rows(tables.get("data_keluarga", pd.DataFrame()))
        if not household_df.empty:
            summary_df, contributor_df = iid_pipeline.build_gini_assessment_tables(household_df)

    for column in (
        "jumlah_kk",
        "rata_rata_iid_rumah_tangga",
        "gini_iid_rumah_tangga",
        "jumlah_kontributor_non_nol",
        "iid_kontributor_utama",
        "porsi_kontributor_utama",
    ):
        if column in summary_df.columns:
            summary_df[column] = pd.to_numeric(summary_df[column], errors="coerce")

    for column in (
        "jumlah_kk_cakupan",
        "gini_iid_rumah_tangga_cakupan",
        "rata_rata_iid_cakupan",
        "iid_rumah_tangga",
        "deviasi_iid_cakupan",
        "jumlah_selisih_pasangan",
        "kontribusi_gini",
        "porsi_kontribusi_gini",
        "peringkat_kontribusi",
    ):
        if column in contributor_df.columns:
            contributor_df[column] = pd.to_numeric(contributor_df[column], errors="coerce")

    return apply_display_name_casing(summary_df), apply_display_name_casing(contributor_df)


def build_top_inequality_contributors_figure(
    contributor_df: pd.DataFrame,
    title: str,
    top_n: int = 15,
) -> go.Figure:
    plot_df = contributor_df.copy()
    plot_df = plot_df.sort_values(
        ["porsi_kontribusi_gini", "kontribusi_gini", "iid_rumah_tangga"],
        ascending=[False, False, False],
        kind="mergesort",
    ).head(top_n)
    if "label_kk" in plot_df.columns:
        plot_df["label_rt"] = plot_df["label_kk"].astype("string")
    elif plot_df["deskel"].astype("string").nunique(dropna=True) > 1:
        plot_df["label_rt"] = plot_df["family_id"].astype("string") + " | " + plot_df["deskel"].astype("string")
    else:
        plot_df["label_rt"] = plot_df["family_id"].astype("string")
    plot_df = plot_df.sort_values("porsi_kontribusi_gini", ascending=True, kind="mergesort")
    plot_df["score_position_label"] = plot_df["arah_deviasi"].map(format_inequality_direction_label)
    if "kategori_iid_rt" in plot_df.columns:
        plot_df["iid_category_label"] = plot_df["kategori_iid_rt"].map(format_iid_category_label)

    hover_data: dict[str, Any] = {
        "family_id": True,
        "deskel": True,
        "iid_rumah_tangga": ":.3f",
        "rata_rata_iid_cakupan": ":.3f",
        "kontribusi_gini": ":.4f",
        "porsi_kontribusi_gini": ":.2%",
        "label_rt": False,
        "score_position_label": True,
    }
    if "nama_kk_subjek" in plot_df.columns:
        hover_data["nama_kk_subjek"] = True
    if "kategori_iid_rt" in plot_df.columns:
        hover_data["iid_category_label"] = True
    if "usia" in plot_df.columns:
        hover_data["usia"] = True
    if "suku" in plot_df.columns:
        hover_data["suku"] = True

    fig = px.bar(
        plot_df,
        x="porsi_kontribusi_gini",
        y="label_rt",
        orientation="h",
        color="score_position_label",
        color_discrete_map=INEQUALITY_DIRECTION_COLORS,
        text=plot_df["porsi_kontribusi_gini"].map(lambda value: f"{float(value) * 100:.2f}%"),
        hover_data=hover_data,
        labels={
            "label_rt": "Household",
            "family_id": "Household ID",
            "deskel": "Village",
            "iid_rumah_tangga": "Household Digital Inclusion Index",
            "rata_rata_iid_cakupan": "Mean Index in Selected Scope",
            "kontribusi_gini": "Gini Contribution",
            "porsi_kontribusi_gini": "Gini Contribution Share",
            "score_position_label": "Score Position",
            "iid_category_label": "Household Digital Inclusion Category",
            "nama_kk_subjek": "Household Head or Subject",
            "usia": "Age",
            "suku": "Ethnic Group",
        },
    )
    fig.update_layout(
        title=title,
        xaxis_title="Share of Total Gini Inequality",
        yaxis_title="Household",
        legend_title_text="Score Position",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(tickformat=".2%", hoverformat=".2%")
    return apply_publication_figure_style(fig)


def build_contributor_profile_preview_df(contributor_df: pd.DataFrame) -> pd.DataFrame:
    preview_columns = [
        column
        for column in (
            "nama_kk_subjek",
            "usia",
            "suku",
            "kategori_iid_rt",
            "iid_rumah_tangga",
            "porsi_kontribusi_gini",
            "arah_deviasi",
            "jml_keluarga",
            "dimensi_A",
            "dimensi_B",
            "dimensi_C",
            "dimensi_D",
            "dimensi_E",
            "indikator_A",
            "indikator_B",
            "indikator_C",
            "indikator_D",
            "indikator_E",
            "indikator_F",
            "indikator_G",
            "indikator_H",
            "indikator_I",
            "indikator_J",
            "indikator_K",
            "indikator_L",
            "indikator_M",
        )
        if column in contributor_df.columns
    ]
    preview_df = contributor_df[preview_columns].copy()
    if "porsi_kontribusi_gini" in preview_df.columns:
        preview_df["porsi_kontribusi_gini"] = preview_df["porsi_kontribusi_gini"].map(format_percent)
    if "kategori_iid_rt" in preview_df.columns:
        preview_df["kategori_iid_rt"] = preview_df["kategori_iid_rt"].map(format_iid_category_label)
    if "arah_deviasi" in preview_df.columns:
        preview_df["arah_deviasi"] = preview_df["arah_deviasi"].map(format_inequality_direction_label)
    return preview_df.rename(
        columns={
            "nama_kk_subjek": "Household Head or Subject",
            "usia": "Age",
            "suku": "Ethnic Group",
            "kategori_iid_rt": "Household Digital Inclusion Category",
            "iid_rumah_tangga": "Household Digital Inclusion Index",
            "porsi_kontribusi_gini": "Gini Contribution Share",
            "arah_deviasi": "Position Against Mean",
            "jml_keluarga": "Household Members",
            "dimensi_A": "Dimension A - Device Access",
            "dimensi_B": "Dimension B - Internet Connectivity",
            "dimensi_C": "Dimension C - Human Capacity",
            "dimensi_D": "Dimension D - Digital Use",
            "dimensi_E": "Dimension E - Social Enabling Environment",
            "indikator_A": "Indicator A - Mobile Phone Ownership",
            "indikator_B": "Indicator B - Mobile Phone Sufficiency",
            "indikator_C": "Indicator C - Productive Digital Device Ownership",
            "indikator_D": "Indicator D - Household Internet Access",
            "indikator_E": "Indicator E - Household Head Educational Attainment",
            "indikator_F": "Indicator F - School Participation Ratio",
            "indikator_G": "Indicator G - Household Head Organizational Involvement",
            "indikator_H": "Indicator H - Household Member Organizational Involvement",
            "indikator_I": "Indicator I - Household Head Community Participation",
            "indikator_J": "Indicator J - Household Member Community Participation",
            "indikator_K": "Indicator K - Social Media Use",
            "indikator_L": "Indicator L - Information Media Access",
            "indikator_M": "Indicator M - Policy Information Participation",
        }
    )


def get_coordinate_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    lat_col = "lat" if "lat" in df.columns else None
    lon_col = None
    for candidate in ("long", "lng", "lon", "longitude"):
        if candidate in df.columns:
            lon_col = candidate
            break
    return lat_col, lon_col


def format_journal_number(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{numeric_value:,.{digits}f}" if digits > 0 else f"{numeric_value:,.0f}"


def format_journal_percent(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


PUBLICATION_FONT_FAMILY = "Arial, Helvetica, sans-serif"
CARTESIAN_TRACE_TYPES = {"bar", "box", "histogram", "scatter", "heatmap"}


def apply_publication_figure_style(
    fig: go.Figure,
    *,
    integer_x: bool = False,
    integer_y: bool = False,
) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        separators=".,",
        font=dict(family=PUBLICATION_FONT_FAMILY, size=13, color="#1f2937"),
        title=dict(x=0, xanchor="left", font=dict(size=18, color="#111827")),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor="#cbd5e1",
            font=dict(family=PUBLICATION_FONT_FAMILY, size=12, color="#111827"),
        ),
        legend=dict(
            font=dict(size=12),
            title_font=dict(size=12),
        ),
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )

    has_cartesian_axes = any(getattr(trace, "type", None) in CARTESIAN_TRACE_TYPES for trace in fig.data)
    if has_cartesian_axes:
        axis_style = dict(
            showline=True,
            linewidth=1,
            linecolor="#cbd5e1",
            ticks="outside",
            tickcolor="#cbd5e1",
            ticklen=4,
            gridcolor="#e5e7eb",
            zeroline=False,
            automargin=True,
            exponentformat="none",
            separatethousands=True,
            tickfont=dict(size=12, color="#4b5563"),
            title_font=dict(size=13, color="#4b5563"),
        )
        fig.update_xaxes(**axis_style)
        fig.update_yaxes(**axis_style)
        if integer_x:
            fig.update_xaxes(tickformat=",.0f")
        if integer_y:
            fig.update_yaxes(tickformat=",.0f")

    fig.update_traces(
        textfont=dict(family=PUBLICATION_FONT_FAMILY, size=12),
        cliponaxis=False,
        selector=dict(type="bar"),
    )
    return fig


def apply_bar_value_text_format(fig: go.Figure, value_axis: str, digits: int = 0, suffix: str = "") -> go.Figure:
    fig.update_traces(
        texttemplate=f"%{{{value_axis}:,.{digits}f}}{suffix}",
        textposition="auto",
        selector=dict(type="bar"),
    )
    return fig


def format_journal_dataframe(
    df: pd.DataFrame,
    percent_columns: tuple[str, ...] = (),
    integer_columns: tuple[str, ...] = (),
    score_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    display_df = df.copy()
    for column in percent_columns:
        if column in display_df.columns:
            display_df[column] = display_df[column].map(format_journal_percent)
    for column in integer_columns:
        if column in display_df.columns:
            display_df[column] = display_df[column].map(lambda value: format_journal_number(value, 0))
    for column in score_columns:
        if column in display_df.columns:
            display_df[column] = pd.to_numeric(display_df[column], errors="coerce").round(3)
    return prepare_display_dataframe(display_df)


def add_journal_village_name(
    df: pd.DataFrame,
    label_column: str = "Village",
    name_column: str = "deskel",
    code_column: str = "kode_deskel",
) -> pd.DataFrame:
    labeled_df = df.copy()
    if labeled_df.empty:
        labeled_df[label_column] = pd.Series(dtype="string")
        return labeled_df

    if name_column in labeled_df.columns:
        village_series = (
            labeled_df[name_column]
            .map(lambda value: format_display_name_value(value, name_column))
            .astype("string")
            .str.strip()
        )
        village_series = village_series.mask(
            village_series.isna() | village_series.eq("") | village_series.str.lower().eq("nan")
        )
        fallback_series = pd.Series(labeled_df.index.astype("string"), index=labeled_df.index)
        labeled_df["_journal_village_base"] = village_series.fillna(fallback_series)

        if code_column in labeled_df.columns:
            village_map = (
                labeled_df[[code_column, "_journal_village_base"]]
                .drop_duplicates()
                .sort_values(["_journal_village_base", code_column], kind="mergesort")
                .copy()
            )
            duplicate_name_mask = village_map["_journal_village_base"].duplicated(keep=False)
            village_map["_journal_village_number"] = (
                village_map.groupby("_journal_village_base", dropna=False).cumcount() + 1
            )
            village_map[label_column] = village_map["_journal_village_base"]
            village_map.loc[duplicate_name_mask, label_column] = (
                village_map.loc[duplicate_name_mask, "_journal_village_base"].astype(str)
                + " - "
                + village_map.loc[duplicate_name_mask, "_journal_village_number"].astype(str)
            )
            labeled_df = labeled_df.merge(
                village_map[[code_column, label_column]].drop_duplicates(),
                on=code_column,
                how="left",
            )
            labeled_df[label_column] = labeled_df[label_column].fillna(labeled_df["_journal_village_base"])
        else:
            labeled_df[label_column] = labeled_df["_journal_village_base"]

        labeled_df = labeled_df.drop(columns=["_journal_village_base"], errors="ignore")
    else:
        labeled_df[label_column] = labeled_df.index.astype("string")

    return labeled_df


def get_journal_page_slice(total_items: int, page: int, page_size: int = JOURNAL_VILLAGE_PAGE_SIZE) -> tuple[int, int]:
    safe_total = max(int(total_items), 0)
    safe_page = max(int(page), 0)
    start = min(safe_page * page_size, safe_total)
    end = min(start + page_size, safe_total)
    return start, end


def render_journal_page_selector(
    container: Any,
    label: str,
    total_items: int,
    key: str,
    page_size: int = JOURNAL_VILLAGE_PAGE_SIZE,
) -> tuple[int, int, str]:
    safe_total = max(int(total_items), 0)
    if safe_total <= page_size:
        page_label = f"Showing {safe_total} village(s)"
        container.caption(page_label)
        return 0, safe_total, page_label

    total_pages = (safe_total + page_size - 1) // page_size
    selected_page = container.selectbox(
        label,
        options=list(range(total_pages)),
        format_func=lambda page: (
            f"Page {page + 1} ({page * page_size + 1}-{min((page + 1) * page_size, safe_total)} of {safe_total})"
        ),
        key=key,
    )
    start, end = get_journal_page_slice(safe_total, int(selected_page), page_size)
    return start, end, f"Page {int(selected_page) + 1}"


def build_journal_overview_table_html(
    total_households: int,
    total_villages: int,
    mean_household_index: Any,
    mean_village_index: Any,
    vulnerable_share: Any,
) -> str:
    rows = [
        (
            "Valid Households",
            format_journal_number(total_households, 0),
            "Household records included in the household-level digital inclusion analysis.",
        ),
        (
            "Villages",
            format_journal_number(total_villages, 0),
            "Village-level units available in the processed index table.",
        ),
        (
            "Mean Household Index",
            format_journal_number(mean_household_index),
            "Average household digital inclusion index on the 0-1 scale.",
        ),
        (
            "Mean Village Index",
            format_journal_number(mean_village_index),
            "Average village digital inclusion index on the 0-1 scale.",
        ),
        (
            "Digitally Vulnerable Share",
            format_journal_percent(vulnerable_share),
            "Share of households classified as very low or low digital inclusion.",
        ),
    ]
    body_rows = "\n".join(
        (
            "<tr>"
            f"<td class='journal-overview-metric'>{escape(metric)}</td>"
            f"<td class='journal-overview-value'>{escape(value)}</td>"
            f"<td class='journal-overview-note'>{escape(note)}</td>"
            "</tr>"
        )
        for metric, value, note in rows
    )
    return f"""
    <div class="journal-overview-table-wrap">
        <table class="journal-overview-table">
            <thead>
                <tr>
                    <th>Summary Measure</th>
                    <th>Value</th>
                    <th>Operational Definition</th>
                </tr>
            </thead>
            <tbody>
                {body_rows}
            </tbody>
        </table>
    </div>
    """


def prepare_journal_household_df(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    household_df = get_household_rows(tables.get("data_keluarga", pd.DataFrame()))
    if household_df.empty:
        return household_df

    numeric_columns = [
        "iid_rumah_tangga",
        *JOURNAL_DIMENSION_LABELS.keys(),
        *JOURNAL_INDICATOR_LABELS.keys(),
        "lat",
        "long",
        "lng",
        "lon",
        "longitude",
        "jumlah_anggota_rumah_tangga",
        "jml_keluarga",
    ]
    for column in numeric_columns:
        if column in household_df.columns:
            household_df[column] = pd.to_numeric(household_df[column], errors="coerce")

    if "kategori_iid_rt" not in household_df.columns:
        household_df["kategori_iid_rt"] = household_df["iid_rumah_tangga"].apply(iid_pipeline.classify_iid_rt)

    household_df = exclude_unscored_iid_category(household_df)
    household_df["Digital Inclusion Category"] = (
        household_df["kategori_iid_rt"].astype(str).map(JOURNAL_CATEGORY_LABELS)
    )
    household_df = household_df.loc[household_df["Digital Inclusion Category"].notna()].copy()
    return household_df


def prepare_journal_raw_profile_df(detail_df: pd.DataFrame, household_df: pd.DataFrame) -> pd.DataFrame:
    raw_columns = {
        "ijazah",
        "hp_punya",
        "hp_jumlah",
        "elektronik_rumah",
        "wifi_teragregasi",
        "hp_provider_teragregasi",
        "jumlah_organisasi_kepala",
        "jumlah_organisasi_anggota",
        "jumlah_partisipasi_masyarakat_kepala",
        "jumlah_partisipasi_masyarakat_anggota",
        "jumlah_partisipasi_kebijakan",
    }
    if not detail_df.empty and raw_columns.intersection(detail_df.columns):
        raw_df = detail_df.copy()
    else:
        raw_df = household_df.copy()

    if raw_df.empty:
        return raw_df

    if "family_id" in raw_df.columns:
        raw_df = raw_df.drop_duplicates(subset=["family_id"], keep="first").copy()

    if "family_id" in raw_df.columns and not household_df.empty and "family_id" in household_df.columns:
        merge_columns = [
            column
            for column in ("family_id", "kategori_iid_rt", "Digital Inclusion Category")
            if column in household_df.columns
        ]
        if len(merge_columns) > 1:
            raw_df = raw_df.merge(
                household_df[merge_columns].drop_duplicates(subset=["family_id"]),
                on="family_id",
                how="left",
                suffixes=("", "_score"),
            )
            for column in ("kategori_iid_rt", "Digital Inclusion Category"):
                score_column = f"{column}_score"
                if score_column in raw_df.columns:
                    if column in raw_df.columns:
                        raw_df[column] = raw_df[column].fillna(raw_df[score_column])
                    else:
                        raw_df[column] = raw_df[score_column]
            raw_df = raw_df.drop(columns=[column for column in raw_df.columns if column.endswith("_score")])

    numeric_columns = (
        "hp_jumlah",
        "hp_jumlah_num",
        "hp_jumlah_terstandar",
        "jumlah_perangkat_produktif_rumah_tangga",
        "jumlah_organisasi_kepala",
        "jumlah_organisasi_anggota",
        "jumlah_partisipasi_masyarakat_kepala",
        "jumlah_partisipasi_masyarakat_anggota",
        "jumlah_partisipasi_kebijakan",
    )
    for column in numeric_columns:
        if column in raw_df.columns:
            raw_df[column] = pd.to_numeric(raw_df[column], errors="coerce")

    return raw_df


def prepare_journal_village_df(
    tables: dict[str, pd.DataFrame],
    household_df: pd.DataFrame,
) -> pd.DataFrame:
    village_df = normalize_desa_gini_table(tables.get("indeks_desa", pd.DataFrame()))
    if village_df.empty:
        return village_df

    village_df = add_journal_village_name(village_df.copy())
    numeric_columns = [
        "jumlah_kk",
        "iid_desa",
        "ikd_desa",
        "gini_iid_rumah_tangga",
        *JOURNAL_DIMENSION_LABELS.keys(),
    ]
    for column in numeric_columns:
        if column in village_df.columns:
            village_df[column] = pd.to_numeric(village_df[column], errors="coerce")
    if "ikd_desa" not in village_df.columns and "iid_desa" in village_df.columns:
        village_df["ikd_desa"] = 1 - village_df["iid_desa"]

    if "iid_desa" in village_df.columns:
        village_df["Village Rank"] = village_df["iid_desa"].rank(method="first", ascending=False).astype("Int64")
    if "interpretasi_gini" in village_df.columns:
        village_df["Within-Village Gini Category"] = (
            village_df["interpretasi_gini"].astype(str).map(JOURNAL_GINI_LABELS).fillna(village_df["interpretasi_gini"])
        )

    lat_col, lon_col = get_coordinate_columns(household_df)
    if lat_col and lon_col and not household_df.empty:
        coord_df = household_df.copy()
        coord_df[lat_col] = pd.to_numeric(coord_df[lat_col], errors="coerce")
        coord_df[lon_col] = pd.to_numeric(coord_df[lon_col], errors="coerce")
        coord_df = coord_df.dropna(subset=[lat_col, lon_col])
        if not coord_df.empty:
            if "kode_deskel" in coord_df.columns and "kode_deskel" in village_df.columns:
                centroid_df = (
                    coord_df.groupby("kode_deskel", dropna=False)[[lat_col, lon_col]]
                    .mean()
                    .rename(columns={lat_col: "village_lat", lon_col: "village_lon"})
                    .reset_index()
                )
                village_df = village_df.merge(centroid_df, on="kode_deskel", how="left")
            elif "deskel" in coord_df.columns and "deskel" in village_df.columns:
                centroid_df = (
                    coord_df.groupby("deskel", dropna=False)[[lat_col, lon_col]]
                    .mean()
                    .rename(columns={lat_col: "village_lat", lon_col: "village_lon"})
                    .reset_index()
                )
                village_df = village_df.merge(centroid_df, on="deskel", how="left")

    return village_df


def build_journal_domain_profile_df(household_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for domain, columns in JOURNAL_PROFILE_DOMAINS.items():
        existing_columns = [column for column in columns if column in household_df.columns]
        if not existing_columns:
            continue
        score_df = household_df[existing_columns].apply(pd.to_numeric, errors="coerce")
        domain_score = score_df.mean(axis=1, skipna=True)
        rows.append(
            {
                "Profile Domain": domain,
                "Mean Score": float(domain_score.mean()) if domain_score.notna().any() else pd.NA,
                "Median Score": float(domain_score.median()) if domain_score.notna().any() else pd.NA,
                "Valid Households": int(domain_score.notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def build_journal_indicator_profile_df(household_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column, label in JOURNAL_INDICATOR_LABELS.items():
        if column not in household_df.columns:
            continue
        score = pd.to_numeric(household_df[column], errors="coerce")
        rows.append(
            {
                "Indicator": label,
                "Mean Score": float(score.mean()) if score.notna().any() else pd.NA,
                "Median Score": float(score.median()) if score.notna().any() else pd.NA,
                "Valid Households": int(score.notna().sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("Mean Score", ascending=True, kind="mergesort")


def build_journal_domain_profile_figure(profile_df: pd.DataFrame) -> go.Figure:
    plot_df = profile_df.sort_values("Mean Score", ascending=True, kind="mergesort")
    fig = px.bar(
        plot_df,
        x="Mean Score",
        y="Profile Domain",
        orientation="h",
        color="Mean Score",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text_auto=".3f",
        hover_data={"Median Score": ":.3f", "Valid Households": ":,.0f"},
    )
    fig.update_layout(
        title="Descriptive Profile of Household Digital Readiness Domains",
        xaxis_title="Mean Score",
        yaxis_title="Profile Domain",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_indicator_profile_figure(indicator_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        indicator_df,
        x="Mean Score",
        y="Indicator",
        orientation="h",
        color="Mean Score",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text_auto=".3f",
        hover_data={"Median Score": ":.3f", "Valid Households": ":,.0f"},
    )
    fig.update_layout(
        title="Mean Score of Household-Level Digital Inclusion Indicators",
        xaxis_title="Mean Score",
        yaxis_title="Indicator",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
        height=max(520, 30 * max(len(indicator_df), 1) + 160),
    )
    fig.update_xaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def normalize_journal_raw_text_series(series: pd.Series) -> pd.Series:
    normalized_series = series.astype("string").str.strip()
    return normalized_series.mask(
        normalized_series.isna()
        | normalized_series.eq("")
        | normalized_series.str.lower().isin({"nan", "none", "<na>", "null"})
    )


def format_journal_category_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return "Not Recorded"
    label = str(value).strip()
    if not label or label.lower() in {"nan", "none", "<na>", "null"}:
        return "Not Recorded"
    return label.title()


def build_journal_binary_share_df(rows: list[dict[str, Any]], label_column: str) -> pd.DataFrame:
    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return plot_df
    plot_df["Share"] = plot_df["Households"] / plot_df["Total Households"].replace(0, pd.NA)
    return plot_df[[label_column, "Households", "Total Households", "Share"]]


def build_journal_education_histogram_figure(raw_df: pd.DataFrame) -> go.Figure | None:
    if "ijazah" not in raw_df.columns:
        return None

    education_series = normalize_journal_raw_text_series(raw_df["ijazah"]).map(format_journal_category_label)
    education_counts = education_series.value_counts(dropna=False).reset_index()
    education_counts.columns = ["Educational Attainment", "Households"]
    education_counts["Share"] = education_counts["Households"] / max(int(education_counts["Households"].sum()), 1)
    if education_counts.empty:
        return None

    fig = px.bar(
        education_counts.sort_values("Households", ascending=True, kind="mergesort"),
        x="Households",
        y="Educational Attainment",
        orientation="h",
        color="Households",
        color_continuous_scale=["#dbeafe", "#2563eb", "#163249"],
        text="Households",
        custom_data=["Share"],
    )
    fig.update_layout(
        title="Educational Attainment of Household Heads",
        xaxis_title="Number of Households",
        yaxis_title="Educational Attainment",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False,
    )
    fig.update_xaxes(tickformat=",.0f")
    apply_bar_value_text_format(fig, "x")
    fig.update_traces(
        hovertemplate=(
            "Educational Attainment: %{y}<br>"
            "Households: %{x:,.0f}<br>"
            "Share: %{customdata[0]:.2%}<extra></extra>"
        )
    )
    return apply_publication_figure_style(fig, integer_x=True)


def build_journal_device_ownership_bar_figure(raw_df: pd.DataFrame) -> go.Figure | None:
    total_households = int(len(raw_df))
    if total_households == 0:
        return None

    hp_owned = pd.Series(False, index=raw_df.index)
    if "hp_punya" in raw_df.columns:
        hp_norm = raw_df["hp_punya"].astype("string").str.strip().str.lower()
        hp_owned = hp_norm.isin(iid_pipeline.YES_VALUES)
    if "hp_jumlah_terstandar" in raw_df.columns:
        hp_owned = hp_owned | pd.to_numeric(raw_df["hp_jumlah_terstandar"], errors="coerce").fillna(0).gt(0)
    elif "hp_jumlah" in raw_df.columns:
        hp_owned = hp_owned | pd.to_numeric(raw_df["hp_jumlah"], errors="coerce").fillna(0).gt(0)

    productive_device = pd.Series(False, index=raw_df.index)
    if "jumlah_perangkat_produktif_rumah_tangga" in raw_df.columns:
        productive_device = pd.to_numeric(
            raw_df["jumlah_perangkat_produktif_rumah_tangga"],
            errors="coerce",
        ).fillna(0).gt(0)
    elif "elektronik_rumah" in raw_df.columns:
        productive_device = raw_df["elektronik_rumah"].apply(
            lambda value: iid_pipeline.count_keyword_matches(value, iid_pipeline.DIGITAL_PRODUCTIVE_DEVICE_KEYWORDS) > 0
        )

    two_or_more_phones = pd.Series(False, index=raw_df.index)
    phone_column = "hp_jumlah_terstandar" if "hp_jumlah_terstandar" in raw_df.columns else "hp_jumlah"
    if phone_column in raw_df.columns:
        two_or_more_phones = pd.to_numeric(raw_df[phone_column], errors="coerce").fillna(0).ge(2)

    plot_df = build_journal_binary_share_df(
        [
            {
                "Device Ownership Measure": "Mobile Phone Owned",
                "Households": int(hp_owned.sum()),
                "Total Households": total_households,
            },
            {
                "Device Ownership Measure": "Two or More Mobile Phones",
                "Households": int(two_or_more_phones.sum()),
                "Total Households": total_households,
            },
            {
                "Device Ownership Measure": "Productive Digital Device Owned",
                "Households": int(productive_device.sum()),
                "Total Households": total_households,
            },
        ],
        "Device Ownership Measure",
    )
    if plot_df.empty:
        return None
    plot_df["Share Label"] = plot_df["Share"].map(lambda value: f"{float(value) * 100:.1f}%")

    fig = px.bar(
        plot_df,
        x="Device Ownership Measure",
        y="Share",
        color="Share",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text="Share Label",
        hover_data={"Households": ":,.0f", "Total Households": ":,.0f", "Share": ":.2%"},
    )
    fig.update_layout(
        title="Household Device Ownership from Source Data",
        xaxis_title="Device Ownership Measure",
        yaxis_title="Share of Households",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=80),
    )
    fig.update_xaxes(tickangle=-14, automargin=True)
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_phone_count_histogram_figure(raw_df: pd.DataFrame) -> go.Figure | None:
    phone_column = "hp_jumlah_terstandar" if "hp_jumlah_terstandar" in raw_df.columns else "hp_jumlah"
    if phone_column not in raw_df.columns:
        return None
    phone_counts = pd.to_numeric(raw_df[phone_column], errors="coerce").fillna(0).clip(lower=0)
    phone_band = phone_counts.astype(int).clip(upper=5).astype("string")
    phone_band = phone_band.mask(phone_counts.ge(6), "6+")
    plot_df = (
        phone_band.value_counts()
        .reindex(["0", "1", "2", "3", "4", "5", "6+"], fill_value=0)
        .rename_axis("Number of Mobile Phones")
        .reset_index(name="Households")
    )
    plot_df["Share"] = plot_df["Households"] / max(int(plot_df["Households"].sum()), 1)
    fig = px.bar(
        plot_df,
        x="Number of Mobile Phones",
        y="Households",
        color="Households",
        color_continuous_scale=["#dbeafe", "#2563eb", "#163249"],
        text="Households",
        custom_data=["Share"],
    )
    fig.update_layout(
        title="Distribution of Mobile Phone Counts per Household",
        xaxis_title="Number of Mobile Phones",
        yaxis_title="Number of Households",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    apply_bar_value_text_format(fig, "y")
    fig.update_traces(
        hovertemplate=(
            "Number of Mobile Phones: %{x}<br>"
            "Households: %{y:,.0f}<br>"
            "Share: %{customdata[0]:.2%}<extra></extra>"
        )
    )
    return apply_publication_figure_style(fig, integer_y=True)


def build_journal_internet_access_pie_figure(raw_df: pd.DataFrame) -> go.Figure | None:
    if raw_df.empty:
        return None

    wifi_available = pd.Series(False, index=raw_df.index)
    if "wifi_teragregasi" in raw_df.columns:
        wifi_available = raw_df["wifi_teragregasi"].apply(iid_pipeline.count_multivalue_items).gt(0)
    elif "wifi" in raw_df.columns:
        wifi_available = raw_df["wifi"].apply(iid_pipeline.count_multivalue_items).gt(0)

    provider_available = pd.Series(False, index=raw_df.index)
    if "hp_provider_teragregasi" in raw_df.columns:
        provider_available = raw_df["hp_provider_teragregasi"].apply(iid_pipeline.count_multivalue_items).gt(0)
    elif "hp_provider" in raw_df.columns:
        provider_available = raw_df["hp_provider"].apply(iid_pipeline.count_multivalue_items).gt(0)

    access_type = pd.Series("No Recorded Internet Access", index=raw_df.index, dtype="object")
    access_type.loc[wifi_available & provider_available] = "Wi-Fi and Mobile Data"
    access_type.loc[wifi_available & ~provider_available] = "Wi-Fi Only"
    access_type.loc[~wifi_available & provider_available] = "Mobile Data Only"

    distribution_df = (
        access_type.value_counts()
        .reindex(
            [
                "Wi-Fi and Mobile Data",
                "Mobile Data Only",
                "Wi-Fi Only",
                "No Recorded Internet Access",
            ],
            fill_value=0,
        )
        .rename_axis("Internet Access Type")
        .reset_index(name="Households")
    )
    distribution_df["Share"] = distribution_df["Households"] / max(int(distribution_df["Households"].sum()), 1)
    if distribution_df.empty:
        return None

    internet_colors = {
        "Wi-Fi and Mobile Data": "#0f766e",
        "Mobile Data Only": "#2563eb",
        "Wi-Fi Only": "#14b8a6",
        "No Recorded Internet Access": "#b91c1c",
    }
    fig = px.pie(
        distribution_df,
        values="Households",
        names="Internet Access Type",
        color="Internet Access Type",
        color_discrete_map=internet_colors,
        hole=0.42,
    )
    fig.update_layout(
        title="Recorded Household Internet Access Type",
        legend_title_text="Internet Access Type",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="Access Type: %{label}<br>Households: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
    )
    return apply_publication_figure_style(fig)


def build_journal_social_participation_bar_figure(raw_df: pd.DataFrame) -> go.Figure | None:
    total_households = int(len(raw_df))
    if total_households == 0:
        return None

    rows: list[dict[str, Any]] = []
    social_columns = (
        ("jumlah_organisasi_kepala", "Household Head Organizational Involvement"),
        ("jumlah_organisasi_anggota", "Household Member Organizational Involvement"),
        ("jumlah_partisipasi_masyarakat_kepala", "Household Head Community Participation"),
        ("jumlah_partisipasi_masyarakat_anggota", "Household Member Community Participation"),
        ("jumlah_partisipasi_kebijakan", "Policy Information Participation"),
    )
    for column, label in social_columns:
        if column not in raw_df.columns:
            continue
        count_series = pd.to_numeric(raw_df[column], errors="coerce").fillna(0)
        rows.append(
            {
                "Social Participation Measure": label,
                "Households": int(count_series.gt(0).sum()),
                "Total Households": total_households,
                "Mean Recorded Activities": float(count_series.mean()),
            }
        )
    plot_df = build_journal_binary_share_df(rows, "Social Participation Measure")
    if plot_df.empty:
        return None
    if "Mean Recorded Activities" not in plot_df.columns:
        plot_df = pd.DataFrame(rows)
        plot_df["Share"] = plot_df["Households"] / plot_df["Total Households"].replace(0, pd.NA)
    plot_df["Share Label"] = plot_df["Share"].map(lambda value: f"{float(value) * 100:.1f}%")

    fig = px.bar(
        plot_df.sort_values("Share", ascending=True, kind="mergesort"),
        x="Share",
        y="Social Participation Measure",
        orientation="h",
        color="Share",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text="Share Label",
        hover_data={"Households": ":,.0f", "Total Households": ":,.0f", "Share": ":.2%"},
    )
    fig.update_layout(
        title="Recorded Social Participation among Households",
        xaxis_title="Share of Households with at Least One Recorded Activity",
        yaxis_title="Social Participation Measure",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_category_share_df(household_df: pd.DataFrame) -> pd.DataFrame:
    counts = (
        household_df["Digital Inclusion Category"]
        .value_counts()
        .reindex(JOURNAL_CATEGORY_ORDER, fill_value=0)
        .rename_axis("Digital Inclusion Category")
        .reset_index(name="Households")
    )
    total = max(int(counts["Households"].sum()), 1)
    counts["Share"] = counts["Households"] / total
    return counts


def build_journal_household_histogram_figure(household_df: pd.DataFrame) -> go.Figure:
    plot_df = household_df.dropna(subset=["iid_rumah_tangga"]).copy()
    fig = px.histogram(
        plot_df,
        x="iid_rumah_tangga",
        color="Digital Inclusion Category",
        category_orders={"Digital Inclusion Category": JOURNAL_CATEGORY_ORDER},
        color_discrete_map=JOURNAL_CATEGORY_COLORS,
        nbins=40,
    )
    fig.update_layout(
        title="Distribution of the Household Digital Inclusion Index",
        xaxis_title="Household Digital Inclusion Index",
        yaxis_title="Number of Households",
        legend_title_text="Digital Inclusion Category",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(range=[0, 1])
    return apply_publication_figure_style(fig, integer_y=True)


def build_journal_category_share_figure(category_df: pd.DataFrame) -> go.Figure:
    plot_df = category_df.copy()
    plot_df["Share Label"] = plot_df["Share"].map(lambda value: f"{float(value) * 100:.1f}%")
    fig = px.bar(
        plot_df,
        x="Digital Inclusion Category",
        y="Share",
        color="Digital Inclusion Category",
        category_orders={"Digital Inclusion Category": JOURNAL_CATEGORY_ORDER},
        color_discrete_map=JOURNAL_CATEGORY_COLORS,
        text="Share Label",
        hover_data={"Households": ":,.0f", "Share": ":.2%"},
    )
    fig.update_layout(
        title="Proportion of Households by Digital Inclusion Category",
        xaxis_title="Digital Inclusion Category",
        yaxis_title="Share of Households",
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_yaxes(tickformat=".0%", range=[0, max(float(plot_df["Share"].max()) * 1.18, 0.05)])
    return apply_publication_figure_style(fig)


def build_journal_household_boxplot_figure(
    household_df: pd.DataFrame,
    selected_villages: list[str],
) -> go.Figure:
    plot_df = add_journal_village_name(household_df)
    plot_df = plot_df.dropna(subset=["iid_rumah_tangga"])
    if selected_villages:
        plot_df = plot_df.loc[plot_df["Village"].isin(selected_villages)].copy()
    median_order = (
        plot_df.groupby("Village")["iid_rumah_tangga"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig = px.box(
        plot_df,
        x="Village",
        y="iid_rumah_tangga",
        category_orders={"Village": median_order},
        points=False,
        color_discrete_sequence=["#2563eb"],
    )
    fig.update_layout(
        title="Household Digital Inclusion Scores by Village",
        xaxis_title="Village",
        yaxis_title="Household Digital Inclusion Index",
        margin=dict(l=20, r=20, t=60, b=80),
        showlegend=False,
    )
    fig.update_xaxes(tickangle=-45, automargin=True)
    fig.update_yaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_vulnerability_summary_df(household_df: pd.DataFrame) -> pd.DataFrame:
    if household_df.empty:
        return pd.DataFrame()
    plot_df = household_df.copy()
    plot_df["_is_vulnerable"] = plot_df["kategori_iid_rt"].astype(str).isin({"sangat rendah", "rendah"})
    group_columns = [column for column in ("kode_deskel", "deskel") if column in plot_df.columns]
    if not group_columns:
        group_columns = ["Digital Inclusion Category"]

    summary_df = (
        plot_df.groupby(group_columns, dropna=False)
        .agg(
            Households=("iid_rumah_tangga", "size"),
            Vulnerable_Households=("_is_vulnerable", "sum"),
            Mean_Household_Index=("iid_rumah_tangga", "mean"),
        )
        .reset_index()
    )
    summary_df["Vulnerable Share"] = summary_df["Vulnerable_Households"] / summary_df["Households"].clip(lower=1)
    summary_df = summary_df.rename(
        columns={
            "Vulnerable_Households": "Vulnerable Households",
            "Mean_Household_Index": "Mean Household Index",
        }
    )

    for column, label in JOURNAL_DIMENSION_LABELS.items():
        if column in plot_df.columns:
            dimension_summary = (
                plot_df.groupby(group_columns, dropna=False)[column]
                .mean()
                .reset_index(name=f"Mean {label}")
            )
            summary_df = summary_df.merge(dimension_summary, on=group_columns, how="left")

    if "deskel" in summary_df.columns:
        summary_df = add_journal_village_name(summary_df)
    else:
        summary_df["Village"] = summary_df[group_columns[0]].astype("string")

    return summary_df.sort_values(
        ["Vulnerable Share", "Vulnerable Households"],
        ascending=[False, False],
        kind="mergesort",
    )


def build_journal_vulnerability_figure(
    vulnerability_df: pd.DataFrame,
    top_n: int = 15,
    offset: int = 0,
) -> go.Figure:
    plot_df = (
        vulnerability_df.sort_values(
            ["Vulnerable Share", "Vulnerable Households"],
            ascending=[False, False],
            kind="mergesort",
        )
        .iloc[offset : offset + top_n]
        .sort_values("Vulnerable Share")
    )
    plot_df["Vulnerable Share Label"] = plot_df["Vulnerable Share"].map(lambda value: f"{float(value) * 100:.1f}%")
    fig = px.bar(
        plot_df,
        x="Vulnerable Share",
        y="Village",
        orientation="h",
        color="Mean Household Index",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text="Vulnerable Share Label",
        hover_data={
            "Households": ":,.0f",
            "Vulnerable Households": ":,.0f",
            "Mean Household Index": ":.3f",
            "Vulnerable Share": ":.2%",
        },
    )
    fig.update_layout(
        title="Villages Ranked by Share of Digitally Vulnerable Households",
        xaxis_title="Share of Digitally Vulnerable Households",
        yaxis_title="Village",
        coloraxis_colorbar_title="Mean Index",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(tickformat=".0%")
    return apply_publication_figure_style(fig)


def build_journal_village_ranking_table(village_df: pd.DataFrame) -> pd.DataFrame:
    ranking_df = village_df.sort_values("iid_desa", ascending=False, kind="mergesort").copy()
    ranking_df["Rank"] = range(1, len(ranking_df) + 1)
    display_columns = [
        "Rank",
        "Village",
        "jumlah_kk",
        "iid_desa",
        "ikd_desa",
        "gini_iid_rumah_tangga",
        "Within-Village Gini Category",
    ]
    display_columns = [column for column in display_columns if column in ranking_df.columns]
    ranking_df = ranking_df[display_columns].rename(
        columns={
            "jumlah_kk": "Households",
            "iid_desa": "Village Digital Inclusion Index",
            "ikd_desa": "Village Digital Deprivation Score",
            "gini_iid_rumah_tangga": "Within-Village Gini",
        }
    )
    return ranking_df


def build_journal_village_index_bar_figure(
    village_df: pd.DataFrame,
    mode: str,
    top_n: int = 15,
    offset: int = 0,
) -> go.Figure:
    if mode == "highest":
        plot_df = (
            village_df.sort_values(["iid_desa", "Village"], ascending=[False, True], kind="mergesort")
            .iloc[offset : offset + top_n]
            .sort_values("iid_desa")
        )
        title = "Village Digital Inclusion Index Ranked from Highest"
        color = "#0f766e"
    else:
        plot_df = (
            village_df.sort_values(["iid_desa", "Village"], ascending=[True, True], kind="mergesort")
            .iloc[offset : offset + top_n]
            .sort_values("iid_desa")
        )
        title = "Village Digital Inclusion Index Ranked from Lowest"
        color = "#b91c1c"

    fig = px.bar(
        plot_df,
        x="iid_desa",
        y="Village",
        orientation="h",
        text_auto=".3f",
        color_discrete_sequence=[color],
        hover_data={"jumlah_kk": ":,.0f", "ikd_desa": ":.3f", "gini_iid_rumah_tangga": ":.3f"},
    )
    fig.update_layout(
        title=title,
        xaxis_title="Village Digital Inclusion Index",
        yaxis_title="Village",
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False,
    )
    fig.update_xaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_village_map_figure(village_df: pd.DataFrame) -> go.Figure | None:
    required_columns = {"village_lat", "village_lon", "iid_desa"}
    if not required_columns.issubset(village_df.columns):
        return None
    plot_df = village_df.dropna(subset=["village_lat", "village_lon", "iid_desa"]).copy()
    if plot_df.empty:
        return None
    plot_df["Village Digital Inclusion Index"] = plot_df["iid_desa"]
    plot_df["Village Digital Deprivation Score"] = plot_df["ikd_desa"] if "ikd_desa" in plot_df.columns else 1 - plot_df["iid_desa"]
    plot_df["Households"] = plot_df["jumlah_kk"] if "jumlah_kk" in plot_df.columns else 1
    fig = px.scatter_mapbox(
        plot_df,
        lat="village_lat",
        lon="village_lon",
        color="Village Digital Inclusion Index",
        size="Households",
        hover_name="Village",
        hover_data={
            "Village Digital Inclusion Index": ":.3f",
            "Village Digital Deprivation Score": ":.3f",
            "Households": ":,.0f",
            "village_lat": False,
            "village_lon": False,
        },
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        zoom=8,
        height=560,
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        title="Spatial Distribution of the Village-Level Digital Inclusion Index",
        margin=dict(l=10, r=10, t=60, b=10),
        coloraxis_colorbar_title="Village Index",
    )
    return apply_publication_figure_style(fig)


def build_journal_dimension_strength_df(village_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column, label in JOURNAL_DIMENSION_LABELS.items():
        if column not in village_df.columns:
            continue
        score = pd.to_numeric(village_df[column], errors="coerce")
        if not score.notna().any():
            continue
        lowest_idx = score.idxmin()
        highest_idx = score.idxmax()
        rows.append(
            {
                "Dimension": label,
                "Mean Score": float(score.mean()),
                "Median Score": float(score.median()),
                "Lowest Village": village_df.loc[lowest_idx, "Village"],
                "Lowest Score": float(score.loc[lowest_idx]),
                "Highest Village": village_df.loc[highest_idx, "Village"],
                "Highest Score": float(score.loc[highest_idx]),
            }
        )
    return pd.DataFrame(rows).sort_values("Mean Score", ascending=False, kind="mergesort")


def build_journal_dimension_bar_figure(strength_df: pd.DataFrame) -> go.Figure:
    plot_df = strength_df.sort_values("Mean Score", ascending=True, kind="mergesort")
    fig = px.bar(
        plot_df,
        x="Mean Score",
        y="Dimension",
        orientation="h",
        color="Mean Score",
        color_continuous_scale=["#b91c1c", "#f59e0b", "#0f766e"],
        text_auto=".3f",
        hover_data={"Median Score": ":.3f", "Lowest Village": True, "Lowest Score": ":.3f"},
    )
    fig.update_layout(
        title="Average Dimensional Profile of Village Digital Inclusion",
        xaxis_title="Mean Score",
        yaxis_title="Dimension",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def build_journal_dimension_radar_figure(
    village_df: pd.DataFrame,
    selected_villages: list[str],
) -> go.Figure:
    dimension_columns = [column for column in JOURNAL_DIMENSION_LABELS if column in village_df.columns]
    theta = [JOURNAL_DIMENSION_LABELS[column] for column in dimension_columns]
    fig = go.Figure()
    for village in selected_villages:
        row = village_df.loc[village_df["Village"].eq(village)].head(1)
        if row.empty:
            continue
        values = [float(pd.to_numeric(row[column], errors="coerce").iloc[0]) for column in dimension_columns]
        fig.add_trace(
            go.Scatterpolar(
                r=[*values, values[0]],
                theta=[*theta, theta[0]],
                fill="toself",
                name=village,
                opacity=0.76,
            )
        )
    fig.update_layout(
        title="Radar Chart of Digital Inclusion Dimensions across Selected Villages",
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickformat=".1f")),
        legend_title_text="Village",
        margin=dict(l=20, r=20, t=70, b=20),
        height=560,
    )
    return apply_publication_figure_style(fig)


def build_journal_dimension_heatmap_figure(
    village_df: pd.DataFrame,
    limit: int = 30,
    offset: int = 0,
) -> go.Figure:
    dimension_columns = [column for column in JOURNAL_DIMENSION_LABELS if column in village_df.columns]
    plot_df = village_df.dropna(subset=dimension_columns, how="all").copy()
    if "iid_desa" in plot_df.columns:
        plot_df = plot_df.sort_values(["iid_desa", "Village"], ascending=[True, True], kind="mergesort")
    else:
        plot_df = plot_df.sort_values("Village", ascending=True, kind="mergesort")
    plot_df = plot_df.iloc[offset : offset + limit]
    z_values = plot_df[dimension_columns].apply(pd.to_numeric, errors="coerce").to_numpy()
    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=[JOURNAL_DIMENSION_LABELS[column] for column in dimension_columns],
            y=plot_df["Village"].tolist(),
            zmin=0,
            zmax=1,
            colorscale=[[0, "#b91c1c"], [0.5, "#f59e0b"], [1, "#0f766e"]],
            colorbar=dict(title="Dimension Score"),
            hovertemplate="Village: %{y}<br>Dimension: %{x}<br>Score: %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Heatmap of Village Digital Inclusion Dimensions",
        xaxis_title="Dimension",
        yaxis_title="Village",
        margin=dict(l=20, r=20, t=60, b=20),
        height=max(460, 28 * max(len(plot_df), 1) + 150),
    )
    fig.update_xaxes(side="top")
    fig.update_yaxes(automargin=True)
    return apply_publication_figure_style(fig)


def build_journal_lagging_dimension_table(village_df: pd.DataFrame, bottom_n: int = 3) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column, label in JOURNAL_DIMENSION_LABELS.items():
        if column not in village_df.columns:
            continue
        dimension_df = village_df.dropna(subset=[column]).nsmallest(bottom_n, column).copy()
        for rank, (_, row) in enumerate(dimension_df.iterrows(), start=1):
            rows.append(
                {
                    "Dimension": label,
                    "Lag Rank": rank,
                    "Village": row["Village"],
                    "Dimension Score": row[column],
                    "Village Digital Inclusion Index": row.get("iid_desa", pd.NA),
                }
            )
    return pd.DataFrame(rows)


def build_journal_deprivation_scatter_figure(village_df: pd.DataFrame) -> go.Figure:
    plot_df = village_df.dropna(subset=["iid_desa", "gini_iid_rumah_tangga"]).copy()
    if "ikd_desa" not in plot_df.columns:
        plot_df["ikd_desa"] = 1 - plot_df["iid_desa"]
    plot_df["Village Digital Inclusion Index"] = plot_df["iid_desa"]
    plot_df["Village Digital Deprivation Score"] = plot_df["ikd_desa"]
    plot_df["Within-Village Gini"] = plot_df["gini_iid_rumah_tangga"]
    plot_df["Households"] = plot_df["jumlah_kk"] if "jumlah_kk" in plot_df.columns else 1
    fig = px.scatter(
        plot_df,
        x="Village Digital Inclusion Index",
        y="Within-Village Gini",
        size="Households",
        color="Village Digital Deprivation Score",
        hover_name="Village",
        hover_data={
            "Village Digital Inclusion Index": ":.3f",
            "Village Digital Deprivation Score": ":.3f",
            "Within-Village Gini": ":.3f",
            "Households": ":,.0f",
        },
        color_continuous_scale=["#0f766e", "#f59e0b", "#b91c1c"],
    )
    mean_index = float(plot_df["Village Digital Inclusion Index"].mean())
    mean_gini = float(plot_df["Within-Village Gini"].mean())
    fig.add_vline(
        x=mean_index,
        line_dash="dash",
        line_color="#475569",
        annotation_text="Mean Village Index",
        annotation_position="top left",
    )
    fig.add_hline(
        y=mean_gini,
        line_dash="dash",
        line_color="#475569",
        annotation_text="Mean Within-Village Gini",
        annotation_position="bottom right",
    )
    fig.update_layout(
        title="Village Mean Index and Within-Village Inequality",
        xaxis_title="Village Digital Inclusion Index",
        yaxis_title="Within-Village Gini of Household Scores",
        coloraxis_colorbar_title="Deprivation Score",
        margin=dict(l=20, r=20, t=70, b=20),
    )
    return apply_publication_figure_style(fig)


def build_journal_deprivation_bar_figure(
    village_df: pd.DataFrame,
    top_n: int = 15,
    offset: int = 0,
) -> go.Figure:
    plot_df = village_df.copy()
    if "ikd_desa" not in plot_df.columns:
        plot_df["ikd_desa"] = 1 - plot_df["iid_desa"]
    plot_df = (
        plot_df.sort_values(["ikd_desa", "gini_iid_rumah_tangga"], ascending=[False, False], kind="mergesort")
        .iloc[offset : offset + top_n]
        .sort_values("ikd_desa")
    )
    fig = px.bar(
        plot_df,
        x="ikd_desa",
        y="Village",
        orientation="h",
        color="gini_iid_rumah_tangga",
        color_continuous_scale=["#0f766e", "#f59e0b", "#b91c1c"],
        text_auto=".3f",
        hover_data={"iid_desa": ":.3f", "gini_iid_rumah_tangga": ":.3f", "jumlah_kk": ":,.0f"},
    )
    fig.update_layout(
        title="Highest Village Digital Deprivation Scores",
        xaxis_title="Village Digital Deprivation Score",
        yaxis_title="Village",
        coloraxis_colorbar_title="Within-Village Gini",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(range=[0, max(float(plot_df["ikd_desa"].max()) * 1.15, 0.05)])
    return apply_publication_figure_style(fig)


def build_journal_deprivation_priority_table(village_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    priority_df = village_df.copy()
    if "ikd_desa" not in priority_df.columns:
        priority_df["ikd_desa"] = 1 - priority_df["iid_desa"]
    high_gini_threshold = priority_df["gini_iid_rumah_tangga"].quantile(0.67)
    high_gini_mask = priority_df["gini_iid_rumah_tangga"].ge(high_gini_threshold)
    if "Within-Village Gini Category" in priority_df.columns:
        high_gini_mask = high_gini_mask | priority_df["Within-Village Gini Category"].astype(str).str.lower().eq("high")
    moderate_high_inequality_df = priority_df.loc[
        priority_df["iid_desa"].between(0.4, 0.6, inclusive="both") & high_gini_mask
    ].copy()
    priority_df = priority_df.sort_values(
        ["ikd_desa", "gini_iid_rumah_tangga"],
        ascending=[False, False],
        kind="mergesort",
    )

    display_columns = [
        "Village",
        "jumlah_kk",
        "iid_desa",
        "ikd_desa",
        "gini_iid_rumah_tangga",
        "Within-Village Gini Category",
    ]
    display_columns = [column for column in display_columns if column in priority_df.columns]
    renamed_columns = {
        "jumlah_kk": "Households",
        "iid_desa": "Village Digital Inclusion Index",
        "ikd_desa": "Village Digital Deprivation Score",
        "gini_iid_rumah_tangga": "Within-Village Gini",
    }
    priority_display_df = priority_df[display_columns].rename(columns=renamed_columns)
    moderate_display_df = moderate_high_inequality_df[display_columns].rename(columns=renamed_columns)
    return priority_display_df, moderate_display_df


def render_hero(meta: dict[str, Any]) -> None:
    badges = [
        f"Source: {meta.get('source_label', '-')}",
        f"Output Folder: {Path(meta.get('output_dir', '-')).name}",
    ]
    if meta.get("scheme"):
        badges.append(f"Scheme: {translate_display_text(meta['scheme'])}")
    if meta.get("input_path"):
        badges.append(f"Input: {Path(meta['input_path']).name}")

    badge_html = "".join(f"<span class='hero-badge'>{item}</span>" for item in badges)
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-kicker">Research Dashboard</div>
            <h1 class="hero-title">Household and Village Digital Inclusion Analysis</h1>
            <div class="hero-subtitle">
                This dashboard presents the processed outputs from the <code>id.py</code> pipeline through
                publication-oriented charts, score profiles, variable documentation, and table summaries.
            </div>
            <div class="hero-badges">{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_summary_metrics(tables: dict[str, pd.DataFrame]) -> None:
    keluarga_df = tables.get("data_keluarga", pd.DataFrame())
    desa_df = tables.get("indeks_desa", pd.DataFrame())
    excluded_df = tables.get("rumah_tangga_dikeluarkan", pd.DataFrame())
    warga_df = tables.get("sebaran_warga_iid_rt", pd.DataFrame())
    inequality_summary_df, _ = resolve_inequality_tables(tables)

    household_df = get_household_rows(keluarga_df)
    total_warga = int(len(keluarga_df))
    if not warga_df.empty and "total_warga" in warga_df.columns:
        total_warga = int(pd.to_numeric(warga_df["total_warga"], errors="coerce").max())

    total_valid = int(len(household_df))
    total_excluded = 0
    if not excluded_df.empty and "family_id" in excluded_df.columns:
        total_excluded = int(excluded_df["family_id"].astype("string").nunique(dropna=True))
    total_desa = int(len(desa_df))
    avg_iid = pd.to_numeric(desa_df.get("iid_desa"), errors="coerce").mean() if not desa_df.empty else None
    overall_row = inequality_summary_df.loc[
        inequality_summary_df["cakupan_analisis"].astype("string").eq("keseluruhan")
    ].head(1)
    overall_gini = overall_row["gini_iid_rumah_tangga"].iloc[0] if not overall_row.empty else None
    overall_category = format_gini_label(overall_row["interpretasi_gini"].iloc[0]) if not overall_row.empty else "-"

    metric_cols = st.columns(5)
    metric_cols[0].metric("Valid Households", format_number(total_valid, 0))
    metric_cols[1].metric("Excluded Households", format_number(total_excluded, 0))
    metric_cols[2].metric("Villages", format_number(total_desa, 0))
    metric_cols[3].metric("Mean Village Index", format_number(avg_iid))
    metric_cols[4].metric("Overall Gini", format_number(overall_gini))

    extra_cols = st.columns(3)
    extra_cols[0].metric("Residents", format_number(total_warga, 0))
    if not household_df.empty and "kategori_iid_rt" in household_df.columns:
        top_category = household_df["kategori_iid_rt"].astype("string").value_counts(dropna=True)
        dominant_category = format_iid_category_label(top_category.index[0]) if not top_category.empty else "-"
        extra_cols[1].metric("Dominant Household Category", dominant_category)
    else:
        extra_cols[1].metric("Dominant Household Category", "-")
    extra_cols[2].metric("Relative Gini Category", str(overall_category) if pd.notna(overall_category) else "-")


def build_household_resource_summary(detail_df: pd.DataFrame) -> dict[str, float]:
    hp_series = pd.to_numeric(detail_df.get("hp_jumlah_num"), errors="coerce")
    member_series = pd.to_numeric(detail_df.get("jml_keluarga"), errors="coerce")
    comm_series = pd.to_numeric(detail_df.get("rp_komunikasi_tertinggi"), errors="coerce")
    return {
        "avg_hp": float(hp_series.mean()) if hp_series.notna().any() else float("nan"),
        "avg_members": float(member_series.mean()) if member_series.notna().any() else float("nan"),
        "avg_comm": float(comm_series.mean()) if comm_series.notna().any() else float("nan"),
        "median_comm": float(comm_series.median()) if comm_series.notna().any() else float("nan"),
    }


def build_category_count_figure(household_df: pd.DataFrame) -> go.Figure:
    plot_df = exclude_unscored_iid_category(household_df)
    category_counts = (
        plot_df["kategori_iid_rt"]
        .astype("string")
        .value_counts()
        .reindex(VISIBLE_CATEGORY_ORDER, fill_value=0)
        .reset_index()
    )
    category_counts.columns = ["kategori_iid_rt", "jumlah_rt"]
    category_counts["Digital Inclusion Category"] = category_counts["kategori_iid_rt"].map(format_iid_category_label)
    fig = px.bar(
        category_counts,
        x="Digital Inclusion Category",
        y="jumlah_rt",
        color="Digital Inclusion Category",
        color_discrete_map=IID_CATEGORY_COLORS,
        category_orders={"Digital Inclusion Category": IID_CATEGORY_ORDER_EN},
        text_auto=True,
        labels={"jumlah_rt": "Households"},
    )
    fig.update_layout(
        title="Valid Households by Digital Inclusion Category",
        xaxis_title="Digital Inclusion Category",
        yaxis_title="Number of Households",
        showlegend=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    apply_bar_value_text_format(fig, "y")
    return apply_publication_figure_style(fig, integer_y=True)


def build_household_histogram_figure(household_df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        household_df,
        x="iid_rumah_tangga",
        nbins=30,
        color_discrete_sequence=["#0f766e"],
    )
    fig.update_layout(
        title="Distribution of Household Digital Inclusion Scores",
        xaxis_title="Household Digital Inclusion Index",
        yaxis_title="Number of Households",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return apply_publication_figure_style(fig, integer_y=True)


def build_household_average_figure(detail_df: pd.DataFrame) -> go.Figure:
    summary = build_household_resource_summary(detail_df)
    plot_df = pd.DataFrame(
        [
            {"metrik": "Mean Mobile Phones", "nilai": summary["avg_hp"], "warna": "#0f766e"},
            {"metrik": "Mean Household Members", "nilai": summary["avg_members"], "warna": "#163249"},
        ]
    )
    fig = px.bar(
        plot_df,
        x="metrik",
        y="nilai",
        color="metrik",
        color_discrete_sequence=plot_df["warna"].tolist(),
        text_auto=".2f",
    )
    fig.update_layout(
        title="Mean Mobile Phones and Household Members",
        xaxis_title="Metric",
        yaxis_title="Mean Value",
        showlegend=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return apply_publication_figure_style(fig)


def build_comm_cost_distribution_figure(detail_df: pd.DataFrame) -> go.Figure:
    plot_df = detail_df.copy()
    plot_df["rp_komunikasi_tertinggi"] = pd.to_numeric(plot_df["rp_komunikasi_tertinggi"], errors="coerce")
    plot_df = plot_df.dropna(subset=["rp_komunikasi_tertinggi"])
    fig = px.histogram(
        plot_df,
        x="rp_komunikasi_tertinggi",
        nbins=40,
        color_discrete_sequence=["#ea580c"],
    )
    fig.update_layout(
        title="Distribution of Household Communication Expenditure",
        xaxis_title="Highest Household Communication Expenditure (IDR)",
        yaxis_title="Number of Households",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(tickformat=",.0f")
    return apply_publication_figure_style(fig, integer_x=True, integer_y=True)


def build_household_resource_by_desa_figure(detail_df: pd.DataFrame, metric: str, top_n: int = 12) -> go.Figure:
    label_map = {
        "hp_jumlah_num": ("Mean Mobile Phones by Village", "Mean Mobile Phones", "#0f766e"),
        "jml_keluarga": ("Mean Household Members by Village", "Mean Household Members", "#163249"),
        "rp_komunikasi_tertinggi": ("Mean Communication Expenditure by Village", "Mean Communication Expenditure (IDR)", "#ea580c"),
    }
    title, xaxis_title, color = label_map[metric]
    plot_df = detail_df[["deskel", metric]].copy()
    plot_df[metric] = pd.to_numeric(plot_df[metric], errors="coerce")
    plot_df = plot_df.dropna(subset=[metric])
    plot_df = plot_df.groupby("deskel", dropna=False)[metric].mean().reset_index()
    plot_df = plot_df.nlargest(top_n, metric).sort_values(metric)
    fig = px.bar(
        plot_df,
        x=metric,
        y="deskel",
        orientation="h",
        text_auto=".2f" if metric != "rp_komunikasi_tertinggi" else ".0f",
        color_discrete_sequence=[color],
    )
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title="Village",
        showlegend=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    if metric == "rp_komunikasi_tertinggi":
        fig.update_xaxes(tickformat=",.0f")
        apply_bar_value_text_format(fig, "x")
        return apply_publication_figure_style(fig, integer_x=True)
    return apply_publication_figure_style(fig)


def build_person_distribution_figure(warga_df: pd.DataFrame) -> go.Figure:
    distribution = exclude_unscored_iid_category(warga_df)
    distribution["jumlah_warga"] = pd.to_numeric(distribution["jumlah_warga"], errors="coerce")
    distribution = (
        distribution.groupby("kategori_iid_rt", dropna=False, as_index=False)["jumlah_warga"].sum()
        .set_index("kategori_iid_rt")
        .reindex(VISIBLE_CATEGORY_ORDER, fill_value=0)
        .reset_index()
    )
    distribution["Digital Inclusion Category"] = distribution["kategori_iid_rt"].map(format_iid_category_label)
    fig = px.pie(
        distribution,
        values="jumlah_warga",
        names="Digital Inclusion Category",
        color="Digital Inclusion Category",
        color_discrete_map=IID_CATEGORY_COLORS,
        hole=0.45,
    )
    fig.update_layout(
        title="Resident Composition by Household Digital Inclusion Category",
        legend_title_text="Digital Inclusion Category",
        margin=dict(l=10, r=10, t=55, b=10),
    )
    fig.update_traces(
        hovertemplate=(
            "Digital Inclusion Category: %{label}<br>"
            "Residents: %{value:,.0f}<br>"
            "Share: %{percent}<extra></extra>"
        )
    )
    return apply_publication_figure_style(fig)


def build_top_bottom_desa_figure(desa_df: pd.DataFrame, mode: str) -> go.Figure:
    if mode == "top":
        chart_df = desa_df.nlargest(10, "iid_desa").sort_values("iid_desa")
        title = "Ten Villages with the Highest Digital Inclusion Index"
        color = "#0f766e"
    else:
        chart_df = desa_df.nsmallest(10, "iid_desa").sort_values("iid_desa")
        title = "Ten Villages with the Lowest Digital Inclusion Index"
        color = "#b91c1c"

    fig = px.bar(
        chart_df,
        x="iid_desa",
        y="deskel",
        orientation="h",
        text_auto=".3f",
        color_discrete_sequence=[color],
    )
    fig.update_layout(
        title=title,
        xaxis_title="Village Digital Inclusion Index",
        yaxis_title="Village",
        margin=dict(l=20, r=20, t=55, b=20),
        showlegend=False,
    )
    return apply_publication_figure_style(fig)


def build_dimension_profile_figure(desa_df: pd.DataFrame) -> go.Figure:
    rows: list[dict[str, Any]] = []
    for column, label in DIMENSION_LABELS.items():
        if column in desa_df.columns:
            rows.append({"Dimension": label, "Mean Score": pd.to_numeric(desa_df[column], errors="coerce").mean()})
    profile_df = pd.DataFrame(rows)
    fig = px.bar(
        profile_df,
        x="Dimension",
        y="Mean Score",
        color="Mean Score",
        color_continuous_scale=["#d8f3eb", "#0f766e", "#163249"],
        text_auto=".3f",
    )
    fig.update_layout(
        title="Mean Village-Level Dimension Scores",
        xaxis_title="Dimension",
        yaxis_title="Mean Score",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_yaxes(range=[0, 1])
    return apply_publication_figure_style(fig)


def build_gini_scatter_figure(desa_df: pd.DataFrame) -> go.Figure:
    plot_df = desa_df.copy()
    plot_df["Relative Gini Category"] = plot_df["interpretasi_gini"].map(format_gini_label)
    fig = px.scatter(
        plot_df,
        x="iid_desa",
        y="gini_iid_rumah_tangga",
        size="jumlah_kk",
        hover_name="deskel",
        color="Relative Gini Category",
        color_discrete_map=GINI_COLORS,
        hover_data={
            "jumlah_kk": ":,.0f",
            "iid_desa": ":.3f",
            "gini_iid_rumah_tangga": ":.3f",
        },
        labels={
            "iid_desa": "Village Digital Inclusion Index",
            "gini_iid_rumah_tangga": "Within-Village Gini",
            "jumlah_kk": "Households",
            "deskel": "Village",
        },
    )
    fig.update_layout(
        title="Village Digital Inclusion and Within-Village Gini by Relative Tertile",
        xaxis_title="Village Digital Inclusion Index",
        yaxis_title="Within-Village Gini of Household Scores",
        legend_title_text="Relative Gini Category",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return apply_publication_figure_style(fig)


def add_ikd_tertile_columns(desa_df: pd.DataFrame) -> pd.DataFrame:
    enriched_df = desa_df.copy()
    enriched_df = enriched_df.drop(columns=["ikd_kuartil", "kategori_kuartil"], errors="ignore")
    enriched_df["ikd_desa"] = pd.to_numeric(enriched_df["ikd_desa"], errors="coerce")
    valid_count = int(enriched_df["ikd_desa"].notna().sum())
    if valid_count < 3:
        enriched_df["ikd_tertil"] = pd.NA
        enriched_df["kategori_tertil"] = pd.NA
        return enriched_df

    ranked_values = enriched_df["ikd_desa"].rank(method="first")
    tertile_series = pd.qcut(ranked_values, q=3, labels=IKD_TERTILE_ORDER)
    enriched_df["ikd_tertil"] = tertile_series.astype("string")
    enriched_df["kategori_tertil"] = enriched_df["ikd_tertil"].map(IKD_TERTILE_TO_RELATIVE)
    return enriched_df


def build_ikd_tertile_distribution_figure(desa_df: pd.DataFrame) -> go.Figure:
    plot_df = (
        desa_df["kategori_tertil"]
        .astype("string")
        .value_counts(dropna=False)
        .reindex(IKD_RELATIVE_ORDER, fill_value=0)
        .rename_axis("Relative Digital Deprivation Class")
        .reset_index(name="Villages")
    )
    plot_df["Tertile Range"] = plot_df["Relative Digital Deprivation Class"].map(IKD_RELATIVE_RANGE_LABELS)
    plot_df["Village Share"] = plot_df["Villages"] / max(int(plot_df["Villages"].sum()), 1)
    fig = px.bar(
        plot_df,
        x="Relative Digital Deprivation Class",
        y="Villages",
        color="Relative Digital Deprivation Class",
        color_discrete_map=IKD_RELATIVE_COLORS,
        category_orders={"Relative Digital Deprivation Class": IKD_RELATIVE_ORDER},
        text_auto=True,
        hover_data={"Tertile Range": True, "Village Share": ":.2%"},
    )
    fig.update_layout(
        title="Villages by Relative Digital Deprivation Tertile",
        xaxis_title="Relative Digital Deprivation Class",
        yaxis_title="Number of Villages",
        showlegend=False,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    apply_bar_value_text_format(fig, "y")
    return apply_publication_figure_style(fig, integer_y=True)


def build_ikd_tertile_scatter_figure(desa_df: pd.DataFrame) -> go.Figure:
    plot_df = desa_df.sort_values("ikd_desa").reset_index(drop=True).copy()
    plot_df["Village Order"] = plot_df.index + 1
    fig = px.scatter(
        plot_df,
        x="Village Order",
        y="ikd_desa",
        color="kategori_tertil",
        color_discrete_map=IKD_RELATIVE_COLORS,
        category_orders={"kategori_tertil": IKD_RELATIVE_ORDER},
        hover_name="deskel",
        hover_data={"ikd_tertil": True, "kategori_tertil": True, "jumlah_kk": ":,.0f", "Village Order": False},
        labels={
            "ikd_desa": "Village Digital Deprivation Score",
            "ikd_tertil": "Digital Deprivation Tertile",
            "kategori_tertil": "Relative Digital Deprivation Class",
            "jumlah_kk": "Households",
            "deskel": "Village",
        },
    )
    fig.update_traces(marker=dict(size=9, opacity=0.82))
    fig.update_layout(
        title="Village Digital Deprivation Scores by Relative Tertile",
        xaxis_title="Village Order after Sorting from Lowest Digital Deprivation",
        yaxis_title="Village Digital Deprivation Score",
        legend_title_text="Relative Digital Deprivation Class",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return apply_publication_figure_style(fig, integer_x=True)


def prepare_desa_distribution_matrix(
    distribution_df: pd.DataFrame,
    desa_df: pd.DataFrame,
    sort_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    plot_df = exclude_unscored_iid_category(distribution_df)
    if plot_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    for column in ("jumlah_kk", "persentase_kk", "total_kk_desa"):
        if column in plot_df.columns:
            plot_df[column] = pd.to_numeric(plot_df[column], errors="coerce")
    plot_df = add_desa_label(plot_df)

    meta_columns = [column for column in ("label_desa", "kode_deskel", "deskel", "total_kk_desa") if column in plot_df.columns]
    meta_df = plot_df[meta_columns].drop_duplicates(subset=["label_desa"]).copy()

    if not desa_df.empty and "iid_desa" in desa_df.columns:
        desa_meta_columns = [column for column in ("kode_deskel", "deskel", "iid_desa") if column in desa_df.columns]
        desa_meta = add_desa_label(desa_df[desa_meta_columns].drop_duplicates().copy())
        desa_meta["iid_desa"] = pd.to_numeric(desa_meta["iid_desa"], errors="coerce")
        meta_df = meta_df.merge(
            desa_meta[["label_desa", "iid_desa"]].drop_duplicates(subset=["label_desa"]),
            on="label_desa",
            how="left",
        )
    else:
        meta_df["iid_desa"] = pd.NA

    if sort_mode == "iid_desc":
        meta_df = meta_df.sort_values(["iid_desa", "label_desa"], ascending=[False, True], na_position="last")
    elif sort_mode == "kk_desc":
        meta_df = meta_df.sort_values(["total_kk_desa", "label_desa"], ascending=[False, True], na_position="last")
    else:
        meta_df = meta_df.sort_values("label_desa", ascending=True)

    pivot_df = plot_df.pivot_table(
        index="label_desa",
        columns="kategori_iid_rt",
        values="persentase_kk",
        aggfunc="sum",
    ).fillna(0.0)
    category_columns = [category for category in VISIBLE_CATEGORY_ORDER if category in pivot_df.columns]
    ordered_labels = meta_df["label_desa"].tolist()
    pivot_df = pivot_df.reindex(index=ordered_labels, columns=category_columns, fill_value=0.0)
    meta_df = meta_df.set_index("label_desa").reindex(ordered_labels).reset_index()
    return pivot_df, meta_df


def build_desa_distribution_heatmap(pivot_df: pd.DataFrame) -> go.Figure:
    heatmap_df = (pivot_df * 100).round(2)
    heatmap_df = heatmap_df.rename(columns={category: format_iid_category_label(category) for category in heatmap_df.columns})
    max_value = float(heatmap_df.max().max()) if not heatmap_df.empty else 0.0
    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_df.to_numpy(),
            x=heatmap_df.columns.tolist(),
            y=heatmap_df.index.tolist(),
            colorscale=RED_HEATMAP_SCALE,
            zmin=0,
            zmax=max(max_value, 1.0),
            colorbar=dict(title="% Households"),
            hovertemplate="Village: %{y}<br>Category: %{x}<br>Share: %{z:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Heatmap of Household Digital Inclusion Categories across Villages",
        xaxis_title="Household Digital Inclusion Category",
        yaxis_title="Village",
        margin=dict(l=20, r=20, t=55, b=20),
        height=max(460, 34 * max(len(heatmap_df.index), 1) + 120),
    )
    fig.update_xaxes(side="top")
    fig.update_yaxes(automargin=True)
    return apply_publication_figure_style(fig)


def build_desa_distribution_focus_figure(distribution_df: pd.DataFrame, selected_label: str) -> go.Figure:
    plot_df = exclude_unscored_iid_category(distribution_df)
    plot_df = add_desa_label(plot_df)
    plot_df["jumlah_kk"] = pd.to_numeric(plot_df["jumlah_kk"], errors="coerce")
    plot_df["persentase_kk"] = pd.to_numeric(plot_df["persentase_kk"], errors="coerce")
    focus_df = plot_df.loc[plot_df["label_desa"].astype("string").eq(str(selected_label))].copy()
    focus_df = (
        focus_df.groupby("kategori_iid_rt", as_index=False)[["jumlah_kk", "persentase_kk"]]
        .sum()
        .set_index("kategori_iid_rt")
        .reindex(VISIBLE_CATEGORY_ORDER, fill_value=0.0)
        .reset_index()
    )
    focus_df["persentase_rt"] = focus_df["persentase_kk"] * 100
    focus_df["Digital Inclusion Category"] = focus_df["kategori_iid_rt"].map(format_iid_category_label)
    fig = px.bar(
        focus_df,
        x="Digital Inclusion Category",
        y="persentase_rt",
        color="Digital Inclusion Category",
        color_discrete_map=IID_CATEGORY_COLORS,
        category_orders={"Digital Inclusion Category": IID_CATEGORY_ORDER_EN},
        text_auto=".2f",
        hover_data={"jumlah_kk": ":,.0f", "persentase_rt": ":.2f"},
        labels={"jumlah_kk": "Households", "persentase_rt": "Household Share"},
    )
    fig.update_layout(
        title=f"Household Digital Inclusion Category Composition in {selected_label}",
        xaxis_title="Household Digital Inclusion Category",
        yaxis_title="Share of Households",
        margin=dict(l=20, r=20, t=55, b=20),
        showlegend=False,
    )
    fig.update_yaxes(ticksuffix="%")
    apply_bar_value_text_format(fig, "y", digits=2, suffix="%")
    return apply_publication_figure_style(fig)


def build_map_figure(household_df: pd.DataFrame) -> go.Figure | None:
    lat_col, lon_col = get_coordinate_columns(household_df)
    if not lat_col or not lon_col:
        return None

    map_df = exclude_unscored_iid_category(household_df)
    map_df[lat_col] = pd.to_numeric(map_df[lat_col], errors="coerce")
    map_df[lon_col] = pd.to_numeric(map_df[lon_col], errors="coerce")
    map_df = map_df.dropna(subset=[lat_col, lon_col, "iid_rumah_tangga"])
    if map_df.empty:
        return None

    sample_size = min(2500, len(map_df))
    map_df = map_df.sample(sample_size, random_state=42) if len(map_df) > sample_size else map_df
    if "kategori_iid_rt" in map_df.columns:
        map_df["Digital Inclusion Category"] = map_df["kategori_iid_rt"].map(format_iid_category_label)
    fig = px.scatter_mapbox(
        map_df,
        lat=lat_col,
        lon=lon_col,
        color="Digital Inclusion Category" if "Digital Inclusion Category" in map_df.columns else None,
        color_discrete_map=IID_CATEGORY_COLORS,
        hover_name="deskel" if "deskel" in map_df.columns else None,
        hover_data={"iid_rumah_tangga": ":.3f"},
        labels={"iid_rumah_tangga": "Household Digital Inclusion Index", "deskel": "Village"},
        zoom=8,
        height=520,
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        title="Spatial Distribution of Valid Households",
        margin=dict(l=10, r=10, t=55, b=10),
        legend_title_text="Digital Inclusion Category",
    )
    return apply_publication_figure_style(fig)


def build_table_overview(df: pd.DataFrame) -> pd.DataFrame:
    total_cells = int(df.shape[0] * df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    numeric_count = int(len(df.select_dtypes(include="number").columns))
    text_count = int(len(df.columns) - numeric_count)
    overview_rows = [
        {"Metric": "Rows", "Value": format_number(int(df.shape[0]), 0)},
        {"Metric": "Columns", "Value": format_number(int(df.shape[1]), 0)},
        {"Metric": "Numeric Columns", "Value": format_number(numeric_count, 0)},
        {"Metric": "Non-Numeric Columns", "Value": format_number(text_count, 0)},
        {"Metric": "Missing Cells", "Value": format_number(missing_cells, 0)},
        {"Metric": "Missing Cell Share", "Value": format_percent(missing_cells / total_cells if total_cells else 0)},
    ]
    return pd.DataFrame(overview_rows)


def build_column_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_rows = max(len(df), 1)
    for column in df.columns:
        series = df[column]
        preview_values = [str(value) for value in series.dropna().astype(str).head(3).tolist()]
        rows.append(
            {
                "Column": DISPLAY_COLUMN_LABELS.get(column, column),
                "Data Type": str(series.dtype),
                "Filled Values": int(series.notna().sum()),
                "Missing Values": int(series.isna().sum()),
                "Missing Share": format_percent(series.isna().sum() / total_rows),
                "Unique Values": int(series.nunique(dropna=True)),
                "Sample Values": ", ".join(preview_values) if preview_values else "-",
            }
        )
    return pd.DataFrame(rows)


def render_column_detail(df: pd.DataFrame, column_name: str) -> None:
    series = df[column_name]
    detail_cols = st.columns(4)
    detail_cols[0].metric("Data Type", str(series.dtype))
    detail_cols[1].metric("Filled Values", format_number(int(series.notna().sum()), 0))
    detail_cols[2].metric("Unique Values", format_number(int(series.nunique(dropna=True)), 0))
    detail_cols[3].metric("Missing Values", format_number(int(series.isna().sum()), 0))

    if pd.api.types.is_numeric_dtype(series):
        stats_df = series.describe(percentiles=[0.25, 0.5, 0.75]).rename("Value").reset_index()
        stats_df.columns = ["Statistic", "Value"]
        st.dataframe(stats_df, width="stretch", hide_index=True)
    else:
        top_values = series.fillna("NA").astype(str).value_counts().head(10).reset_index()
        top_values.columns = ["Value", "Frequency"]
        top_values["Value"] = top_values["Value"].map(lambda value: translate_display_text(value, column_name))
        st.dataframe(top_values, width="stretch", hide_index=True)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def excel_bytes_from_sheets(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    prepared_sheets = {
        sheet_name[:31]: iid_pipeline.round_numeric_dataframe(df.copy())
        for sheet_name, df in sheets.items()
    }
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in prepared_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        iid_pipeline.apply_excel_number_formats(writer.book, prepared_sheets)
    buffer.seek(0)
    return buffer.getvalue()


def collect_advanced_analysis_tables_for_download(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    ordered_keys = (
        "analisis_determinasi_dimensi",
        "analisis_determinasi_variabel",
        "analisis_sensitivitas_oat",
        "analisis_shapley_variabel",
    )
    collected: dict[str, pd.DataFrame] = {}
    for key in ordered_keys:
        df = tables.get(key, pd.DataFrame()).copy()
        if not df.empty:
            collected[key] = df
    return collected


def render_sidebar() -> None:
    ensure_request_state()
    default_output_dir = detect_default_output_dir()

    logo_path = BASE_DIR / "assets" / "logo-banner2.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width=150)
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-kicker">Research Dashboard</div>
            <div class="sidebar-title">Digital Inclusion and Inequality</div>
            <div class="sidebar-subtitle">
                Load processed index outputs or re-run the pipeline from source data.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown('<div class="sidebar-section-label">Data Source</div>', unsafe_allow_html=True)
    with st.sidebar.form("dashboard_loader_form"):
        source_mode = st.radio(
            "Select data-loading mode",
            options=("Prepared Output Folder", "Process Source Data"),
            index=0 if st.session_state.dashboard_request.get("mode") == "folder_hasil" else 1,
            label_visibility="collapsed",
        )

        if source_mode == "Prepared Output Folder":
            st.markdown(
                '<div class="sidebar-help">Use this mode when processed CSV outputs are already available. It is the fastest way to open the dashboard.</div>',
                unsafe_allow_html=True,
            )
            output_dir = st.text_input(
                "Processed Output Folder",
                value=st.session_state.dashboard_request.get("output_dir", str(default_output_dir)),
                help="Folder containing output files such as indeks_desa.csv and data_keluarga.csv.",
            )
            submit = st.form_submit_button("Display Dashboard")
            if submit:
                st.session_state.dashboard_request = {
                    "mode": "folder_hasil",
                    "output_dir": output_dir,
                }
        else:
            st.markdown(
                '<div class="sidebar-help">Upload source data to recalculate the index. Technical options are kept in the advanced section to keep the sidebar concise.</div>',
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader("Upload CSV/XLSX/Parquet File", type=["csv", "xlsx", "xls", "parquet"])
            input_path = st.text_input(
                "Local File Path",
                value=str(detect_default_input_path() or BASE_DIR / "data_asli.parquet"),
                help="Used when no file is uploaded.",
            )
            scheme = st.selectbox(
                "Calculation Scheme",
                options=["rekomendasi", "baseline"],
                index=0,
                format_func=lambda value: str(translate_display_text(value)),
            )
            with st.expander("Calculation Options", expanded=False):
                school_age_min = st.number_input("Minimum School Age", min_value=0, max_value=100, value=7, step=1)
                school_age_max = st.number_input("Maximum School Age", min_value=0, max_value=100, value=25, step=1)
                missing_threshold = st.slider("Core Indicator Missingness Threshold", min_value=0.0, max_value=1.0, value=0.20, step=0.01)
            submit = st.form_submit_button("Process and Display")
            if submit:
                source_path = save_uploaded_file(uploaded_file) if uploaded_file is not None else Path(input_path)
                st.session_state.dashboard_request = {
                    "mode": "olah_ulang",
                    "input_path": str(source_path),
                    "scheme": scheme,
                    "school_age_min": int(school_age_min),
                    "school_age_max": int(school_age_max),
                    "missing_threshold": float(missing_threshold),
                }

    active_request = st.session_state.dashboard_request
    if active_request["mode"] == "folder_hasil":
        active_detail = Path(active_request["output_dir"]).name or str(active_request["output_dir"])
        active_label = "Prepared Output Folder"
    else:
        active_detail = Path(active_request["input_path"]).name
        active_label = f"Reprocessed Source Data - {translate_display_text(active_request.get('scheme', 'rekomendasi'))}"
    st.sidebar.markdown(
        f"""
        <div class="sidebar-status">
            <b>Active Mode</b><br>
            {active_label}<br>
            <span>{active_detail}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def resolve_bundle_from_request() -> dict[str, Any]:
    request = st.session_state.dashboard_request
    if request["mode"] == "folder_hasil":
        output_dir = Path(request["output_dir"])
        return load_output_bundle(output_dir)

    input_path = Path(request["input_path"])
    return process_input_bundle(
        input_path=input_path,
        scheme=request["scheme"],
        school_age_min=request["school_age_min"],
        school_age_max=request["school_age_max"],
        missing_threshold=request["missing_threshold"],
    )


def render_household_resource_section(detail_df: pd.DataFrame, section_key: str) -> None:
    if detail_df.empty:
        st.info("Mobile phone, household-size, and communication-expenditure statistics cannot be computed because the source data are not available.")
        return

    summary = build_household_resource_summary(detail_df)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Mean Mobile Phones", format_number(summary["avg_hp"], 2))
    metric_cols[1].metric("Mean Household Members", format_number(summary["avg_members"], 2))
    metric_cols[2].metric("Mean Communication Expenditure", format_currency(summary["avg_comm"], 0))
    metric_cols[3].metric("Median Communication Expenditure", format_currency(summary["median_comm"], 0))

    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(
        build_household_average_figure(detail_df),
        width="stretch",
        key=f"{section_key}_avg_hp_members",
    )
    chart_cols[1].plotly_chart(
        build_comm_cost_distribution_figure(detail_df),
        width="stretch",
        key=f"{section_key}_comm_distribution",
    )

    bottom_cols = st.columns(2)
    bottom_cols[0].plotly_chart(
        build_household_resource_by_desa_figure(detail_df, "hp_jumlah_num"),
        width="stretch",
        key=f"{section_key}_hp_by_desa",
    )
    bottom_cols[1].plotly_chart(
        build_household_resource_by_desa_figure(detail_df, "jml_keluarga"),
        width="stretch",
        key=f"{section_key}_members_by_desa",
    )

    if "rp_komunikasi_tertinggi" in detail_df.columns and detail_df["rp_komunikasi_tertinggi"].notna().any():
        st.plotly_chart(
            build_household_resource_by_desa_figure(detail_df, "rp_komunikasi_tertinggi"),
            width="stretch",
            key=f"{section_key}_comm_by_desa",
        )


def render_overall_inequality_section(tables: dict[str, pd.DataFrame]) -> None:
    summary_df, contributor_df = resolve_inequality_tables(tables)
    if summary_df.empty or contributor_df.empty:
        return

    overall_summary = summary_df.loc[summary_df["cakupan_analisis"].astype("string").eq("keseluruhan")].head(1)
    overall_contributors = contributor_df.loc[
        contributor_df["cakupan_analisis"].astype("string").eq("keseluruhan")
    ].copy()
    if overall_summary.empty or overall_contributors.empty:
        return

    top_row = overall_contributors.sort_values("peringkat_kontribusi", ascending=True, kind="mergesort").head(1)
    top_label = "-"
    if not top_row.empty:
        top_label = f"{top_row['family_id'].iloc[0]} ({format_percent(top_row['porsi_kontribusi_gini'].iloc[0])})"

    st.markdown("### Overall Inequality")
    st.caption(
        "Each contribution is calculated from the total difference between a household digital inclusion score and the scores of other households. A larger contribution indicates that the household is farther from the overall pattern and therefore contributes more strongly to inequality. Relative Gini categories are based on tertiles across sampled villages."
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Overall Gini", format_number(overall_summary["gini_iid_rumah_tangga"].iloc[0]))
    metric_cols[1].metric("Relative Category", str(format_gini_label(overall_summary["interpretasi_gini"].iloc[0])))
    metric_cols[2].metric("Households Included", format_number(overall_summary["jumlah_kk"].iloc[0], 0))
    metric_cols[3].metric("Leading Contributor", top_label)

    chart_cols = st.columns([1.15, 0.85])
    chart_cols[0].plotly_chart(
        build_top_inequality_contributors_figure(
            overall_contributors,
            title="Households with the Largest Overall Contributions to Inequality",
        ),
        width="stretch",
        key="overall_inequality_contributors",
    )
    chart_cols[0].caption(
        "The percentage shown on each bar is the household share of total Gini inequality, not a household-specific Gini value."
    )
    with chart_cols[1]:
        preview_columns = [
            column
            for column in (
                "family_id",
                "deskel",
                "iid_rumah_tangga",
                "arah_deviasi",
                "porsi_kontribusi_gini",
            )
            if column in overall_contributors.columns
        ]
        preview_df = overall_contributors[preview_columns].head(15).copy()
        if "porsi_kontribusi_gini" in preview_df.columns:
            preview_df["porsi_kontribusi_gini"] = preview_df["porsi_kontribusi_gini"].map(
                lambda value: format_percent(value)
            )
        st.dataframe(prepare_display_dataframe(preview_df), width="stretch", hide_index=True)


def render_summary_tab(tables: dict[str, pd.DataFrame], detail_df: pd.DataFrame) -> None:
    st.markdown("<span class='pill-note'>Executive Summary</span>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>Review the core index scores, household distribution, and processing notes in a concise research-oriented format.</div>",
        unsafe_allow_html=True,
    )
    render_top_summary_metrics(tables)

    keluarga_df = tables.get("data_keluarga", pd.DataFrame())
    desa_df = tables.get("indeks_desa", pd.DataFrame())
    warga_df = tables.get("sebaran_warga_iid_rt", pd.DataFrame())
    household_df = get_household_rows(keluarga_df)

    if not household_df.empty:
        chart_cols = st.columns(2)
        chart_cols[0].plotly_chart(
            build_category_count_figure(household_df),
            width="stretch",
            key="summary_category_count",
        )
        chart_cols[1].plotly_chart(
            build_household_histogram_figure(household_df),
            width="stretch",
            key="summary_household_histogram",
        )

    if not warga_df.empty:
        warga_col, ringkas_col = st.columns([1.15, 0.85])
        warga_col.plotly_chart(
            build_person_distribution_figure(warga_df),
            width="stretch",
            key="summary_person_distribution",
        )
        with ringkas_col:
            st.markdown("### Processing Summary")
            summary_df = tables.get("ringkasan_pengolahan", pd.DataFrame())
            if summary_df.empty:
                st.info("The processing summary is not available for this data source.")
            else:
                st.dataframe(prepare_display_dataframe(summary_df), width="stretch", hide_index=True)
    elif not desa_df.empty:
        st.markdown("### Processing Summary")
        summary_df = tables.get("ringkasan_pengolahan", pd.DataFrame())
        if summary_df.empty:
            st.info("The processing summary is not available for this data source.")
        else:
            st.dataframe(prepare_display_dataframe(summary_df), width="stretch", hide_index=True)

    st.markdown("### Household Resources and Communication Expenditure")
    st.caption("These statistics are computed at the valid-household level.")
    render_household_resource_section(detail_df, section_key="summary_resource")


def render_household_tab(tables: dict[str, pd.DataFrame], detail_df: pd.DataFrame) -> None:
    keluarga_df = tables.get("data_keluarga", pd.DataFrame())
    household_df = get_household_rows(keluarga_df)

    if household_df.empty:
        st.warning("No valid household records are available for visualization.")
        return

    filter_cols = st.columns(2)
    all_villages_label = "All Villages"
    all_categories_label = "All Categories"
    desa_options = [all_villages_label] + sorted(household_df["deskel"].dropna().astype(str).unique().tolist()) if "deskel" in household_df.columns else [all_villages_label]
    selected_desa = filter_cols[0].selectbox("Village Filter", options=desa_options)
    kategori_options = [all_categories_label] + [
        category for category in VISIBLE_CATEGORY_ORDER if category in household_df["kategori_iid_rt"].astype("string").unique().tolist()
    ]
    selected_category = filter_cols[1].selectbox(
        "Household Digital Inclusion Category Filter",
        options=kategori_options,
        format_func=lambda value: all_categories_label if value == all_categories_label else str(format_iid_category_label(value)),
    )

    filtered_df = household_df.copy()
    if selected_desa != all_villages_label and "deskel" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["deskel"].astype(str) == selected_desa]
    if selected_category != all_categories_label:
        filtered_df = filtered_df[filtered_df["kategori_iid_rt"].astype(str) == selected_category]

    st.caption(f"Displaying {len(filtered_df):,} valid households.")

    filtered_detail_df = pd.DataFrame()
    if not detail_df.empty:
        filtered_detail_df = detail_df.copy()
        if selected_desa != all_villages_label and "deskel" in filtered_detail_df.columns:
            filtered_detail_df = filtered_detail_df[filtered_detail_df["deskel"].astype(str) == selected_desa]
        if selected_category != all_categories_label and "kategori_iid_rt" in filtered_detail_df.columns:
            filtered_detail_df = filtered_detail_df[filtered_detail_df["kategori_iid_rt"].astype(str) == selected_category]

    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(
        build_category_count_figure(filtered_df),
        width="stretch",
        key="household_category_count",
    )
    chart_cols[1].plotly_chart(
        build_household_histogram_figure(filtered_df),
        width="stretch",
        key="household_histogram",
    )

    st.markdown("### Household Structure Statistics")
    render_household_resource_section(filtered_detail_df, section_key="household_resource")

    map_figure = build_map_figure(filtered_df)
    if map_figure is not None:
        st.plotly_chart(map_figure, width="stretch", key="household_map")

    preview_columns = [column for column in ("family_id", "deskel", "iid_rumah_tangga", "kategori_iid_rt", "dimensi_A", "dimensi_B", "dimensi_C", "dimensi_D", "dimensi_E") if column in filtered_df.columns]
    st.markdown("### Valid Household Data Preview")
    st.dataframe(prepare_display_dataframe(filtered_df[preview_columns].head(200)), width="stretch", hide_index=True)


def render_desa_tab(tables: dict[str, pd.DataFrame], detail_df: pd.DataFrame) -> None:
    desa_df = normalize_desa_gini_table(tables.get("indeks_desa", pd.DataFrame()))
    distribution_df = tables.get("sebaran_iid_rt_desa", pd.DataFrame()).copy()
    household_df = get_household_rows(tables.get("data_keluarga", pd.DataFrame()))
    household_profile_df = build_household_profile_lookup(household_df, detail_df)
    gini_distribution_df = normalize_gini_distribution_table(tables.get("sebaran_gini_desa", pd.DataFrame()), desa_df)
    inequality_summary_df, inequality_contributor_df = resolve_inequality_tables(tables)
    if desa_df.empty:
        st.warning("The village index table is not available.")
        return

    numeric_columns = ["iid_desa", "gini_iid_rumah_tangga", "jumlah_kk"]
    for column in numeric_columns:
        if column in desa_df.columns:
            desa_df[column] = pd.to_numeric(desa_df[column], errors="coerce")
    if "ikd_desa" in desa_df.columns:
        desa_df["ikd_desa"] = pd.to_numeric(desa_df["ikd_desa"], errors="coerce")
        desa_df = add_ikd_tertile_columns(desa_df)

    top_cols = st.columns(2)
    top_cols[0].plotly_chart(
        build_top_bottom_desa_figure(desa_df, "top"),
        width="stretch",
        key="desa_top_iid",
    )
    top_cols[1].plotly_chart(
        build_top_bottom_desa_figure(desa_df, "bottom"),
        width="stretch",
        key="desa_bottom_iid",
    )

    mid_cols = st.columns(2)
    mid_cols[0].plotly_chart(
        build_dimension_profile_figure(desa_df),
        width="stretch",
        key="desa_dimension_profile",
    )
    mid_cols[1].plotly_chart(
        build_gini_scatter_figure(desa_df),
        width="stretch",
        key="desa_gini_scatter",
    )

    if not gini_distribution_df.empty:
        st.markdown("### Relative Gini Categories across Villages")
        st.caption(
            "Because all village Gini values fall within a low absolute range, relative inequality positions are distinguished with tertiles: the lowest third, middle third, and highest third within the study sample."
        )
        preview_columns = [
            column
            for column in ("interpretasi_gini", "rentang_gini", "jumlah_desa", "persentase_desa")
            if column in gini_distribution_df.columns
        ]
        gini_preview_df = gini_distribution_df[preview_columns].copy()
        if "persentase_desa" in gini_preview_df.columns:
            gini_preview_df["persentase_desa"] = gini_preview_df["persentase_desa"].map(format_percent)
        st.dataframe(prepare_display_dataframe(gini_preview_df), width="stretch", hide_index=True)

    if not distribution_df.empty:
        st.markdown("### Household Digital Inclusion Categories across Villages")
        st.caption(
            "The heatmap presents the percentage composition of household digital inclusion categories in each village, allowing the full village distribution to be read without limiting the view to the largest villages."
        )
        sort_option_map = {
            "Alphabetical by Village": "alphabetical",
            "Highest Village Index First": "iid_desc",
            "Largest Household Count First": "kk_desc",
        }
        control_cols = st.columns(2)
        selected_sort_label = control_cols[0].selectbox(
            "Village Ordering for Heatmap",
            options=list(sort_option_map.keys()),
            key="desa_distribution_sort_mode",
        )
        pivot_df, distribution_meta_df = prepare_desa_distribution_matrix(
            distribution_df,
            desa_df,
            sort_option_map[selected_sort_label],
        )
        if not pivot_df.empty:
            selected_desa_distribution = control_cols[1].selectbox(
                "Select a Village for Category Composition",
                options=distribution_meta_df["label_desa"].tolist(),
                key="desa_distribution_focus_selector",
            )
            st.plotly_chart(
                build_desa_distribution_heatmap(pivot_df),
                width="stretch",
                key="desa_distribution_heatmap",
            )
            selected_meta = distribution_meta_df.loc[
                distribution_meta_df["label_desa"].astype("string").eq(str(selected_desa_distribution))
            ].head(1)
            detail_metric_cols = st.columns(2)
            if not selected_meta.empty:
                if "total_kk_desa" in selected_meta.columns:
                    detail_metric_cols[0].metric(
                        "Village Households",
                        format_number(selected_meta["total_kk_desa"].iloc[0], 0),
                    )
                if "iid_desa" in selected_meta.columns:
                    detail_metric_cols[1].metric(
                        "Village Digital Inclusion Index",
                        format_number(selected_meta["iid_desa"].iloc[0]),
                    )
            st.plotly_chart(
                build_desa_distribution_focus_figure(distribution_df, selected_desa_distribution),
                width="stretch",
                key="desa_distribution_focus_chart",
            )

    desa_inequality_df = inequality_summary_df.loc[
        inequality_summary_df["cakupan_analisis"].astype("string").eq("desa")
    ].copy()
    desa_inequality_df = desa_inequality_df.dropna(subset=["deskel"], how="all")
    if not desa_inequality_df.empty:
        st.markdown("### Village-Level Inequality Assessment")
        st.caption(
            "This section reports the relative inequality category for each village and identifies the households that contribute most strongly to within-village inequality."
        )

        selector_df = add_desa_label(desa_inequality_df[["kode_deskel", "deskel"]].drop_duplicates().copy())
        selected_label = st.selectbox(
            "Select a Village to Review Inequality Contributors",
            options=selector_df["label_desa"].tolist(),
            key="desa_inequality_selector",
        )
        selected_info = selector_df.loc[selector_df["label_desa"] == selected_label].iloc[0]
        selected_summary = desa_inequality_df.loc[
            desa_inequality_df["deskel"].astype("string").eq(str(selected_info["deskel"]))
        ].copy()
        if pd.notna(selected_info["kode_deskel"]):
            selected_summary = selected_summary.loc[
                selected_summary["kode_deskel"].astype("string").eq(str(selected_info["kode_deskel"]))
            ]
        selected_summary = selected_summary.head(1)

        selected_contributors = inequality_contributor_df.loc[
            (
                inequality_contributor_df["cakupan_analisis"].astype("string").eq("desa")
            )
            & (
                inequality_contributor_df["deskel_cakupan"].astype("string").eq(str(selected_info["deskel"]))
            )
        ].copy()
        if pd.notna(selected_info["kode_deskel"]):
            selected_contributors = selected_contributors.loc[
                selected_contributors["kode_deskel_cakupan"].astype("string").eq(str(selected_info["kode_deskel"]))
            ]

        profile_merge_columns = [
            column
            for column in (
                "family_id",
                "nama_kk_subjek",
                "label_kk",
                "subjek",
                "usia",
                "suku",
                "kategori_iid_rt",
                "jml_keluarga",
                "dimensi_A",
                "dimensi_B",
                "dimensi_C",
                "dimensi_D",
                "dimensi_E",
                "indikator_A",
                "indikator_B",
                "indikator_C",
                "indikator_D",
                "indikator_E",
                "indikator_F",
                "indikator_G",
                "indikator_H",
                "indikator_I",
                "indikator_J",
                "indikator_K",
                "indikator_L",
                "indikator_M",
            )
            if column in household_profile_df.columns
        ]
        if profile_merge_columns:
            selected_contributors = selected_contributors.merge(
                household_profile_df[profile_merge_columns].drop_duplicates(subset=["family_id"]),
                on="family_id",
                how="left",
            )

        all_categories_label = "All Categories"
        selected_category_inequality = all_categories_label
        if "kategori_iid_rt" in selected_contributors.columns:
            category_options = [all_categories_label] + [
                category
                for category in VISIBLE_CATEGORY_ORDER
                if category in selected_contributors["kategori_iid_rt"].astype("string").unique().tolist()
            ]
            selected_category_inequality = st.selectbox(
                "Household Digital Inclusion Category Filter for Contributor Profiles",
                options=category_options,
                format_func=lambda value: all_categories_label if value == all_categories_label else str(format_iid_category_label(value)),
                key="desa_inequality_category_selector",
            )

        filtered_contributors = selected_contributors.copy()
        if selected_category_inequality != all_categories_label and "kategori_iid_rt" in filtered_contributors.columns:
            filtered_contributors = filtered_contributors.loc[
                filtered_contributors["kategori_iid_rt"].astype("string").eq(selected_category_inequality)
            ].copy()

        if not selected_summary.empty:
            top_contributor = filtered_contributors.sort_values(
                "peringkat_kontribusi",
                ascending=True,
                kind="mergesort",
            ).head(1)
            top_contributor_label = "-"
            if not top_contributor.empty:
                contributor_name = None
                if "nama_kk_subjek" in top_contributor.columns:
                    contributor_name = top_contributor["nama_kk_subjek"].astype("string").iloc[0]
                if contributor_name is None or pd.isna(contributor_name) or str(contributor_name).strip() in {"", "nan"}:
                    contributor_name = str(top_contributor["family_id"].iloc[0])
                top_contributor_label = (
                    f"{contributor_name} "
                    f"({format_percent(top_contributor['porsi_kontribusi_gini'].iloc[0])})"
                )

            metric_cols = st.columns(4)
            metric_cols[0].metric("Village Gini", format_number(selected_summary["gini_iid_rumah_tangga"].iloc[0]))
            metric_cols[1].metric("Relative Category", str(format_gini_label(selected_summary["interpretasi_gini"].iloc[0])))
            metric_cols[2].metric("Households", format_number(selected_summary["jumlah_kk"].iloc[0], 0))
            metric_cols[3].metric(
                "Leading Contributor in Category" if selected_category_inequality != all_categories_label else "Leading Contributor",
                top_contributor_label,
            )

            if filtered_contributors.empty:
                st.info(f"No households in the `{format_iid_category_label(selected_category_inequality)}` category are available for this village.")
            else:
                title_suffix = (
                    f" in the {format_iid_category_label(selected_category_inequality)} Category"
                    if selected_category_inequality != all_categories_label
                    else ""
                )
                st.plotly_chart(
                    build_top_inequality_contributors_figure(
                        filtered_contributors,
                        title=f"Largest Inequality Contributors{title_suffix} in {selected_info['deskel']}",
                    ),
                    width="stretch",
                    key="desa_selected_inequality_contributors",
                )
                st.caption(
                    "The percentage shown on each bar is the household share of total Gini inequality within the selected scope, not a household-specific Gini value."
                )
                st.caption(
                    "The profile below shows one row per household head, combining basic source-data identifiers with processed dimension and indicator scores."
                )
                profile_preview_df = build_contributor_profile_preview_df(
                    filtered_contributors.sort_values(
                        ["porsi_kontribusi_gini", "iid_rumah_tangga"],
                        ascending=[False, False],
                        kind="mergesort",
                    )
                )
                st.dataframe(prepare_display_dataframe(profile_preview_df), width="stretch", hide_index=True)

        ranking_columns = [
            column
            for column in (
                "kode_deskel",
                "deskel",
                "jumlah_kk",
                "gini_iid_rumah_tangga",
                "interpretasi_gini",
                "family_id_kontributor_utama",
                "porsi_kontributor_utama",
            )
            if column in desa_inequality_df.columns
        ]
        ranking_df = desa_inequality_df[ranking_columns].sort_values(
            ["gini_iid_rumah_tangga", "jumlah_kk"],
            ascending=[False, False],
            kind="mergesort",
        ).copy()
        if "porsi_kontributor_utama" in ranking_df.columns:
            ranking_df["porsi_kontributor_utama"] = ranking_df["porsi_kontributor_utama"].map(format_percent)
        st.dataframe(prepare_display_dataframe(ranking_df), width="stretch", hide_index=True)

    if {"ikd_desa", "ikd_tertil", "kategori_tertil"}.issubset(desa_df.columns):
        st.markdown("### Villages by Relative Digital Deprivation Tertile")
        st.caption(
            "The `ikd_desa` column is interpreted as the village digital deprivation score, calculated as the complement of `1 - iid_desa`. It is not the Village Welfare Index. Relative tertiles are computed from the `ikd_desa` distribution; higher values indicate higher relative digital deprivation within the sample."
        )
        tertile_cols = st.columns(2)
        tertile_cols[0].plotly_chart(
            build_ikd_tertile_distribution_figure(desa_df),
            width="stretch",
            key="desa_ikd_tertile_distribution",
        )
        tertile_cols[1].plotly_chart(
            build_ikd_tertile_scatter_figure(desa_df),
            width="stretch",
            key="desa_ikd_tertile_scatter",
        )

        tertile_preview_columns = [
            column
            for column in ("kode_deskel", "deskel", "jumlah_kk", "ikd_desa", "ikd_tertil", "kategori_tertil")
            if column in desa_df.columns
        ]
        st.dataframe(
            prepare_display_dataframe(desa_df[tertile_preview_columns].sort_values("ikd_desa", ascending=True)),
            width="stretch",
            hide_index=True,
        )

    st.markdown("### Village Index Preview")
    st.dataframe(prepare_display_dataframe(desa_df.head(100)), width="stretch", hide_index=True)


def render_journal_analysis_tab(tables: dict[str, pd.DataFrame], detail_df: pd.DataFrame) -> None:
    household_df = prepare_journal_household_df(tables)
    raw_profile_df = prepare_journal_raw_profile_df(detail_df, household_df)
    village_df = prepare_journal_village_df(tables, household_df)

    if household_df.empty and village_df.empty:
        st.warning("The journal analysis page requires household and village index tables.")
        return

    st.markdown("<span class='pill-note'>Journal-oriented analysis</span>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>This page uses formal English labels for charts, tables, and visual annotations so the outputs can be adapted for academic reporting.</div>",
        unsafe_allow_html=True,
    )

    total_households = int(len(household_df))
    total_villages = int(len(village_df))
    mean_household_index = (
        pd.to_numeric(household_df.get("iid_rumah_tangga"), errors="coerce").mean()
        if not household_df.empty
        else pd.NA
    )
    mean_village_index = (
        pd.to_numeric(village_df.get("iid_desa"), errors="coerce").mean()
        if not village_df.empty
        else pd.NA
    )
    vulnerable_share = pd.NA
    if not household_df.empty and "kategori_iid_rt" in household_df.columns:
        vulnerable_share = household_df["kategori_iid_rt"].astype(str).isin({"sangat rendah", "rendah"}).mean()

    st.markdown(
        build_journal_overview_table_html(
            total_households,
            total_villages,
            mean_household_index,
            mean_village_index,
            vulnerable_share,
        ),
        unsafe_allow_html=True,
    )

    st.markdown("### 1. Descriptive Profile of Households and Villages")
    if household_df.empty:
        st.info("Household-level records are not available for the descriptive profile.")
    else:
        st.markdown("#### Raw Household Characteristics")
        st.caption("These visualizations are derived from the source household variables, not from aggregate index scores.")
        characteristic_figures = [
            build_journal_education_histogram_figure(raw_profile_df),
            build_journal_device_ownership_bar_figure(raw_profile_df),
            build_journal_phone_count_histogram_figure(raw_profile_df),
            build_journal_internet_access_pie_figure(raw_profile_df),
            build_journal_social_participation_bar_figure(raw_profile_df),
        ]
        characteristic_figures = [figure for figure in characteristic_figures if figure is not None]
        if characteristic_figures:
            for index in range(0, len(characteristic_figures), 2):
                characteristic_cols = st.columns(2)
                for chart_offset, (column_container, figure) in enumerate(
                    zip(characteristic_cols, characteristic_figures[index : index + 2], strict=False),
                    start=0,
                ):
                    column_container.plotly_chart(
                        figure,
                        width="stretch",
                        key=f"journal_raw_household_characteristic_{index + chart_offset}",
                    )
        else:
            st.info("Source household variables are not available for raw descriptive visualization.")

        with st.expander("Scored Index Component Summary", expanded=False):
            domain_profile_df = build_journal_domain_profile_df(household_df)
            indicator_profile_df = build_journal_indicator_profile_df(household_df)
            if not domain_profile_df.empty:
                profile_cols = st.columns([0.95, 1.05])
                profile_cols[0].plotly_chart(
                    build_journal_domain_profile_figure(domain_profile_df),
                    width="stretch",
                    key="journal_domain_profile",
                )
                if not indicator_profile_df.empty:
                    profile_cols[1].plotly_chart(
                        build_journal_indicator_profile_figure(indicator_profile_df),
                        width="stretch",
                        key="journal_indicator_profile",
                    )
                    st.dataframe(
                        format_journal_dataframe(
                            indicator_profile_df,
                            integer_columns=("Valid Households",),
                            score_columns=("Mean Score", "Median Score"),
                        ),
                        width="stretch",
                        hide_index=True,
                    )

    st.markdown("### 2. Distribution of Household Digital Inclusion")
    if household_df.empty:
        st.info("Household-level index scores are not available.")
    else:
        category_share_df = build_journal_category_share_df(household_df)
        distribution_cols = st.columns(2)
        distribution_cols[0].plotly_chart(
            build_journal_household_histogram_figure(household_df),
            width="stretch",
            key="journal_household_histogram",
        )
        distribution_cols[1].plotly_chart(
            build_journal_category_share_figure(category_share_df),
            width="stretch",
            key="journal_category_share",
        )

        household_labeled_df = add_journal_village_name(household_df)
        village_options = sorted(household_labeled_df["Village"].dropna().astype(str).unique().tolist())
        if village_options:
            box_start, box_end, _ = render_journal_page_selector(
                st,
                "Household boxplot village page",
                len(village_options),
                key="journal_box_village_page",
            )
            selected_box_villages = village_options[box_start:box_end]
            st.plotly_chart(
                build_journal_household_boxplot_figure(household_df, selected_box_villages),
                width="stretch",
                key="journal_household_boxplot",
            )

        vulnerability_df = build_journal_vulnerability_summary_df(household_df)
        if not vulnerability_df.empty:
            vulnerability_start, vulnerability_end, _ = render_journal_page_selector(
                st,
                "Digitally vulnerable household village page",
                len(vulnerability_df),
                key="journal_vulnerability_page",
            )
            st.plotly_chart(
                build_journal_vulnerability_figure(
                    vulnerability_df,
                    top_n=JOURNAL_VILLAGE_PAGE_SIZE,
                    offset=vulnerability_start,
                ),
                width="stretch",
                key="journal_vulnerability_villages",
            )
            vulnerability_columns = [
                "Village",
                "Households",
                "Vulnerable Households",
                "Vulnerable Share",
                "Mean Household Index",
                *[column for column in vulnerability_df.columns if column.startswith("Mean ") and column != "Mean Household Index"],
            ]
            vulnerability_columns = [column for column in vulnerability_columns if column in vulnerability_df.columns]
            st.dataframe(
                format_journal_dataframe(
                    vulnerability_df[vulnerability_columns].iloc[vulnerability_start:vulnerability_end],
                    percent_columns=("Vulnerable Share",),
                    integer_columns=("Households", "Vulnerable Households"),
                    score_columns=tuple(column for column in vulnerability_columns if column.startswith("Mean ")),
                ),
                width="stretch",
                hide_index=True,
            )

    st.markdown("### 3. Village-Level Digital Inclusion Index")
    if village_df.empty:
        st.info("Village-level index records are not available.")
    else:
        village_sorted_df = village_df.sort_values("iid_desa", ascending=False, kind="mergesort")
        highest_village = village_sorted_df.head(1)
        lowest_village = village_sorted_df.tail(1)
        village_metric_cols = st.columns(4)
        village_metric_cols[0].metric(
            "Highest Village Index",
            format_journal_number(highest_village["iid_desa"].iloc[0]) if not highest_village.empty else "-",
            highest_village["Village"].iloc[0] if not highest_village.empty else None,
        )
        village_metric_cols[1].metric(
            "Lowest Village Index",
            format_journal_number(lowest_village["iid_desa"].iloc[0]) if not lowest_village.empty else "-",
            lowest_village["Village"].iloc[0] if not lowest_village.empty else None,
        )
        village_metric_cols[2].metric(
            "Standard Deviation",
            format_journal_number(pd.to_numeric(village_df["iid_desa"], errors="coerce").std()),
        )
        village_metric_cols[3].metric(
            "Index Range",
            format_journal_number(
                pd.to_numeric(village_df["iid_desa"], errors="coerce").max()
                - pd.to_numeric(village_df["iid_desa"], errors="coerce").min()
            ),
        )

        ranking_start, ranking_end, _ = render_journal_page_selector(
            st,
            "Village ranking page",
            len(village_df),
            key="journal_village_ranking_page",
        )

        village_chart_cols = st.columns(2)
        village_chart_cols[0].plotly_chart(
            build_journal_village_index_bar_figure(
                village_df,
                "highest",
                top_n=JOURNAL_VILLAGE_PAGE_SIZE,
                offset=ranking_start,
            ),
            width="stretch",
            key="journal_highest_village_index",
        )
        village_chart_cols[1].plotly_chart(
            build_journal_village_index_bar_figure(
                village_df,
                "lowest",
                top_n=JOURNAL_VILLAGE_PAGE_SIZE,
                offset=ranking_start,
            ),
            width="stretch",
            key="journal_lowest_village_index",
        )

        ranking_table_df = build_journal_village_ranking_table(village_df)
        st.dataframe(
            format_journal_dataframe(
                ranking_table_df.iloc[ranking_start:ranking_end],
                integer_columns=("Rank", "Households"),
                score_columns=(
                    "Village Digital Inclusion Index",
                    "Village Digital Deprivation Score",
                    "Within-Village Gini",
                ),
            ),
            width="stretch",
            hide_index=True,
        )

        map_figure = build_journal_village_map_figure(village_df)
        if map_figure is not None:
            st.plotly_chart(map_figure, width="stretch", key="journal_village_index_map")
        else:
            st.info("Village centroid coordinates are not available for the spatial map.")

    st.markdown("### 4. Dimensional Profile of Digital Inclusion")
    if village_df.empty:
        st.info("Village-level dimension scores are not available.")
    else:
        dimension_strength_df = build_journal_dimension_strength_df(village_df)
        if dimension_strength_df.empty:
            st.info("Dimension scores are not available in the village-level index table.")
        else:
            strongest_dimension = dimension_strength_df.sort_values("Mean Score", ascending=False).head(1)
            weakest_dimension = dimension_strength_df.sort_values("Mean Score", ascending=True).head(1)
            dimension_metric_cols = st.columns(2)
            dimension_metric_cols[0].metric(
                "Strongest Dimension",
                strongest_dimension["Dimension"].iloc[0],
                format_journal_number(strongest_dimension["Mean Score"].iloc[0]),
            )
            dimension_metric_cols[1].metric(
                "Weakest Dimension",
                weakest_dimension["Dimension"].iloc[0],
                format_journal_number(weakest_dimension["Mean Score"].iloc[0]),
            )

            dimension_cols = st.columns([0.9, 1.1])
            dimension_cols[0].plotly_chart(
                build_journal_dimension_bar_figure(dimension_strength_df),
                width="stretch",
                key="journal_dimension_strength",
            )
            village_options = village_df.sort_values("iid_desa", ascending=False, kind="mergesort")["Village"].tolist()
            default_radar_villages = list(
                dict.fromkeys(
                    [
                        *village_df.nlargest(2, "iid_desa")["Village"].tolist(),
                        *village_df.nsmallest(2, "iid_desa")["Village"].tolist(),
                    ]
                )
            )
            selected_radar_villages = dimension_cols[1].multiselect(
                "Villages displayed in the radar chart",
                options=village_options,
                default=[village for village in default_radar_villages if village in village_options],
                key="journal_radar_villages",
            )
            if len(selected_radar_villages) > 6:
                dimension_cols[1].warning("Only the first six selected villages are displayed to preserve readability.")
                selected_radar_villages = selected_radar_villages[:6]
            if selected_radar_villages:
                dimension_cols[1].plotly_chart(
                    build_journal_dimension_radar_figure(village_df, selected_radar_villages),
                    width="stretch",
                    key="journal_dimension_radar",
                )

            heatmap_dimension_columns = [column for column in JOURNAL_DIMENSION_LABELS if column in village_df.columns]
            heatmap_village_count = int(village_df.dropna(subset=heatmap_dimension_columns, how="all").shape[0])
            heatmap_start, _, _ = render_journal_page_selector(
                st,
                "Dimension heatmap village page",
                heatmap_village_count,
                key="journal_dimension_heatmap_page",
            )
            st.plotly_chart(
                build_journal_dimension_heatmap_figure(
                    village_df,
                    limit=JOURNAL_VILLAGE_PAGE_SIZE,
                    offset=heatmap_start,
                ),
                width="stretch",
                key="journal_dimension_heatmap",
            )

            lagging_dimension_df = build_journal_lagging_dimension_table(village_df, bottom_n=3)
            if not lagging_dimension_df.empty:
                st.dataframe(
                    format_journal_dataframe(
                        lagging_dimension_df,
                        integer_columns=("Lag Rank",),
                        score_columns=("Dimension Score", "Village Digital Inclusion Index"),
                    ),
                    width="stretch",
                    hide_index=True,
                )

    st.markdown("### 5. Digital Deprivation and Within-Village Inequality")
    if village_df.empty or not {"iid_desa", "gini_iid_rumah_tangga"}.issubset(village_df.columns):
        st.info("Village-level deprivation and Gini statistics are not available.")
    else:
        st.caption(
            "A village with a moderate mean index should not automatically be interpreted as inclusive when within-village inequality is high, because the mean may conceal digitally deprived households."
        )
        deprivation_start, deprivation_end, _ = render_journal_page_selector(
            st,
            "Digital deprivation village page",
            len(village_df),
            key="journal_deprivation_page",
        )
        deprivation_cols = st.columns(2)
        deprivation_cols[0].plotly_chart(
            build_journal_deprivation_scatter_figure(village_df),
            width="stretch",
            key="journal_deprivation_gini_scatter",
        )
        deprivation_cols[1].plotly_chart(
            build_journal_deprivation_bar_figure(
                village_df,
                top_n=JOURNAL_VILLAGE_PAGE_SIZE,
                offset=deprivation_start,
            ),
            width="stretch",
            key="journal_deprivation_bar",
        )
        priority_df, moderate_high_inequality_df = build_journal_deprivation_priority_table(village_df)
        st.markdown("#### Priority Villages by Digital Deprivation and Internal Inequality")
        st.dataframe(
            format_journal_dataframe(
                priority_df.iloc[deprivation_start:deprivation_end],
                integer_columns=("Households",),
                score_columns=(
                    "Village Digital Inclusion Index",
                    "Village Digital Deprivation Score",
                    "Within-Village Gini",
                ),
            ),
            width="stretch",
            hide_index=True,
        )
        st.markdown("#### Moderate-Index Villages with High Internal Inequality")
        if moderate_high_inequality_df.empty:
            st.info("No moderate-index villages meet the high internal inequality criterion in the current data.")
        else:
            moderate_start, moderate_end, _ = render_journal_page_selector(
                st,
                "Moderate-index high-inequality village page",
                len(moderate_high_inequality_df),
                key="journal_moderate_inequality_page",
            )
            st.dataframe(
                format_journal_dataframe(
                    moderate_high_inequality_df.iloc[moderate_start:moderate_end],
                    integer_columns=("Households",),
                    score_columns=(
                        "Village Digital Inclusion Index",
                        "Village Digital Deprivation Score",
                        "Within-Village Gini",
                    ),
                ),
                width="stretch",
                hide_index=True,
            )


def build_dimension_determinant_figure(determinant_df: pd.DataFrame) -> go.Figure:
    return build_ranked_red_bar_figure(
        determinant_df,
        value_column="R2 IID Desa",
        label_column="Dimensi",
        title="Dimension-Level Determination of the Village Digital Inclusion Index",
        xaxis_title="Dimension",
        yaxis_title=format_analysis_metric_label("R2 IID Desa"),
        text_auto=".3f",
    )


def build_oat_sensitivity_figure(oat_df: pd.DataFrame) -> go.Figure:
    preferred_metrics = (
        "Rata-rata Kenaikan IID Desa (%)",
        "Rata-rata Penurunan Deprivasi Digital (%)",
    )
    plot_df = oat_df.melt(
        id_vars="Dimensi",
        value_vars=[
            column
            for column in preferred_metrics
            if column in oat_df.columns
        ],
        var_name="Metrik",
        value_name="Persentase",
    ).dropna(subset=["Persentase"])
    plot_df["Metrik Tampilan"] = plot_df["Metrik"].map(format_analysis_metric_label)
    metric_order = [
        format_analysis_metric_label(column)
        for column in preferred_metrics
        if column in plot_df["Metrik"].astype("string").unique().tolist()
    ]
    plot_df = add_top_rank_highlight(plot_df, "Persentase", group_column="Metrik Tampilan")
    plot_df["Dimensi"] = plot_df["Dimensi"].map(lambda value: translate_display_text(value, "Dimensi"))
    plot_df["Metrik Tampilan"] = pd.Categorical(plot_df["Metrik Tampilan"], categories=metric_order, ordered=True)
    plot_df = plot_df.sort_values(["Metrik Tampilan", "Persentase"], ascending=[True, False], kind="mergesort")
    fig = px.bar(
        plot_df,
        x="Dimensi",
        y="Persentase",
        color="_rank_highlight",
        color_discrete_map=RED_RANK_COLORS,
        category_orders={"_rank_highlight": RED_RANK_ORDER, "Metrik Tampilan": metric_order},
        facet_col="Metrik Tampilan",
        text_auto=".2f",
        facet_col_spacing=0.12,
    )
    fig.update_layout(
        title="Outcome Changes in the One-at-a-Time Sensitivity Simulation",
        yaxis_title="Change (%)",
        xaxis_title="Dimension",
        margin=dict(l=10, r=10, t=70, b=10),
        legend_title_text="Value Rank",
    )
    fig.update_traces(marker_line_color="#7f1d1d", marker_line_width=0.8)
    fig.update_xaxes(tickangle=-20)
    fig.for_each_annotation(lambda ann: ann.update(text=ann.text.split("=")[-1]))
    return apply_publication_figure_style(fig)


def build_variable_determinant_figure(variable_df: pd.DataFrame, metric_column: str) -> go.Figure:
    metric_label = format_analysis_metric_label(metric_column)
    display_df = variable_df.copy()
    display_df["Variabel"] = display_df["Variabel"].map(lambda value: translate_display_text(value, "Variabel"))
    return build_ranked_red_bar_figure(
        display_df,
        value_column=metric_column,
        label_column="Variabel",
        title=f"Indicator-Level Determination by {metric_label}",
        xaxis_title=metric_label,
        yaxis_title="Indicator",
        text_auto=".3f",
        orientation="h",
    )


def build_shapley_figure(shapley_df: pd.DataFrame, value_column: str) -> go.Figure:
    value_label = format_analysis_metric_label(value_column)
    display_df = shapley_df.copy()
    display_df["Variabel"] = display_df["Variabel"].map(lambda value: translate_display_text(value, "Variabel"))
    return build_ranked_red_bar_figure(
        display_df,
        value_column=value_column,
        label_column="Variabel",
        title=f"Indicator Shapley Contribution by {value_label}",
        xaxis_title=value_label,
        yaxis_title="Indicator",
        text_auto=".3f",
        orientation="h",
    )


def render_advanced_analysis_tab(tables: dict[str, pd.DataFrame]) -> None:
    dimension_df = tables.get("analisis_determinasi_dimensi", pd.DataFrame()).copy()
    variable_df = tables.get("analisis_determinasi_variabel", pd.DataFrame()).copy()
    oat_df = tables.get("analisis_sensitivitas_oat", pd.DataFrame()).copy()
    shapley_df = tables.get("analisis_shapley_variabel", pd.DataFrame()).copy()
    desa_index_df = tables.get("indeks_desa", pd.DataFrame()).copy()
    variable_explanation_df = tables.get("penjelasan_variabel", pd.DataFrame()).copy()
    download_tables = collect_advanced_analysis_tables_for_download(tables)

    if dimension_df.empty and variable_df.empty and oat_df.empty and shapley_df.empty:
        st.info("Advanced analysis tables are not available.")
        return

    st.markdown("<span class='pill-note'>Advanced Analysis</span>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>This section treats the village digital inclusion index as the primary outcome. The `ikd_desa` field is interpreted as the digital deprivation score, defined as the complement of `1 - iid_desa`; therefore, higher inclusion corresponds to lower digital deprivation.</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Determination statistics are estimated with linear regression on the natural-log transformation ln(100*X+epsilon); the factor 100 is used only for statistical transformation. The OAT simulation applies the selected increase directly on the 0-1 index scale, while Shapley R-squared allocates indicator contributions proportionally to the source dimension and to the village digital inclusion index."
    )
    st.caption("The red gradient highlights the three largest values in each chart: darkest red for rank 1, strong red for rank 2, and medium red for rank 3.")

    if download_tables:
        st.markdown("### Download Advanced Analysis Data")
        excel_sheet_map = {TABLE_SPECS[key]["label"]: df for key, df in download_tables.items()}
        st.download_button(
            label="Download All Advanced Analysis Tables (Excel)",
            data=excel_bytes_from_sheets(excel_sheet_map),
            file_name="analisis_lanjutan_iid_desa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        csv_download_cols = st.columns(len(download_tables))
        for column_container, (key, df) in zip(csv_download_cols, download_tables.items(), strict=False):
            with column_container:
                st.download_button(
                    label=f"Download {TABLE_SPECS[key]['label']}",
                    data=csv_bytes(df),
                    file_name=TABLE_SPECS[key]["filename"],
                    mime="text/csv",
                    width="stretch",
                    key=f"download_{key}",
                )

    subtab_dimensi, subtab_variabel, subtab_oat, subtab_shapley = st.tabs(
        ["Dimension Determination", "Indicator Determination", "OAT Sensitivity", "Shapley"]
    )

    with subtab_dimensi:
        if dimension_df.empty:
            st.info("The dimension determination table is not available.")
        else:
            st.caption(
                "R-squared indicates the share of variation in the village digital inclusion index explained by each dimension after natural-log transformation."
            )
            st.plotly_chart(
                build_dimension_determinant_figure(dimension_df),
                width="stretch",
                key="advanced_dimension_determinant",
            )
            st.dataframe(with_analysis_metric_display_columns(dimension_df), width="stretch", hide_index=True)

    with subtab_variabel:
        if variable_df.empty:
            st.info("The indicator determination table is not available.")
        else:
            st.caption(
                "Indicator determination is reported at two levels: each indicator against its source dimension and each indicator against the overall village digital inclusion index."
            )
            all_dimensions_label = "All Dimensions"
            dimension_options = [all_dimensions_label] + variable_df["Dimensi"].dropna().astype(str).unique().tolist()
            selected_dimension = st.selectbox(
                "Select Dimension",
                options=dimension_options,
                format_func=lambda value: all_dimensions_label if value == all_dimensions_label else str(translate_display_text(value, "Dimensi")),
                key="advanced_variable_dimension_filter",
            )
            filtered_variable_df = variable_df.copy()
            if selected_dimension != all_dimensions_label:
                filtered_variable_df = filtered_variable_df[filtered_variable_df["Dimensi"].astype(str) == selected_dimension]

            metric_column = st.selectbox(
                "Highlighted Metric",
                options=[column for column in ("R2 Dimensi", "R2 IID Desa") if column in filtered_variable_df.columns],
                format_func=format_analysis_metric_label,
                key="advanced_variable_metric",
            )
            st.plotly_chart(
                build_variable_determinant_figure(filtered_variable_df, metric_column),
                width="stretch",
                key="advanced_variable_determinant",
            )
            st.dataframe(
                with_analysis_metric_display_columns(filtered_variable_df),
                width="stretch",
                hide_index=True,
            )

    with subtab_oat:
        if oat_df.empty:
            st.info("The OAT sensitivity table is not available.")
        else:
            selected_oat_percent = st.selectbox(
                "Select OAT Dimension Increase",
                options=list(range(1, 101)),
                index=0,
                format_func=lambda value: f"{value}%",
                key="advanced_oat_increment_percent",
            )
            oat_increment = selected_oat_percent / 100.0
            dynamic_oat_df = iid_pipeline.build_oat_sensitivity_table(
                desa_index_df,
                variable_explanation_df,
                increment_value=oat_increment,
            )
            if dynamic_oat_df.empty:
                dynamic_oat_df = oat_df
            st.caption(
                f"The OAT simulation increases one dimension by {oat_increment:.2f}, equivalent to {selected_oat_percent}%, directly on the 0-1 index scale while holding other dimensions constant. The chart reports percentage changes; absolute deltas and scenario notes remain available in the table."
            )
            st.plotly_chart(
                build_oat_sensitivity_figure(dynamic_oat_df),
                width="stretch",
                key="advanced_oat_sensitivity",
            )
            st.dataframe(with_analysis_metric_display_columns(iid_pipeline.round_numeric_dataframe(dynamic_oat_df)), width="stretch", hide_index=True)

    with subtab_shapley:
        if shapley_df.empty:
            st.info("The Shapley contribution table is not available.")
        else:
            st.caption(
                "Shapley R-squared allocates explanatory model contribution to indicators based on their marginal contribution across all indicator combinations. Dimension values refer to each indicator's contribution to its source dimension, while index values refer to the primary village-level outcome."
            )
            all_dimensions_label = "All Dimensions"
            shapley_dimension_options = [all_dimensions_label] + shapley_df["Dimensi"].dropna().astype(str).unique().tolist()
            selected_shapley_dimension = st.selectbox(
                "Select Dimension for Shapley Analysis",
                options=shapley_dimension_options,
                format_func=lambda value: all_dimensions_label if value == all_dimensions_label else str(translate_display_text(value, "Dimensi")),
                key="advanced_shapley_dimension_filter",
            )
            filtered_shapley_df = shapley_df.copy()
            if selected_shapley_dimension != all_dimensions_label:
                filtered_shapley_df = filtered_shapley_df[filtered_shapley_df["Dimensi"].astype(str) == selected_shapley_dimension]

            shapley_metric = st.selectbox(
                "Displayed Shapley Metric",
                options=[
                    column
                    for column in (
                        "Shapley R2 Dimensi",
                        "Proporsi Shapley Dimensi",
                        "Shapley R2 IID Desa",
                        "Proporsi Shapley IID Desa",
                        "Proporsi Shapley IID",
                    )
                    if column in filtered_shapley_df.columns
                ],
                format_func=format_analysis_metric_label,
                key="advanced_shapley_metric",
            )
            st.plotly_chart(
                build_shapley_figure(filtered_shapley_df.sort_values(shapley_metric, ascending=False), shapley_metric),
                width="stretch",
                key="advanced_shapley_chart",
            )
            preview_df = filtered_shapley_df.copy()
            for column in ("Proporsi Shapley Dimensi", "Proporsi Shapley IID Desa", "Proporsi Shapley IID"):
                if column in preview_df.columns:
                    preview_df[column] = preview_df[column].map(
                        lambda value: format_percent(value) if pd.notna(value) else "-"
                    )
            st.dataframe(with_analysis_metric_display_columns(preview_df), width="stretch", hide_index=True)


def render_variable_tab(tables: dict[str, pd.DataFrame]) -> None:
    variable_df = tables.get("penjelasan_variabel", pd.DataFrame()).copy()
    if variable_df.empty:
        st.warning("The variable documentation table is not available.")
        return

    filter_cols = st.columns(2)
    all_dimensions_label = "All Dimensions"
    dimensi_options = [all_dimensions_label] + sorted(variable_df["dimensi"].dropna().astype(str).unique().tolist()) if "dimensi" in variable_df.columns else [all_dimensions_label]
    selected_dimension = filter_cols[0].selectbox(
        "Dimension Filter",
        options=dimensi_options,
        format_func=lambda value: all_dimensions_label if value == all_dimensions_label else str(translate_display_text(value, "dimensi")),
    )
    keyword = filter_cols[1].text_input("Search Variable or Concept", value="")

    filtered_df = variable_df.copy()
    if selected_dimension != all_dimensions_label and "dimensi" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["dimensi"].astype(str) == selected_dimension]
    if keyword.strip():
        keyword_mask = filtered_df.apply(
            lambda row: keyword.lower() in " ".join(str(value).lower() for value in row.values),
            axis=1,
        )
        filtered_df = filtered_df[keyword_mask]

    st.caption(f"Displaying {len(filtered_df):,} variable documentation rows.")
    st.dataframe(prepare_display_dataframe(filtered_df), width="stretch", hide_index=True)

    if not filtered_df.empty and "nama_variabel" in filtered_df.columns:
        chosen_variable = st.selectbox("Select a Variable for Detail Review", options=filtered_df["nama_variabel"].astype(str).tolist())
        selected_row = filtered_df.loc[filtered_df["nama_variabel"].astype(str) == chosen_variable].head(1).T.reset_index()
        selected_row.columns = ["atribut", "nilai"]
        st.markdown("### Variable Detail")
        st.dataframe(prepare_display_dataframe(selected_row), width="stretch", hide_index=True)


def render_table_explorer_tab(tables: dict[str, pd.DataFrame]) -> None:
    available_keys = [key for key in TABLE_SPECS if key in tables]
    option_labels = {TABLE_SPECS[key]["label"]: key for key in available_keys}
    selected_label = st.selectbox("Select Table", options=list(option_labels.keys()))
    selected_key = option_labels[selected_label]
    df = tables[selected_key]
    spec = TABLE_SPECS[selected_key]

    st.markdown(f"### {spec['label']}")
    st.caption(spec["description"])

    overview_cols = st.columns([0.9, 1.1])
    with overview_cols[0]:
        st.markdown("#### Table Description")
        st.dataframe(build_table_overview(df), width="stretch", hide_index=True)
    with overview_cols[1]:
        st.markdown("#### Column Profile")
        st.dataframe(build_column_profile(df), width="stretch", hide_index=True)

    if len(df.columns) > 0:
        inspected_column = st.selectbox(
            "Column for Detailed Review",
            options=df.columns.tolist(),
            format_func=lambda value: DISPLAY_COLUMN_LABELS.get(value, value),
        )
        render_column_detail(df, inspected_column)

    preview_limit = st.slider("Preview Row Count", min_value=20, max_value=300, value=100, step=20)
    st.markdown("#### Data Preview")
    st.dataframe(prepare_display_dataframe(df.head(preview_limit)), width="stretch", hide_index=True)

    st.download_button(
        label=f"Download {spec['filename']}",
        data=csv_bytes(df),
        file_name=spec["filename"],
        mime="text/csv",
    )


def render_scheme_tables(tables: dict[str, pd.DataFrame]) -> None:
    optional_keys = [key for key in ("batas_kategori_iid_rt", "perbandingan_skema", "skema_rekomendasi") if key in tables]
    if not optional_keys:
        return

    st.markdown("### Additional Scheme Tables")
    for key in optional_keys:
        st.markdown(f"#### {TABLE_SPECS[key]['label']}")
        st.caption(TABLE_SPECS[key]["description"])
        st.dataframe(prepare_display_dataframe(tables[key]), width="stretch", hide_index=True)


def main() -> None:
    inject_styles()
    render_sidebar()

    try:
        with st.spinner("Loading dashboard tables and processed outputs..."):
            bundle = resolve_bundle_from_request()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    meta = bundle["meta"]
    tables = bundle["tables"]

    with st.spinner("Computing mobile phone, household-size, and communication-expenditure statistics..."):
        household_detail_df = resolve_household_detail_df(meta, tables)

    render_hero(meta)

    if meta.get("workbook_path"):
        st.markdown(
            f"<div class='small-muted'>The Excel workbook is available at <code>{meta['workbook_path']}</code></div>",
            unsafe_allow_html=True,
        )

    tab_ringkasan, tab_rt, tab_journal, tab_desa, tab_analisis, tab_variabel, tab_tabel = st.tabs(
        [
            "Summary",
            "Households",
            "Journal Analysis",
            "Villages",
            "Advanced Analysis",
            "Variable Documentation",
            "Table Explorer",
        ]
    )

    with tab_ringkasan:
        render_summary_tab(tables, household_detail_df)
        render_scheme_tables(tables)

    with tab_rt:
        render_household_tab(tables, household_detail_df)

    with tab_journal:
        render_journal_analysis_tab(tables, household_detail_df)

    with tab_desa:
        render_desa_tab(tables, household_detail_df)

    with tab_analisis:
        render_advanced_analysis_tab(tables)

    with tab_variabel:
        render_variable_tab(tables)

    with tab_tabel:
        render_table_explorer_tab(tables)


if __name__ == "__main__":
    main()
