# Survey of Industries dashboard

Files
- index.html: the dashboard (sign-in, Census/Survey choice, EN/বাং switch, 3D/2D map, charts, text editor)
- scripts/fetch_kobo.py: pulls both Kobo projects and writes data.json (Census) and data-survey.json (Survey)
- .github/workflows/update-data.yml: runs every 30 minutes and on demand
- Map boundaries: geoBoundaries (CC BY 4.0), dissolved to divisions

## Kobo secrets (Settings > Secrets and variables > Actions)
Both projects are in the same Kobo account, so there is one token.
- KOBO_TOKEN: API token of the Kobo account
- KOBO_ASSET_UID: form ID of "Census of Foreign/JV Industries"
- KOBO_ASSET_UID_SURVEY: form ID of "Survey of Industries in Bangladesh 2026"

A form ID is the part after /forms/ in the project's address in Kobo.

## Sign-in
Account SANEM. Change the password with `python scripts/make_user.py`.

## Changing text
Press "Edit text", pick EN or বাং, click outlined text and type. Each language keeps its own wording.
To make changes permanent for everyone, press "Copy text settings" and paste over the
`const TEXT = { en: {}, bn: {} };` line in index.html.
