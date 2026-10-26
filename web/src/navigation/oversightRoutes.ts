/** Oversight paths (DEC-031 Phase 5): backend menus tenant.scorecard / .unbilled_work / .idle_machines /
 * .site_checkins, plus tenant.field.checkin (the supervisor's own check-in page under Field work). */
export const OVERSIGHT_ROUTES = {
  scorecard: '/tenant/scorecard',
  scorecardPerson: '/tenant/scorecard/:staffId',
  unbilledWork: '/tenant/unbilled-work',
  idleMachines: '/tenant/idle-machines',
  siteCheckins: '/tenant/site-checkins',
  siteCheckinDetail: '/tenant/site-checkins/:id',
  /** Backend menu tenant.field.checkin (Field work); also reached from My jobs. */
  fieldCheckin: '/tenant/field/check-in',
} as const;

/** Paths with a page in this build (merged into IMPLEMENTED_PATHS). */
export const OVERSIGHT_MENU_PATHS: readonly string[] = [
  OVERSIGHT_ROUTES.scorecard,
  OVERSIGHT_ROUTES.unbilledWork,
  OVERSIGHT_ROUTES.idleMachines,
  OVERSIGHT_ROUTES.siteCheckins,
  OVERSIGHT_ROUTES.fieldCheckin,
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

export function siteCheckinPath(checkinId: string): string {
  return `${OVERSIGHT_ROUTES.siteCheckins}/${encodeURIComponent(checkinId)}`;
}

/** Site check-ins pre-filtered (e.g. one person and period). */
export function siteCheckinsPath(
  filters: Readonly<Record<string, string | undefined>> = {},
): string {
  return withFilters(OVERSIGHT_ROUTES.siteCheckins, filters);
}
