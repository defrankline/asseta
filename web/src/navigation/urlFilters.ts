/** Deep links into filtered list pages (dashboard cards) and reading those filters on arrival. */

/** `path?key=value&…`, dropping empty values. */
export function withQuery(
  path: string,
  params: Readonly<Record<string, string | null | undefined>>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, value);
  }
  const query = search.toString();
  if (query === '') return path;
  return `${path}${path.includes('?') ? '&' : '?'}${query}`;
}

/**
 * A list filter's initial value from the URL: the parameter when it is one of `allowed`
 * (static option values), else `fallback`. Unknown values are ignored, never sent to the API.
 */
export function initialFilter(
  params: URLSearchParams,
  key: string,
  allowed: readonly (string | { value: string })[],
  fallback: string,
): string {
  const raw = params.get(key);
  if (raw === null) return fallback;
  if (raw === '') return '';
  const values = allowed.map((a) => (typeof a === 'string' ? a : a.value));
  return values.includes(raw) ? raw : fallback;
}
