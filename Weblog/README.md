# DenislavaDe
Portfolio
Hello my name is Deni

## WebLog Observatory

A pastel Streamlit dashboard for the Apache access log in `weblog.txt`, built from
the steps in `weblog.ipynb`.

- `data_loader.py` parses the log with a regex and adds derived columns: timestamp, static/bot flags, status class, URL section, browser/OS/device, and country from `GeoLite2-City.mmdb`.
- `app.py` is the dashboard: KPI cards, plus tabs for Overview, Content, Rhythm, Audience, Errors and Data.

### Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Use the sidebar to filter by date range and status class, and to choose the traffic
lens (human page views, all content pages, or every request).
Set `WEBLOG_PATH` / `GEOIP_PATH` to use other files.
