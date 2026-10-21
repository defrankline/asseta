import { parseMode, serializeMode, type ConsoleMode } from './permissions';

const KEY = 'asseta.console.mode';

/** Per-browser convenience only; never trusted for authorization (validated against /me). */
export function loadStoredMode(): ConsoleMode | null {
  try {
    return parseMode(window.localStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export function storeMode(mode: ConsoleMode): void {
  try {
    window.localStorage.setItem(KEY, serializeMode(mode));
  } catch {
    // Storage unavailable (private mode); selection simply is not remembered.
  }
}
