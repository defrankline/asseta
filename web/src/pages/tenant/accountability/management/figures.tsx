import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import type {
  CountFigureDto,
  HoursFigureDto,
  MoneyFigureDto,
  PurchaseQueueDto,
} from '../../../../api/custodyTypes';
import { MoneyText } from '../../../../components/display/MoneyText';
import { formatMoney } from '../../../../utils/money';
import { hoursText } from '../../hours/hoursDisplay';
import { KpiCard, type KpiRow } from '../../dashboard/KpiCard';
import { moneyRows } from './moneyRows';

/** Building blocks of the guideline section 8 dashboard: every figure opens the records behind it. */

/** A headed group of figures. */
export function FigureGroup({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <Box component="section" aria-labelledby={id} data-group={id} className="flex flex-col gap-3">
      <Box>
        <Typography id={id} variant="h6" component="h2">
          {title}
        </Typography>
        {note !== undefined && (
          <Typography variant="body2" color="text.secondary">
            {note}
          </Typography>
        )}
      </Box>
      {children}
    </Box>
  );
}

export function FigureGrid({ children }: { children: ReactNode }) {
  return <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</Box>;
}

const records = (n: number) => `${String(n)} ${n === 1 ? 'record' : 'records'}`;

export function HoursCard({ title, figure }: { title: string; figure: HoursFigureDto }) {
  return (
    <KpiCard
      title={title}
      value={hoursText(figure.hours)}
      valueText={hoursText(figure.hours)}
      to={figure.route}
      description={records(figure.count)}
    />
  );
}

export function CountCard({
  title,
  figure,
  description,
}: {
  title: string;
  figure: CountFigureDto;
  description?: string;
}) {
  return (
    <KpiCard
      title={title}
      value={figure.count}
      valueText={String(figure.count)}
      to={figure.route}
      {...(description !== undefined ? { description } : {})}
    />
  );
}

export function MoneyCard({
  title,
  figure,
  extra = [],
}: {
  title: string;
  figure: MoneyFigureDto;
  extra?: readonly KpiRow[];
}) {
  const [only] = figure.lines;
  const single = figure.lines.length === 1 && only !== undefined;
  return (
    <KpiCard
      title={title}
      value={single ? <MoneyText amount={only.amount} currency={only.currency} /> : figure.count}
      valueText={single ? formatMoney(only.amount, only.currency) : String(figure.count)}
      to={figure.route}
      description={records(figure.count)}
      rows={[...(single ? [] : moneyRows(title, figure)), ...extra]}
    />
  );
}

/** A queue of purchases: how many, the hours waiting, the money still open, the oldest ones. */
export function PurchaseQueueCard({ title, queue }: { title: string; queue: PurchaseQueueDto }) {
  return (
    <KpiCard
      title={title}
      value={queue.count}
      valueText={String(queue.count)}
      to={queue.route}
      description={`${hoursText(queue.hours)} waiting`}
      rows={[
        ...queue.amounts.map((a) => ({
          key: `open-${a.currency}`,
          label: `Still to pay (${a.currency})`,
          value: <MoneyText amount={a.amount} currency={a.currency} />,
          valueText: formatMoney(a.amount, a.currency),
          to: queue.route,
        })),
        ...queue.items.map((p) => ({
          key: p.purchase_id,
          label: `${p.purchase_number ?? 'Purchase'}${p.customer_name != null ? `, ${p.customer_name}` : ''}`,
          value: hoursText(p.hours_awaiting),
          valueText: hoursText(p.hours_awaiting),
          to: p.route,
        })),
      ]}
    />
  );
}
