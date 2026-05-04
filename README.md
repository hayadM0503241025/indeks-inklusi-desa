# Dashboard Indeks Inklusi Digital Desa

Dashboard Streamlit untuk pengolahan dan visualisasi Indeks Inklusi Digital Desa, termasuk ringkasan desa, ketimpangan, analisis OAT, Shapley, dan PCA.

## Menjalankan lokal

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy ke Streamlit Community Cloud

Gunakan pengaturan berikut saat membuat atau mengubah app:

- Repository: `hayadM0503241025/indeks-inklusi-desa`
- Branch: `main`
- Main file path: `streamlit_app.py`

File `streamlit_app.py` adalah entrypoint deploy yang menjalankan dashboard utama di `dashboard_streamlit.py`.

Data besar disimpan sebagai Parquet terkompresi agar tetap ringan untuk GitHub. Dashboard dapat membaca `.csv`, `.xlsx`, `.xls`, dan `.parquet`.

## File data

- `data_asli.parquet`: versi terkompresi dari data mentah.
- `hasil_indeks_digital/data_keluarga.parquet`: versi terkompresi tabel keluarga.
- `hasil_indeks_digital/kontributor_ketimpangan.parquet`: versi terkompresi tabel kontributor ketimpangan.
- CSV kecil di `hasil_indeks_digital/` tetap disertakan agar dashboard bisa langsung memuat folder hasil siap pakai.
