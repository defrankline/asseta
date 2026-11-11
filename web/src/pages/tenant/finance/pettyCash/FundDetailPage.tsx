import { Alert, Box, Link, Tab, Tabs, TextField, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router';
import type {
  PettyCashBalanceDto,
  PettyCashFundDto,
  PettyCashStatementLineDto,
} from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { ExportMenu } from '../../../../components/data/ExportMenu';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../../components/lifecycle/ActiveChip';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { PETTY_CASH_ROUTES, pettyCashEntityPath } from '../../../../navigation/pettyCashRoutes';
import { useSession } from '../../../../session/useSession';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { useFundActions } from './pettyCashActions';
import { FIGURE_LABELS } from './pettyCashDisplay';
import { useMyFunds, usePettyCashPolicy } from './pettyCashState';
import { MovementsTab } from './PettyCashTabs';
import { AdjustmentsTab, AdvancesTab, CountsTab, HolderChangesTab } from './RecordTabs';

const money = (amount: string, currency: string, strong = false) => (
  <MoneyText amount={amount} currency={currency} strong={strong} />
);

/** The ledger now: balance, available to spend and every figure behind them. */
export function BalanceGrid({
  b,
  timeZone,
  advances,
}: {
  b: PettyCashBalanceDto;
  timeZone: string;
  advances: boolean;
}) {
  const c = b.currency;
  const items: KeyValueItem[] = [
    { label: 'Balance', value: money(b.balance, c, true) },
    { label: 'Available to spend', value: money(b.available_to_spend, c, true) },
    { label: 'Approved limit', value: money(b.approved_limit, c) },
    { label: FIGURE_LABELS.funded, value: money(b.funded, c) },
    { label: FIGURE_LABELS.spent, value: money(b.spent, c) },
    { label: FIGURE_LABELS.returned, value: money(b.returned, c) },
    { label: FIGURE_LABELS.adjustments, value: money(b.adjustments, c) },
    { label: FIGURE_LABELS.written_off, value: money(b.written_off, c) },
    { label: FIGURE_LABELS.pending_spending, value: money(b.pending_spending, c) },
    { label: FIGURE_LABELS.awaiting_acknowledgement, value: money(b.awaiting_acknowledgement, c) },
    { label: FIGURE_LABELS.returns_claimed, value: money(b.returns_claimed, c) },
    { label: FIGURE_LABELS.open_return_differences, value: money(b.open_return_differences, c) },
    { label: FIGURE_LABELS.pending_adjustments, value: money(b.pending_adjustments, c) },
    ...(advances
      ? [
          { label: FIGURE_LABELS.advances_issued, value: money(b.advances_issued, c) },
          {
            label: FIGURE_LABELS.advance_change_returned,
            value: money(b.advance_change_returned, c),
          },
          { label: FIGURE_LABELS.advances_outstanding, value: money(b.advances_outstanding, c) },
        ]
      : []),
    {
      label: 'Last count',
      value: b.last_count_at == null ? 'Never' : formatInstantIn(b.last_count_at, timeZone),
    },
    {
      label: 'Next count due',
      value: b.next_count_due_at == null ? '—' : formatInstantIn(b.next_count_due_at, timeZone),
    },
  ];
  return (
    <>
      {b.below_low_balance && (
        <Alert severity="warning">
          This fund is below its low-balance level; consider a top-up.
        </Alert>
      )}
      <KeyValueGrid columns={3} items={items} />
      <Typography variant="caption" color="text.secondary">
        Balance = money received − approved spending − confirmed returns ± approved adjustments −
        written-off differences{advances ? ' − advances + change returned' : ''}. Available to spend
        = balance − spending waiting for approval − returns waiting for the office.
      </Typography>
    </>
  );
}

/** Every movement of the balance in a period, with the running balance. */
export function FundStatement({
  fund,
  timeZone,
  reloadKey,
}: {
  fund: PettyCashFundDto;
  timeZone: string;
  reloadKey: number;
}) {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const load = useCallback(
    (signal: AbortSignal) =>
      pettyCashService.statement(fund.id, { from: from || undefined, to: to || undefined }, signal),
    [fund.id, from, to],
  );
  const res = useAsyncResource(load, [reloadKey]);
  const c = fund.currency;
  const columns: DataColumn<PettyCashStatementLineDto>[] = [
    { id: 'at', header: 'When', render: (l) => formatInstantIn(l.occurred_at, timeZone) },
    { id: 'what', header: 'What', render: (l) => FIGURE_LABELS[l.figure] },
    {
      id: 'ref',
      header: 'Reference',
      render: (l) => {
        const to = pettyCashEntityPath(l.entity_type, l.entity_id);
        const text = l.reference ?? 'Open';
        return to === null ? (
          (l.reference ?? '—')
        ) : (
          <Link component={RouterLink} to={to}>
            {text}
          </Link>
        );
      },
    },
    { id: 'note', header: 'Note', render: (l) => l.note ?? '—' },
    { id: 'in', header: 'In', align: 'right', render: (l) => money(l.money_in, c) },
    { id: 'out', header: 'Out', align: 'right', render: (l) => money(l.money_out, c) },
    {
      id: 'run',
      header: 'Balance',
      align: 'right',
      render: (l) => money(l.running_balance, c, true),
    },
  ];
  return (
    <Box className="flex flex-col gap-2">
      <Box className="flex flex-wrap items-center gap-3">
        <TextField
          type="date"
          size="small"
          label="From"
          value={from}
          onChange={(e) => {
            setFrom(e.target.value);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          type="date"
          size="small"
          label="To"
          value={to}
          onChange={(e) => {
            setTo(e.target.value);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <Box className="flex-1" />
        <ExportMenu
          reports={[{ code: 'petty_cash_statement', filters: { fund_id: fund.id, from, to } }]}
        />
      </Box>
      <AsyncContent
        resource={res}
        loadingLabel="Loading statement"
        errorTitle="Could not load the statement"
      >
        {(s) => (
          <>
            <Typography variant="body2">
              Opening balance on {s.date_from}: {money(s.opening_balance, c, true)} · Closing
              balance on {s.date_to}: {money(s.closing_balance, c, true)}
            </Typography>
            {s.lines.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No movements in this period.
              </Typography>
            ) : (
              <StaticTable
                columns={columns}
                rows={s.lines}
                getRowId={(l) => `${l.entity_type}-${l.entity_id}-${l.figure}-${l.occurred_at}`}
                ariaLabel="Fund statement"
              />
            )}
          </>
        )}
      </AsyncContent>
    </Box>
  );
}

type Related = 'fundings' | 'returns' | 'counts' | 'adjustments' | 'holder-changes' | 'advances';

/** /tenant/finance/petty-cash/funds/:id — the fund, its ledger, statement and records. */
export function FundDetailPage() {
  const { id = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const { hasPermission } = useSession();
  const policy = usePettyCashPolicy();
  const advances = policy?.advancesEnabled === true;
  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback((signal: AbortSignal) => pettyCashService.fund(id, signal), [id]);
  const resource = useAsyncResource(load, [reloadKey]);
  const mine = useMyFunds(reloadKey);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const { actionsFor, dialogs } = useFundActions({ holds: mine.holds, onChanged: reload });
  const [related, setRelated] = useState<Related>('fundings');
  const fund = resource.data;
  const office = hasPermission(
    [
      PERMISSIONS.tenantPettyCashManage,
      PERMISSIONS.tenantPettyCashPropose,
      PERMISSIONS.tenantPettyCashApprove,
    ],
    'any',
  );
  const common = { timeZone, fundId: id, holds: mine.holds, reloadKey, onChanged: reload };
  return (
    <>
      <EntityDetailsLayout
        title={fund === null ? 'Petty cash fund' : `${fund.code} · ${fund.name}`}
        subtitle="Petty cash fund"
        back={
          office
            ? { label: 'Petty cash', to: PETTY_CASH_ROUTES.home }
            : { label: 'My petty cash', to: PETTY_CASH_ROUTES.field }
        }
        {...(fund !== null
          ? {
              status: <ActiveChip active={fund.is_active} />,
              actions: <ActionButtons actions={actionsFor(fund)} primaryKey="propose" />,
            }
          : {})}
        inactive={
          fund !== null && !fund.is_active
            ? {
                title: 'This fund is inactive; nobody can spend from it or fund it.',
                reason: fund.deactivation_reason,
                since:
                  fund.deactivated_at === null
                    ? null
                    : formatInstantIn(fund.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          loadingLabel="Loading fund"
          errorTitle="Could not load the fund"
        >
          {(f) => (
            <>
              {f.pending_holder_change_id != null && (
                <Alert
                  severity="info"
                  action={
                    <Link
                      component={RouterLink}
                      to={`${PETTY_CASH_ROUTES.holderChanges}/${f.pending_holder_change_id}`}
                    >
                      Open
                    </Link>
                  }
                >
                  A holder change is waiting for the new holder;{' '}
                  {f.holder_staff_name ?? 'the current holder'} stays accountable until then.
                </Alert>
              )}
              <DetailSection title="Balance">
                {f.balance == null ? (
                  <Typography variant="body2">No balance available.</Typography>
                ) : (
                  <BalanceGrid b={f.balance} timeZone={timeZone} advances={advances} />
                )}
              </DetailSection>
              <DetailSection title="Statement">
                <FundStatement fund={f} timeZone={timeZone} reloadKey={reloadKey} />
              </DetailSection>
              <DetailSection title="Fund">
                <KeyValueGrid
                  columns={3}
                  items={[
                    { label: 'Code', value: f.code },
                    { label: 'Name', value: f.name },
                    { label: 'Holder', value: f.holder_staff_name ?? '—' },
                    { label: 'Job site', value: f.job_site_name ?? '—' },
                    { label: 'Currency', value: f.currency },
                    { label: 'Approved limit', value: money(f.approved_limit, f.currency) },
                    {
                      label: 'Low-balance level',
                      value:
                        f.low_balance_level == null ? '—' : money(f.low_balance_level, f.currency),
                    },
                    { label: 'Note', value: f.note ?? '—' },
                    {
                      label: 'Created by',
                      value: <PersonName userId={f.created_by} name={f.created_by_name} />,
                    },
                    { label: 'Created', value: formatInstantIn(f.created_at, timeZone) },
                    ...(f.balance?.below_low_balance === true
                      ? [
                          {
                            label: 'Level',
                            value: (
                              <StatusChip
                                status="LOW"
                                tones={{ LOW: 'warning' }}
                                label="Running low"
                              />
                            ),
                          },
                        ]
                      : []),
                  ]}
                />
              </DetailSection>
              <DetailSection title="Records">
                <Tabs
                  value={related}
                  variant="scrollable"
                  aria-label="Fund records"
                  onChange={(_e, v: Related) => {
                    setRelated(v);
                  }}
                >
                  <Tab value="fundings" label="Fundings & top-ups" />
                  <Tab value="returns" label="Returns" />
                  <Tab value="counts" label="Counts" />
                  <Tab value="adjustments" label="Adjustments" />
                  <Tab value="holder-changes" label="Holder changes" />
                  {advances && <Tab value="advances" label="Advances" />}
                </Tabs>
                <Box className="pt-3">
                  {related === 'fundings' && <MovementsTab {...common} group="fundings" />}
                  {related === 'returns' && <MovementsTab {...common} group="returns" />}
                  {related === 'counts' && <CountsTab {...common} />}
                  {related === 'adjustments' && <AdjustmentsTab {...common} />}
                  {related === 'holder-changes' && <HolderChangesTab {...common} />}
                  {related === 'advances' && <AdvancesTab {...common} />}
                </Box>
                <Box className="pt-2">
                  <Link
                    component="button"
                    type="button"
                    onClick={() => {
                      void navigate(
                        `/tenant/expenses?paid_from=PETTY_CASH&petty_cash_fund_id=${encodeURIComponent(f.id)}`,
                      );
                    }}
                  >
                    Expenses paid from this fund
                  </Link>
                </Box>
              </DetailSection>
            </>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
