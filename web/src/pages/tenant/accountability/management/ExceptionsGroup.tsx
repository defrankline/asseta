import type { ExceptionsSectionDto } from '../../../../api/custodyTypes';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { MoneyText } from '../../../../components/display/MoneyText';
import { formatMoney } from '../../../../utils/money';
import { formatInstantIn } from '../../../../utils/time';
import { humanize } from '../../../../utils/text';
import { hoursText } from '../../hours/hoursDisplay';
import { machineText, nameOr } from '../../shared/names';
import { KpiCard, type KpiRow } from '../../dashboard/KpiCard';
import { FigureGrid, FigureGroup, HoursCard, MoneyCard } from './figures';
import { moneyRows } from './moneyRows';

const openedRows = (key: string, figure: ExceptionsSectionDto['shortages']): KpiRow[] =>
  moneyRows(key, figure, 'Opened in this period');

/** Guideline section 8, "Exceptions and Investigations". Wording stays neutral. */
export function ExceptionsGroup({ section: s }: { section: ExceptionsSectionDto }) {
  const timeZone = useDisplayTimeZone();
  const kindRows = (rows: ExceptionsSectionDto['outstanding_approvals']['by_kind']): KpiRow[] =>
    rows.map((k) => ({
      key: k.kind,
      label: humanize(k.kind),
      value: k.count,
      valueText: String(k.count),
      to: k.route,
    }));
  const pending = s.pending_adjustments;
  const changeover = s.changeover_jobs_awaiting_approval;
  return (
    <FigureGroup
      id="exceptions"
      title="Exceptions and investigations"
      note="Open queues show the position now, whatever period is chosen."
    >
      <FigureGrid>
        <HoursCard title="Unexplained engine hours" figure={s.unexplained_engine_hours} />
        <MoneyCard
          title="Cash shortages"
          figure={s.shortages}
          extra={openedRows('opened', s.shortages_opened_in_period)}
        />
        <MoneyCard
          title="Cash overages"
          figure={s.overages}
          extra={openedRows('opened', s.overages_opened_in_period)}
        />
        <KpiCard
          title="Pending adjustments"
          value={pending.total}
          valueText={String(pending.total)}
          to={pending.route}
          rows={[
            ...kindRows(pending.by_kind),
            ...pending.oldest.map((p) => ({
              key: p.id,
              label: `${p.reference ?? humanize(p.record_type)}, since ${formatInstantIn(p.requested_at, timeZone)}`,
              value: p.status === '' ? '—' : humanize(p.status),
              valueText: humanize(p.status),
              to: p.route ?? undefined,
            })),
          ]}
        />
        <KpiCard
          title="Refused attempts"
          value={
            s.unauthorized_attempts.permission_denied +
            s.unauthorized_attempts.segregation_of_duties
          }
          valueText={String(
            s.unauthorized_attempts.permission_denied +
              s.unauthorized_attempts.segregation_of_duties,
          )}
          to={s.unauthorized_attempts.route}
          description={`Since ${formatInstantIn(s.unauthorized_attempts.since, timeZone)}`}
          rows={[
            {
              key: 'denied',
              label: 'Missing permission',
              value: s.unauthorized_attempts.permission_denied,
              valueText: String(s.unauthorized_attempts.permission_denied),
              to: s.unauthorized_attempts.route,
            },
            {
              key: 'sod',
              label: 'Own record refused',
              value: s.unauthorized_attempts.segregation_of_duties,
              valueText: String(s.unauthorized_attempts.segregation_of_duties),
              to: s.unauthorized_attempts.route,
            },
          ]}
        />
        <MoneyCard title="Unconfirmed payments" figure={s.unconfirmed_payments} />
        <KpiCard
          title="Outstanding approvals"
          value={s.outstanding_approvals.total}
          valueText={String(s.outstanding_approvals.total)}
          rows={kindRows(s.outstanding_approvals.by_kind)}
        />
        <KpiCard
          title="Overdue reports"
          value={s.overdue_reports.total}
          valueText={String(s.overdue_reports.total)}
          rows={[
            {
              key: 'daily',
              label: 'Missing daily reports',
              value: s.overdue_reports.missing_daily_reports.count,
              valueText: String(s.overdue_reports.missing_daily_reports.count),
              to: s.overdue_reports.missing_daily_reports.route,
            },
            {
              key: 'remit',
              label: 'Remittances overdue today',
              value: s.overdue_reports.remittances_overdue_today.count,
              valueText: String(s.overdue_reports.remittances_overdue_today.count),
              to: s.overdue_reports.remittances_overdue_today.route,
            },
          ]}
        />
        <KpiCard
          title="Unresolved variances"
          value={s.unresolved_variances.total}
          valueText={String(s.unresolved_variances.total)}
          rows={s.unresolved_variances.by_source.flatMap((v) => [
            {
              key: `${v.source}-${v.unit}`,
              label: humanize(v.source),
              value: v.count,
              valueText: String(v.count),
              to: v.route,
            },
            ...v.amounts
              .filter((a) => a.currency !== '')
              .map((a) => ({
                key: `${v.source}-${v.unit}-${a.currency}`,
                label: `${humanize(v.source)} (${a.currency})`,
                value:
                  v.unit === 'HOURS' ? (
                    hoursText(a.amount)
                  ) : (
                    <MoneyText amount={a.amount} currency={a.currency} />
                  ),
                valueText:
                  v.unit === 'HOURS' ? hoursText(a.amount) : formatMoney(a.amount, a.currency),
                to: v.route,
              })),
          ])}
        />
        <KpiCard
          title="Changeover jobs awaiting approval"
          value={changeover.count}
          valueText={String(changeover.count)}
          description={
            changeover.oldest_days === null
              ? 'Hours after a changeover stay unbilled until the job is approved'
              : `Oldest waiting ${String(changeover.oldest_days)} days; hours stay unbilled until approved`
          }
          rows={changeover.items.map((j) => ({
            key: j.job_id,
            label: `${j.job_number ?? 'Job'}, ${nameOr(j.customer_name, j.customer_id)}, ${machineText(j.machine_code, j.machine_name, j.machine_id)}`,
            value: `${String(j.days_waiting)}d`,
            valueText: `${String(j.days_waiting)} days`,
            to: j.route,
          }))}
        />
      </FigureGrid>
    </FigureGroup>
  );
}
