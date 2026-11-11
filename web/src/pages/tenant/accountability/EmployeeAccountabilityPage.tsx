import { Alert, Box, Chip, Link, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink, useParams, useSearchParams } from 'react-router';
import type { EmployeeAccountabilityDto, EmployeeRecordDto } from '../../../api/custodyTypes';
import { accountabilityService } from '../../../api/services/accountabilityService';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { staffDetailPath } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { scorecardPersonPath } from '../../../navigation/oversightRoutes';
import { pettyCashFundPath } from '../../../navigation/pettyCashRoutes';
import { hoursText } from '../hours/hoursDisplay';
import { PeriodFields } from '../oversight/oversightParts';
import { nameOr } from '../shared/names';
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';

type ListKey =
  | 'collections'
  | 'floats'
  | 'transfers_in'
  | 'transfers_out'
  | 'remittances'
  | 'spending'
  | 'retentions'
  | 'differences'
  | 'custody_adjustments'
  | 'reports_submitted'
  | 'approvals_made'
  | 'adjustments_requested'
  | 'adjustments_decided'
  | 'scorecard_items';

const LISTS: readonly { key: ListKey; label: string }[] = [
  { key: 'collections', label: 'Collections' },
  { key: 'floats', label: 'Floats' },
  { key: 'transfers_in', label: 'Transfers in' },
  { key: 'transfers_out', label: 'Transfers out' },
  { key: 'remittances', label: 'Remittances' },
  { key: 'spending', label: 'Spending' },
  { key: 'retentions', label: 'Retentions' },
  { key: 'differences', label: 'Differences' },
  { key: 'custody_adjustments', label: 'Custody adjustments' },
  { key: 'reports_submitted', label: 'Reports submitted' },
  { key: 'approvals_made', label: 'Approvals made' },
  { key: 'adjustments_requested', label: 'Adjustments requested' },
  { key: 'adjustments_decided', label: 'Adjustments decided' },
  { key: 'scorecard_items', label: 'Scorecard items' },
];

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

function RecordAmount({ r }: { r: EmployeeRecordDto }) {
  if (r.amount == null) return <>—</>;
  if (r.unit === 'HOURS') return <>{hoursText(r.amount)}</>;
  return r.currency == null ? (
    <>{r.amount}</>
  ) : (
    <MoneyText amount={r.amount} currency={r.currency} />
  );
}

function recordColumns(timeZone: string): DataColumn<EmployeeRecordDto>[] {
  return [
    { id: 'at', header: 'When', render: (r) => formatInstantIn(r.occurred_at, timeZone) },
    {
      id: 'ref',
      header: 'Record',
      render: (r) => {
        const label = r.reference ?? humanize(r.record_type);
        return r.route == null ? (
          label
        ) : (
          <Link component={RouterLink} to={r.route}>
            {label}
          </Link>
        );
      },
    },
    { id: 'what', header: 'What', render: (r) => (r.label == null ? '—' : humanize(r.label)) },
    {
      id: 'who',
      header: 'With',
      render: (r) =>
        r.counterparty_staff_id == null
          ? '—'
          : nameOr(r.counterparty_staff_name, r.counterparty_staff_id),
    },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (r.status == null ? '—' : humanize(r.status)),
    },
    { id: 'amount', header: 'Amount', align: 'right', render: (r) => <RecordAmount r={r} /> },
  ];
}

function Identity({ d }: { d: EmployeeAccountabilityDto }) {
  const i = d.identity;
  return (
    <KeyValueGrid
      columns={3}
      items={[
        { label: 'Full name', value: i.full_name },
        { label: 'Kind', value: labelOf(STAFF_KIND_OPTIONS, i.kind) },
        { label: 'Employee code', value: i.employee_code ?? '—' },
        { label: 'Phone', value: i.phone ?? '—' },
        { label: 'Login', value: i.login_email ?? 'Not linked' },
        { label: 'Roles', value: i.roles.length === 0 ? '—' : i.roles.join(', ') },
      ]}
    />
  );
}

function CashHeld({ d }: { d: EmployeeAccountabilityDto }) {
  if (d.cash_held.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Holds no cash.
      </Typography>
    );
  }
  type Held = (typeof d.cash_held)[number];
  const cell = (key: keyof Held, header: string, strong = false): DataColumn<Held> => ({
    id: key,
    header,
    align: 'right',
    render: (b) => <MoneyText amount={b[key]} currency={b.currency} strong={strong} />,
  });
  return (
    <StaticTable
      ariaLabel="Cash held"
      rows={d.cash_held}
      getRowId={(b) => b.currency}
      columns={[
        { id: 'currency', header: 'Currency', render: (b) => b.currency },
        cell('outstanding', 'Held', true),
        cell('in_transit_in', 'In transit in'),
        cell('in_transit_out', 'In transit out'),
        cell('claimed_unverified_handovers', 'Declared, unconfirmed'),
        cell('pending_floats', 'Pending floats'),
        cell('pending_spending', 'Pending spending'),
        cell('approved_retention', 'Approved retention'),
      ]}
    />
  );
}

/** Petty cash funds the person holds now (DEC-033), kept apart from the collections custody above. */
function PettyCashHeld({ d, canOpen }: { d: EmployeeAccountabilityDto; canOpen: boolean }) {
  type Fund = (typeof d.petty_cash_funds)[number];
  const money = (
    key: 'balance' | 'available_to_spend' | 'approved_limit' | 'pending_spending',
    header: string,
    strong = false,
  ): DataColumn<Fund> => ({
    id: key,
    header,
    align: 'right',
    render: (f) => <MoneyText amount={f[key]} currency={f.currency} strong={strong} />,
  });
  return (
    <StaticTable
      ariaLabel="Petty cash held"
      rows={d.petty_cash_funds}
      getRowId={(f) => f.fund_id}
      columns={[
        {
          id: 'fund',
          header: 'Fund',
          render: (f) =>
            canOpen ? (
              <Link component={RouterLink} to={pettyCashFundPath(f.fund_id)}>
                {`${f.fund_code} · ${f.fund_name}`}
              </Link>
            ) : (
              `${f.fund_code} · ${f.fund_name}`
            ),
        },
        money('balance', 'Balance', true),
        money('available_to_spend', 'Available to spend', true),
        money('pending_spending', 'Spending waiting for approval'),
        money('approved_limit', 'Approved limit'),
        {
          id: 'state',
          header: 'State',
          render: (f) =>
            !f.is_active ? 'Inactive' : f.below_low_balance ? 'Running low' : 'Active',
        },
      ]}
    />
  );
}

/** One person: identity, cash held now, and every record behind it over the period (guideline section 10). */
export function EmployeeAccountabilityPage() {
  const { staffId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const [params, setParams] = useSearchParams();
  const [from, setFrom] = useState(() => params.get('date_from') ?? '');
  const [to, setTo] = useState(() => params.get('date_to') ?? '');
  const [listKey, setListKey] = useState<ListKey>('collections');
  const backwards = isDay(from) && isDay(to) && from > to;
  const dateFrom = isDay(from) && !backwards ? from : undefined;
  const dateTo = isDay(to) && !backwards ? to : undefined;
  const load = useCallback(
    (signal: AbortSignal) =>
      accountabilityService.employee(staffId, { date_from: dateFrom, date_to: dateTo }, signal),
    [staffId, dateFrom, dateTo],
  );
  const res = useAsyncResource(load, [staffId, dateFrom, dateTo], staffId !== '');
  const columns = useMemo(() => recordColumns(timeZone), [timeZone]);
  const sync = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (isDay(value)) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <AsyncContent
      resource={res}
      loadingLabel="Loading employee accountability"
      errorTitle="Could not load this employee"
    >
      {(d) => {
        const lists = LISTS.filter((l) => l.key !== 'scorecard_items' || d.scorecard_visible);
        const active = lists.some((l) => l.key === listKey) ? listKey : 'collections';
        const shownTruncated = d.truncated.includes(active);
        return (
          <EntityDetailsLayout
            title={d.identity.full_name}
            subtitle={`${formatDate(d.date_from)} to ${formatDate(d.date_to)}`}
            back={{ label: 'Staff member', to: staffDetailPath(staffId) }}
            status={
              d.identity.is_active ? undefined : (
                <Chip size="small" variant="outlined" label="Inactive" />
              )
            }
            actions={
              hasPermission(PERMISSIONS.tenantOversightScorecardRead) ? (
                <Link
                  component={RouterLink}
                  to={scorecardPersonPath(staffId, { day_from: dateFrom, day_to: dateTo })}
                >
                  Open scorecard
                </Link>
              ) : undefined
            }
          >
            <Box className="flex flex-wrap items-center gap-3">
              <PeriodFields
                from={from}
                to={to}
                onFrom={(v) => {
                  setFrom(v);
                  sync('date_from', v);
                }}
                onTo={(v) => {
                  setTo(v);
                  sync('date_to', v);
                }}
              />
            </Box>
            {backwards && <Alert severity="error">The start of the period is after its end.</Alert>}
            <DetailSection title="Person">
              <Identity d={d} />
            </DetailSection>
            <DetailSection title="Cash held now">
              <CashHeld d={d} />
            </DetailSection>
            {d.petty_cash_funds.length > 0 && (
              <DetailSection title="Petty cash held now">
                <PettyCashHeld d={d} canOpen={hasPermission(PERMISSIONS.tenantPettyCashRead)} />
              </DetailSection>
            )}
            <Paper variant="outlined">
              <Tabs
                value={active}
                variant="scrollable"
                aria-label="Records of this person"
                onChange={(_e, v: ListKey) => {
                  setListKey(v);
                }}
              >
                {lists.map((l) => (
                  <Tab
                    key={l.key}
                    value={l.key}
                    label={`${l.label} (${String(d[l.key].length)})`}
                  />
                ))}
              </Tabs>
              <Stack spacing={1} className="p-3">
                {shownTruncated && (
                  <Alert severity="info">
                    Only the most recent records of this list are shown. Choose a shorter period.
                  </Alert>
                )}
                {d[active].length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    Nothing in this period.
                  </Typography>
                ) : (
                  <StaticTable
                    ariaLabel={LISTS.find((l) => l.key === active)?.label ?? 'Records'}
                    rows={d[active]}
                    getRowId={(r) =>
                      `${r.record_type}-${r.id ?? ''}-${r.occurred_at}-${r.label ?? ''}`
                    }
                    columns={columns}
                  />
                )}
              </Stack>
            </Paper>
          </EntityDetailsLayout>
        );
      }}
    </AsyncContent>
  );
}
