/** `?missing=…` views of the machine list (links from the go-live checklist), filtered by the server. */
export type MissingView = 'tracker' | 'enrollment';

export function missingViewOf(raw: string | null): MissingView | null {
  return raw === 'tracker' || raw === 'enrollment' ? raw : null;
}
