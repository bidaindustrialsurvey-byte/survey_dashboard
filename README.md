# Survey of Industries dashboard

Files
- index.html: the dashboard (login, 3D/2D Bangladesh map, 2D/3D charts, text editor)
  Map boundaries: geoBoundaries (CC BY 4.0), dissolved to divisions
- scripts/fetch_kobo.py: pulls Kobo submissions and writes data.json (counts only)
- scripts/make_user.py: creates password hashes for new accounts
- .github/workflows/update-data.yml: runs the fetch script every 30 minutes

Until data.json exists, the dashboard shows demo figures and a "Demo data" badge.

## Sign-in
One account: SANEM, password 12345. Change it before sharing the link
(run `python scripts/make_user.py` and paste the new line into index.html).

## Setup
1. Edit the FIELDS and WORKFORCE blocks at the top of scripts/fetch_kobo.py so they
   match the question names in your XLSForm.
2. Create a private GitHub repository and upload everything in this folder
   (keep the .github folder).
3. Repository > Settings > Secrets and variables > Actions > New repository secret:
   KOBO_TOKEN, KOBO_ASSET_UID, and KOBO_SERVER (https://kf.kobotoolbox.org or
   https://eu.kobotoolbox.org).
4. Actions tab > "Update dashboard data" > Run workflow. Check that data.json appears.
5. Cloudflare dashboard > Workers & Pages > Create > Pages > Connect to Git.
   Pick the repository, framework preset "None", build command empty,
   output directory "/". You get a link like https://soi-dashboard.pages.dev.
   Every data.json commit redeploys automatically.
6. Change the password with `python scripts/make_user.py`.

## About the login
The sign-in screen runs in the browser. It keeps casual visitors out, but someone
technical can bypass it and can open data.json directly. data.json holds only
aggregated counts, which limits the risk.

For real access control, add Cloudflare Access (Zero Trust, free up to 50 users):
Zero Trust > Access > Applications > Add > Self-hosted, enter the pages.dev domain,
and allow the team's email addresses. Visitors then get a one-time code by email
before the page or data.json loads at all.

## Changing text on the page
1. Sign in and press "Edit text". Outlined text can be clicked and retyped.
   "Edit sign-in page" lets you change the sign-in screen too.
2. Changes save in your browser straight away, but other people will not see them yet.
3. To make them permanent for everyone, press "Copy text settings", open index.html,
   find the line `const TEXT = {};` and paste over it. Commit the file.
