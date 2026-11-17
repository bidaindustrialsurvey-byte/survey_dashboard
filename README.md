# Survey of Industries dashboard

Files
- index.html: the dashboard (sign-in, Census/Survey choice, 3D/2D map, charts)
- scripts/fetch_kobo.py: pulls both Kobo projects and writes data.json (Census) and data-survey.json (Survey)
- scripts/fetch_sheet.py: reads the unsuccessful-surveys Google Sheet and writes data-unsuccessful.json (counts only)
- scripts/make_user.py: changes a sign-in password
- .github/workflows/update-data.yml: runs every 30 minutes and on demand
- Map boundaries: geoBoundaries (CC BY 4.0), dissolved to divisions

## Sign-in accounts
- SANEM
- Invest Bangladesh
Change a password with `python scripts/make_user.py`.

## GitHub secrets (Settings > Secrets and variables > Actions)
- KOBO_TOKEN: API key of the Kobo account
- KOBO_ASSET_UID: form ID of the Census project
- KOBO_ASSET_UID_SURVEY: form ID of the Survey project
- UNSUCCESSFUL_SHEET_URL: link to the Google Sheet of unsuccessful surveys

## Google Sheet for unsuccessful surveys
- Each row is one firm that could not be surveyed. The chart counts the "Status" column (e.g. Closed, Not Found).
  Firm names, enumerators and the "Updated Status" notes are never sent to the website.
- Share the sheet as "Anyone with the link: Viewer" and paste its normal link into the secret.
  The link stays inside GitHub; the website only receives counts.
- To count a different column, set UNSUCCESSFUL_REASON_COLUMN in the workflow step's env.
- One tab per status (current setup): UNSUCCESSFUL_TABS in the workflow lists each status and its tab's gid,
  e.g. `Not Found=448647754; Closed=960313769`. Each status is the number of firms (rows with a Company Name)
  in its tab. To add a status, add a tab and add `Name=gid` to the list; the gid is the `#gid=...` part of the
  tab's address. Remove UNSUCCESSFUL_TABS to go back to counting one "Status" column.
