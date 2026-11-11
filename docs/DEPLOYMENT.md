# Deployment

The dashboard is a Streamlit app (`app.py`) hosted on Render's free tier. `render.yaml` defines the service, so Render can create it
as a Blueprint (New + > Blueprint > pick this repository). Every push to `main` redeploys.

## What the app reads at runtime

| File | Purpose |
|------|---------|
| `app.py`, `src/view.py`, `src/acs_config.py` | The dashboard and its map rules |
| `data/processed/*.csv` | Cleaned counties, state, tracts and the period table |
| `data/processed/florida_counties.geojson`, `florida_tracts.geojson` | Simplified boundaries |
| `requirements.txt` | pandas, NumPy, Plotly, Streamlit (the rebuild tools are in `requirements-pipeline.txt`) |

`.python-version` pins the Python version Render uses. Free services sleep after about 15 minutes idle, so the first load afterward can
take about 30 seconds. No API key is needed to run the app; the key is only used to rebuild the data.

If a deploy shows an old version, use Manual Deploy > Clear build cache & deploy.

## Health check and what is running

Streamlit serves its own health endpoint at `/_stcore/health` (it returns `ok`). `render.yaml` sets it as the health check path; a
service created by hand needs the same path in its Render settings. The sidebar's **About this deployment** panel shows the deployed
commit (from Render's `RENDER_GIT_COMMIT`), the Python and library versions, and the memory the app process is using, so the hosted
figure can be read from the live app after a deploy.
