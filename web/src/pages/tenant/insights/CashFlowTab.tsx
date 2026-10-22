import { Alert, Box, Typography } from '@mui/material';
import type { CashFlowInsightDto, CashFlowWeekDto } from '../../../api/types';
import { MiniBars } from '../../../components/charts/MiniBars';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatMoney } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { insufficientText, TREND_LABELS, TREND_TONES, weekEndingLabel } from './insightsDisplay';

/** Weekly verified receipts less approved expenses, in the tenant currency (money as decimal strings). */
export function CashFlowTab({ flow, timeZone }: { flow: CashFlowInsightDto; timeZone: string }) {
  const money = (amount: string) => <MoneyText amount={amount} currency={flow.currency} />;
  const columns: DataColumn<CashFlowWeekDto>[] = [
    {
      id: 'week',
      header: 'Week',
      render: (w) =>
        `${formatInstantIn(w.week_start, timeZone)} – ${formatInstantIn(w.week_end, timeZone)}`,
    },
    { id: 'receipts', header: 'Receipts', align: 'right', render: (w) => money(w.receipts) },
    { id: 'expenses', header: 'Expenses', align: 'right', render: (w) => money(w.expenses) },
    {
      id: 'net',
      header: 'Net',
      align: 'right',
      render: (w) => <MoneyText amount={w.net} currency={flow.currency} strong />,
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      {flow.status === 'INSUFFICIENT_DATA' ? (
        <Alert severity="info">{insufficientText(flow)}</Alert>
      ) : (
        <Typography variant="body2" color="text.secondary">
          {flow.message}
        </Typography>
      )}
      <KeyValueGrid
        columns={3}
        items={[
          {
            label: 'Trend',
            value:
              flow.trend === null ? (
                '—'
              ) : (
                <StatusChip
                  status={flow.trend}
                  tones={TREND_TONES}
                  label={TREND_LABELS[flow.trend]}
                />
              ),
          },
          {
            label: 'Change in weekly net, per week',
            value:
              flow.trend_per_week === null ? '—' : formatMoney(flow.trend_per_week, flow.currency),
          },
          {
            label: 'Median weekly net',
            value:
              flow.median_weekly_net === null
                ? '—'
                : formatMoney(flow.median_weekly_net, flow.currency),
          },
        ]}
      />
      {flow.weeks.length > 0 && (
        <>
          <MiniBars
            width={Math.min(480, flow.weeks.length * 28)}
            height={64}
            label={`Weekly net cash flow in ${flow.currency}, ${String(flow.weeks.length)} weeks`}
            bars={flow.weeks.map((w) => ({
              key: w.week_end,
              value: Number(w.net),
              title: `${weekEndingLabel(w.week_end, timeZone)}: ${formatMoney(w.net, flow.currency)}`,
            }))}
          />
          <StaticTable
            ariaLabel="Weekly cash flow"
            columns={columns}
            rows={flow.weeks}
            getRowId={(w) => w.week_start}
          />
        </>
      )}
    </Box>
  );
}
