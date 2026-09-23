/**
 * Saves the dashboard layout to GitHub. Runs on Cloudflare Pages, not in the browser,
 * so the admin password and the GitHub token are never part of the website.
 *
 * Environment variables to set in Cloudflare (Settings > Environment variables):
 *   ADMIN_PASSWORD   the password the editor asks for
 *   GITHUB_TOKEN     a fine-grained token with Contents: Read and write on this repo
 *   GITHUB_REPO      owner/repo, e.g. bidaindustrialsurvey-byte/survey_dashboard
 *   GITHUB_BRANCH    optional, defaults to main
 */
const FILE = 'layout.json';
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });

function toBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

// compare without leaking how much of the password matched
function samePassword(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function onRequestPost({ request, env }) {
  if (!env.ADMIN_PASSWORD) return json({ ok: false, error: 'ADMIN_PASSWORD is not set in Cloudflare' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ ok: false, error: 'Bad request' }, 400); }

  if (!samePassword(body.password || '', env.ADMIN_PASSWORD)) {
    await new Promise(r => setTimeout(r, 600));          // slow down guessing
    return json({ ok: false, error: 'That password is not correct.' }, 401);
  }
  if (body.check) return json({ ok: true });             // password check only

  const layout = body.layout;
  if (!layout || typeof layout !== 'object') return json({ ok: false, error: 'No layout sent' }, 400);
  const text = JSON.stringify(layout, null, 1);
  if (text.length > 200000) return json({ ok: false, error: 'Layout is too large' }, 413);

  if (!env.GITHUB_TOKEN || !env.GITHUB_REPO) {
    return json({ ok: false, error: 'GITHUB_TOKEN or GITHUB_REPO is not set in Cloudflare' }, 500);
  }
  const branch = env.GITHUB_BRANCH || 'main';
  const api = `https://api.github.com/repos/${env.GITHUB_REPO}/contents/${FILE}`;
  const headers = {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'dashboard-editor',
    'Content-Type': 'application/json',
  };

  let sha;
  const current = await fetch(`${api}?ref=${branch}`, { headers });
  if (current.ok) sha = (await current.json()).sha;
  else if (current.status !== 404) {
    return json({ ok: false, error: `GitHub read failed (${current.status})` }, 502);
  }

  const put = await fetch(api, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ message: 'Update dashboard layout', content: toBase64(text), branch, sha }),
  });
  if (!put.ok) {
    const detail = await put.text();
    return json({ ok: false, error: `GitHub save failed (${put.status}): ${detail.slice(0, 120)}` }, 502);
  }
  return json({ ok: true, saved: text.length });
}

export const onRequestGet = () => json({ ok: true, info: 'POST with a password to save the layout.' });
