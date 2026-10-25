import {
  Alert,
  Box,
  Link,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { cashService } from '../../../../api/services/cashService';
import type {
  CashReconciliationDayDto,
  CashReconciliationDto,
  StaffDto,
} from '../../../../api/types';
import type { ReconciliationFigure } from '../../../../api/custodyTypes';
import { ExportMenu } from '../../../../components/data/ExportMenu';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../../components/feedback/EmptyState';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { formatDate, isIsoDate, todayIsoDate } from '../../../../utils/dates';
import { CURRENCY_FILTER_OPTIONS } from '../../shared/financeDisplay';
import { StaffFilter } from '../../shared/financePickers';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';
import { TransactionsDrawer, type DrillDown } from './TransactionsDrawer';

/** The reconciliation identity (acceptance §10 #8), as computed by the server per tenant-local day. */
export const RECONCILIATION_FORMULA =
  'Opening + floats + collections + transfers received − transfers sent − approved cash expenses − confirmed remittances ± approved adjustments − written off = outstanding';

/** The same identity while the tenant switches the cash custody controls off (no transfers, adjustments or write-offs). */
export const RECONCILIATION_FORMULA_BASIC =
  'Opening + floats + collections − approved cash expenses − confirmed remittances = outstanding';

/** The formula the tenant's cash custody setting uses (basic while the controls are off). */
export function ReconciliationFormula() {
  return useCapabilityEnabled(CAPABILITY.cashCustody)
    ? RECONCILIATION_FORMULA
    : RECONCILIATION_FORMULA_BASIC;
}

/** Figures of the cash custody controls (DEC-030): not shown while CASH_CUSTODY is off. */
const CONTROL_FIGURES: ReadonlySet<keyof CashReconciliationDayDto> = new Set([
  'transfers_in',
  'transfers_out',
  'adjustments',
  'written_off',
  'in_transit_out',
  'in_transit_in',
  'pending_floats',
  'pending_adjustments',
]);
const shown = (controlsOn: boolean, figure: keyof CashReconciliationDayDto) =>
  controlsOn || !CONTROL_FIGURES.has(figure);

type Day = CashReconciliationDayDto;
/** Opens the transactions behind a figure of a day (every figure drills down). */
export type OnFigure = (day: string, figure: ReconciliationFigure) => void;

/** A figure, as a button that opens its transactions when drill-down is available. */
function Figure({
  value,
  currency,
  strong = false,
  label,
  onOpen,
}: {
  value: string;
  currency: string;
  strong?: boolean;
  label: string;
  onOpen?: (() => void) | undefined;
}) {
  const money = <MoneyText amount={value} currency={currency} strong={strong} />;
  if (onOpen === undefined) return money;
  return (
    <Link
      component="button"
      type="button"
      underline="hover"
      color="inherit"
      onClick={onOpen}
      aria-label={`${label}: show the transactions`}
      sx={{ fontVariantNumeric: 'tabular-nums' }}
    >
      {money}
    </Link>
  );
}

/** Outstanding calculation lines: sign, figure, label. */
const LINES: readonly [string, ReconciliationFigure, string][] = [
  ['+', 'floats_issued', 'Floats issued'],
  ['+', 'collections', 'Cash collections'],
  ['+', 'transfers_in', 'Transfers received'],
  ['−', 'transfers_out', 'Transfers sent'],
  ['−', 'approved_spending', 'Approved cash expenses'],
  ['−', 'verified_handovers', 'Confirmed remittances'],
  ['±', 'adjustments', 'Approved adjustments'],
  ['−', 'written_off', 'Written off'],
];

/** Claims and items in flight, never counted in the outstanding until confirmed. */
const PENDING: readonly [ReconciliationFigure, string][] = [
  ['claimed_unverified_handovers', 'Remittances awaiting confirmation'],
  ['pending_spending', 'Cash expenses pending approval'],
  ['unverified_collections', 'Collections not yet verified (included above)'],
  ['in_transit_out', 'Sent, not yet acknowledged (still held)'],
  ['in_transit_in', 'Incoming, not yet acknowledged'],
  ['pending_floats', 'Floats awaiting acknowledgement'],
  ['pending_adjustments', 'Adjustments awaiting decision'],
];

export function FormulaCard({
  day: d,
  currency,
  onFigure,
}: {
  day: Day;
  currency: string;
  onFigure?: OnFigure | undefined;
}) {
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const open = (f: ReconciliationFigure) =>
    onFigure === undefined
      ? undefined
      : () => {
          onFigure(d.day, f);
        };
  return (
    <Paper
      variant="outlined"
      className="p-4"
      component="section"
      aria-label={`Reconciliation ${d.day}`}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {formatDate(d.day)} — closing accountability
      </Typography>
      <Box className="flex flex-wrap gap-8">
        <Table
          size="small"
          sx={{ width: 'auto', minWidth: 340 }}
          aria-label="Outstanding calculation"
        >
          <TableBody>
            <TableRow>
              <TableCell sx={{ width: 24 }} />
              <TableCell>Opening cash</TableCell>
              <TableCell align="right">
                <MoneyText amount={d.opening} currency={currency} />
              </TableCell>
            </TableRow>
            {LINES.filter(([, figure]) => shown(controlsOn, figure)).map(
              ([sign, figure, label]) => (
                <TableRow key={figure}>
                  <TableCell sx={{ width: 24 }}>{sign}</TableCell>
                  <TableCell>{label}</TableCell>
                  <TableCell align="right">
                    <Figure
                      value={d[figure]}
                      currency={currency}
                      label={label}
                      onOpen={open(figure)}
                    />
                  </TableCell>
                </TableRow>
              ),
            )}
            <TableRow>
              <TableCell>=</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Outstanding</TableCell>
              <TableCell align="right" data-testid="outstanding">
                <MoneyText amount={d.outstanding} currency={currency} strong />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Table size="small" sx={{ width: 'auto', minWidth: 340 }} aria-label="Not yet verified">
          <TableBody>
            <TableRow>
              <TableCell colSpan={2}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Claims not yet counted (shown separately)
                </Typography>
              </TableCell>
            </TableRow>
            {PENDING.filter(([figure]) => shown(controlsOn, figure)).map(([figure, label]) => (
              <TableRow key={figure}>
                <TableCell>{label}</TableCell>
                <TableCell align="right">
                  <Figure
                    value={d[figure]}
                    currency={currency}
                    label={label}
                    onOpen={open(figure)}
                  />
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>
                Outstanding if claimed remittances are confirmed
              </TableCell>
              <TableCell align="right" data-testid="outstanding-if-verified">
                <MoneyText amount={d.outstanding_if_claims_verified} currency={currency} strong />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Box>
    </Paper>
  );
}

/** Day-table columns: header and the figure behind it (null = derived, not drillable). */
const COLUMNS: readonly [string, keyof Day, ReconciliationFigure | null][] = [
  ['Opening', 'opening', null],
  ['+ Floats', 'floats_issued', 'floats_issued'],
  ['+ Collections', 'collections', 'collections'],
  ['+ Transfers in', 'transfers_in', 'transfers_in'],
  ['− Transfers out', 'transfers_out', 'transfers_out'],
  ['− Approved expenses', 'approved_spending', 'approved_spending'],
  ['− Confirmed remittances', 'verified_handovers', 'verified_handovers'],
  ['± Adjustments', 'adjustments', 'adjustments'],
  ['− Written off', 'written_off', 'written_off'],
  ['= Outstanding', 'outstanding', null],
  [
    'Remittances awaiting confirmation',
    'claimed_unverified_handovers',
    'claimed_unverified_handovers',
  ],
  ['Pending expenses', 'pending_spending', 'pending_spending'],
  ['Unverified collections', 'unverified_collections', 'unverified_collections'],
  ['In transit (sent)', 'in_transit_out', 'in_transit_out'],
  ['Outstanding if claims confirmed', 'outstanding_if_claims_verified', null],
];

function DaysTable({ data, onFigure }: { data: CashReconciliationDto; onFigure: OnFigure }) {
  const c = data.currency;
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const columns = COLUMNS.filter(([, key]) => shown(controlsOn, key));
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Daily reconciliation">
        <TableHead>
          <TableRow>
            <TableCell>Day</TableCell>
            {columns.map(([h]) => (
              <TableCell key={h} align="right">
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {data.days.map((d) => (
            <TableRow key={d.day}>
              <TableCell>{formatDate(d.day)}</TableCell>
              {columns.map(([h, key, figure]) => (
                <TableCell key={h} align="right">
                  <Figure
                    value={d[key]}
                    currency={c}
                    strong={key === 'outstanding'}
                    label={`${formatDate(d.day)} ${h}`}
                    onOpen={
                      figure === null
                        ? undefined
                        : () => {
                            onFigure(d.day, figure);
                          }
                    }
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

interface ReconciliationTabProps {
  supervisor: StaffDto | null;
  onSupervisorChange: (s: StaffDto | null) => void;
  timeZone?: string;
}

/** Daily cash reconciliation per supervisor and currency; every figure comes from the API. */
export function ReconciliationTab({
  supervisor,
  onSupervisorChange,
  timeZone = 'UTC',
}: ReconciliationTabProps) {
  const [drill, setDrill] = useState<DrillDown | null>(null);
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const [from, setFrom] = useState(() => dayjs().subtract(6, 'day').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const [currency, setCurrency] = useState('');
  const staffId = supervisor?.id ?? '';
  const valid = isIsoDate(from) && isIsoDate(to) && from <= to;
  const load = useCallback(
    (signal: AbortSignal) =>
      cashService.reconciliation(
        { staffMemberId: staffId, from, to, currency: currency || undefined },
        signal,
      ),
    [staffId, from, to, currency],
  );
  const res = useAsyncResource(load, [], staffId !== '' && valid);
  useLiveRefresh([ENTITY.cashHandover, ENTITY.customerPayment, ENTITY.expense], res.reload);
  return (
    <Box className="flex flex-col gap-3">
      <Alert severity="info">
        <strong>
          <ReconciliationFormula />.
        </strong>{' '}
        Remittances awaiting confirmation
        {controlsOn ? ', transfers not yet acknowledged' : ''} and expenses pending approval never
        reduce accountability until confirmed; they are listed separately. Select any figure to see
        the transactions behind it.
      </Alert>
      <Box className="flex flex-wrap items-center gap-3">
        <Box sx={{ minWidth: 260 }}>
          <StaffFilter
            label="Custodian"
            placeholder="Choose a custodian"
            value={supervisor}
            onChange={onSupervisorChange}
          />
        </Box>
        <TextField
          size="small"
          type="date"
          label="From"
          value={from}
          onChange={(e) => {
            setFrom(e.target.value);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="To"
          value={to}
          onChange={(e) => {
            setTo(e.target.value);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <StaticSelectFilter
          label="Currency"
          value={currency}
          options={CURRENCY_FILTER_OPTIONS}
          allLabel="Tenant base currency"
          onChange={setCurrency}
        />
        <Box className="flex-1" />
        <ExportMenu
          reports={[
            {
              code: 'cash',
              filters: valid ? { from, to, currency, staff_member_id: supervisor?.id } : {},
            },
          ]}
        />
      </Box>
      {!valid && <Alert severity="error">Choose a valid period (from must not be after to).</Alert>}
      {supervisor === null ? (
        <EmptyState title="Choose a custodian" description="Reconciliation is per custodian." />
      ) : (
        <AsyncContent resource={res} errorTitle="Could not load the reconciliation">
          {(data) => {
            const last = data.days[data.days.length - 1];
            const onFigure: OnFigure = (day, figure) => {
              setDrill({
                staffMemberId: data.staff_member_id,
                from: day,
                to: day,
                currency: data.currency,
                figure,
              });
            };
            return (
              <Box className="flex flex-col gap-3">
                <Typography variant="body2" color="text.secondary">
                  {data.currency} · days in the tenant’s time zone ({data.timezone})
                </Typography>
                {last !== undefined && (
                  <FormulaCard day={last} currency={data.currency} onFigure={onFigure} />
                )}
                <DaysTable data={data} onFigure={onFigure} />
              </Box>
            );
          }}
        </AsyncContent>
      )}
      {drill !== null && (
        <TransactionsDrawer
          drill={drill}
          timeZone={timeZone}
          onClose={() => {
            setDrill(null);
          }}
        />
      )}
    </Box>
  );
}
