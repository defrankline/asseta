const KEY = 'asseta.nav.groups';

/** Per-group expanded/collapsed choice of this viewer (per-browser convenience; may be empty). */
export type NavGroupState = Readonly<Record<string, boolean>>;

export function loadNavGroupState(): NavGroupState {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? '{}');
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter((e): e is [string, boolean] => typeof e[1] === 'boolean'),
    );
  } catch {
    return {};
  }
}

export function storeNavGroupState(state: NavGroupState): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Storage unavailable (private mode); the choice simply is not remembered.
  }
}
