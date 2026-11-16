/** Oversight paths (DEC-031 Phase 5): backend menus tenant.scorecard / .idle_machines. */
export const OVERSIGHT_ROUTES = {
  scorecard: '/tenant/scorecard',
  scorecardPerson: '/tenant/scorecard/:staffId',
  idleMachines: '/tenant/idle-machines',
} as const;

/** Paths with a page in this build (merged into IMPLEMENTED_PATHS). */
export const OVERSIGHT_MENU_PATHS: readonly string[] = [
  OVERSIGHT_ROUTES.scorecard,
  OVERSIGHT_ROUTES.idleMachines,
];

const withFilters = (base: string, filters: Readonly<Record<string, string | undefined>>) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v !== undefined && v !== '') q.set(k, v);
  const qs = q.toString();
  return qs === '' ? base : `${base}?${qs}`;
};

/** One person's scorecard for the same period (`day_from` / `day_to`) and optionally one item. */
export function scorecardPersonPath(
  staffId: string,
  filters: Readonly<Record<string, string | undefined>> = {},
): string {
  return withFilters(`${OVERSIGHT_ROUTES.scorecard}/${encodeURIComponent(staffId)}`, filters);
}
