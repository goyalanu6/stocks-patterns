# stocks (rbr)

This repository contains the RBR/DBD analysis tools and a Streamlit app.

Quick steps to prepare and push to GitHub (Windows PowerShell):

1. Ensure you have Git installed and in PATH: https://git-scm.com/download/win
2. (Optional) Install GitHub CLI `gh` to create a repo from terminal: https://cli.github.com/
3. Initialize, commit and push:

```powershell
git init
git add .
git commit -m "Initial commit"
# create remote via GitHub web or with `gh repo create` and then:
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

4. For Streamlit Community Cloud:
   - Push your repo to GitHub.
   - On https://share.streamlit.io, click "New app", select this repo, branch `main`, and the file to run (e.g., `rbr_app.py`).
   - Add your secrets (DHAN_ACCESS_TOKEN, DHAN_CLIENT_ID) on Streamlit's Secrets page or set environment variables via the UI.

Security notes:
- Never commit `.env` with real tokens. Use `.env.example` to show required keys.
# Dhan API Stock Analysis

## Setup

1. Clone the repository
```bash
git clone <your-repo-url>
cd <repo-directory>
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up environment variables:

Option A: Using `.env` file
```bash
# Copy the example file
cp .env.example .env
# Edit .env with your credentials
```

Option B: Set environment variables directly
```bash
# Linux/Mac
export DHAN_ACCESS_TOKEN="your_access_token"
export DHAN_CLIENT_ID="your_client_id"

# Windows PowerShell
$env:DHAN_ACCESS_TOKEN="your_access_token"
$env:DHAN_CLIENT_ID="your_client_id"
```

4. Run the application
```bash
streamlit run rbr_app.py
```

## Deployment

### GitHub Actions
Add these secrets in your repository settings:
- `DHAN_ACCESS_TOKEN`
- `DHAN_CLIENT_ID`

### Heroku
Set config vars in your app settings:
```bash
heroku config:set DHAN_ACCESS_TOKEN=your_access_token
heroku config:set DHAN_CLIENT_ID=your_client_id
```

### Other Platforms
Configure the following environment variables:
- `DHAN_ACCESS_TOKEN`: Your Dhan API access token
- `DHAN_CLIENT_ID`: Your Dhan client ID
- `DHAN_API_URL`: API endpoint (default: https://api.dhan.co/v2/charts/historical)
- `DHAN_TOKEN_RENEWAL_URL`: Token renewal endpoint (default: https://api.dhan.co/v2/RenewToken)
- `DHAN_EXCHANGE_SEGMENT`: Exchange segment (default: NSE_EQ)
- `DHAN_INSTRUMENT`: Instrument type (default: EQUITY)
- `DHAN_TOKEN_RENEWAL_BUFFER`: Minutes before expiry to renew token (default: 5)