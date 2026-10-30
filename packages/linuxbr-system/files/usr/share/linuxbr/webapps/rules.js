// Pure rules shared by the service worker and regression tests.
export function safeURL(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\s\\\u0000-\u001f]/u.test(value)) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port ||
        !url.hostname.includes('.') || /^[\d.]+$/.test(url.hostname) ||
        /\.(localhost|local|internal|test|invalid)$/.test(url.hostname)) return null;
    url.search = ''; url.hash = '';
    return url;
  } catch { return null; }
}

export function classify(page, metadata, catalog) {
  const url = safeURL(page);
  if (!url) return null;
  const known = catalog.services.find(service => service.hosts.includes(url.hostname));
  if (known) return {name: known.name, url: known.url, origin: new URL(known.url).origin,
    availability: known.availability, source: known.source};
  const manifest = metadata?.manifest;
  const start = safeURL(manifest?.start_url);
  if (!start || start.origin !== url.origin || !['standalone','minimal-ui','fullscreen'].includes(manifest.display) ||
      typeof manifest.name !== 'string' || !manifest.name.trim()) return null;
  return {name: manifest.name.replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,70),
    url: start.href, origin: start.origin, availability:'unknown', source:''};
}

export function shouldNotify(candidate, preferences, now = Date.now()) {
  return preferences.enabled !== false && candidate.availability === 'web' &&
    !candidate.installed && !candidate.native_installed && !preferences.ignored?.[candidate.origin] &&
    now - (preferences.offered?.[candidate.origin] || 0) > 7*24*60*60*1000;
}
