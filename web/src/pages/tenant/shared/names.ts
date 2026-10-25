import { shortId } from './financeDisplay';

/**
 * A record's display name (customer, custodian, site, …) from the DTO's `*_name` field; the short id
 * only when the server could not name it, and an em dash when there is no reference at all.
 */
export function nameOr(name: string | null | undefined, id: string | null | undefined): string {
  if (name != null && name !== '') return name;
  return id == null || id === '' ? '—' : shortId(id);
}

/** `CODE · Name` of a machine from the DTO's `machine_code` / `machine_name`; short id as fallback. */
export function machineText(
  code: string | null | undefined,
  name: string | null | undefined,
  id: string | null | undefined,
): string {
  const parts = [code, name].filter((p): p is string => p != null && p !== '');
  return parts.length > 0 ? parts.join(' · ') : nameOr(null, id);
}
