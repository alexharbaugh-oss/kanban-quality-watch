# Kanban Quality Watch

Cross-references your Jira production pipeline with Ion quality data to flag parts with quality history before they hit the tool.

## How to deploy (Streamlit Community Cloud)

1. Create a new repo on GitHub (or add to your existing repo)
2. Upload these files:
   - `app.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
3. Go to [share.streamlit.io](https://share.streamlit.io)
4. Connect your GitHub repo
5. Set main file to `app.py`
6. Deploy

## How to use

1. Export quality issues from Ion as CSV (you can upload multiple files)
2. Export your Jira Kanban board as CSV
3. Upload both in the sidebar
4. Dashboard auto-generates the quality watch

## Severity levels

- **RED**: 2+ scrap events on the part number. Stop and plan before layup.
- **ORANGE**: 1 scrap event, or 3+ total issues. Extra eyes needed.
- **YELLOW**: 1-2 issues, no scrap. Watch list.
- **CLEAN**: No quality history. Standard process.

## Pipeline stages tracked

Ready to Schedule > Scheduled > Material Cutting > Ready to Layup > Layup > Ready to Cure
