# Survey of Industries dashboard

Live field dashboard for the BIDA/ADB/SANEM Survey of Industries in Bangladesh.

## Files
- `index.html` — the dashboard (login, 3D/2D Bangladesh map, 2D/3D charts, text editor)
- `scripts/fetch_kobo.py` — pulls Kobo submissions and writes `data.json` (aggregates only)
- `scripts/make_user.py` — creates password hashes for new accounts
- `.github/workflows/update-data.yml` — runs the fetch script every 30 minutes

Until `data.json` exists, the dashboard shows demo figures with a "Demo data" badge.

## Sign-in
One account: **SANEM**, default password **12345**.
Change it before sharing the link.

## Setup

### 1. Kobo credentials
- Server: **Global** → `https://kf.kobotoolbox.org`
- API Token: Kobo → Account Settings → Security → API Token
- Asset UID: the `aXXXXXXXXXXXXXXX` part of your form's URL

### 2. GitHub repository
1. Create a **private** repo
2. Upload everything in this folder (keep the `.github` folder)
3. **Settings → Secrets and variables → Actions → New repository secret**:
   - `KOBO_TOKEN` = your API token
   - `KOBO_ASSET_UID` = your form's asset UID
   *(no `KOBO_SERVER` needed — it's set in the workflow)*

### 3. First run
- **Actions** tab → **Update dashboard data** → **Run workflow**
- Watch the log; it prints all available field names (debug mode)
- Check that `data.json` appears in the repo root
- The "Summary" block at the end of the log shows how many labels were matched per chart

### 4. Deploy
- Cloudflare Dashboard → **Workers & Pages → Create → Pages → Connect to Git**
- Pick your repo
- Framework preset: **None**
- Build command: *(empty)*
- Output directory: `/`
- Save and Deploy → you get a `*.pages.dev` link
- Every `data.json` commit auto-redeploys

### 5. (Optional) Real access control
Client-side login only keeps casual visitors out. For real security:
- Zero Trust → Access → Applications → Add → Self-hosted
- Domain: your `*.pages.dev`
- Allow the team's email addresses

## Changing the password
```bash
python scripts/make_user.py