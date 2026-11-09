const isDay = (v: string | null): v is string => v !== null && /^\d{4}-\d{2}-\d{2}$/.test(v);

/** The `date_from` / `date_to` a dashboard link carries; invalid values are ignored. */
export function urlPeriod(params: URLSearchParams): {
  dateFrom: string | undefined;
  dateTo: string | undefined;
} {
  const from = params.get('date_from');
  const to = params.get('date_to');
  return { dateFrom: isDay(from) ? from : undefined, dateTo: isDay(to) ? to : undefined };
}
