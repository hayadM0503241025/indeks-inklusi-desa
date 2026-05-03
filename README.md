# Dashboard Indeks Inklusi Digital Desa

Dashboard Streamlit untuk pengolahan dan visualisasi Indeks Inklusi Digital Desa, termasuk ringkasan desa, ketimpangan, analisis OAT, Shapley, dan PCA.

## Menjalankan lokal

```bash
pip install -r requirements.txt
streamlit run dashboard_streamlit.py
```

Data besar disimpan sebagai Parquet terkompresi agar tetap ringan untuk GitHub. Dashboard dapat membaca `.csv`, `.xlsx`, `.xls`, dan `.parquet`.

## File data

- `data_asli.parquet`: versi terkompresi dari data mentah.
- `hasil_indeks_digital/data_keluarga.parquet`: versi terkompresi tabel keluarga.
- `hasil_indeks_digital/kontributor_ketimpangan.parquet`: versi terkompresi tabel kontributor ketimpangan.
- CSV kecil di `hasil_indeks_digital/` tetap disertakan agar dashboard bisa langsung memuat folder hasil siap pakai.
