import { Link, Paper, Stack, Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import type { LookupMatchDto } from '../../../api/custodyTypes';
import { accountabilityService } from '../../../api/services/accountabilityService';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { hoursText } from '../hours/hoursDisplay';
import { machineText, nameOr } from '../shared/names';
import { PersonName } from '../shared/PersonName';

/** What is still outstanding on a record, in money or hours. */
function balanceItems(m: LookupMatchDto): KeyValueItem[] {
  const items: KeyValueItem[] = [];
  if (m.balance_outstanding != null) {
    items.push({
      label: 'Balance outstanding',
      value:
        m.balance_unit !== 'HOURS' && m.currency != null ? (
          <MoneyText amount={m.balance_outstanding} currency={m.currency} strong />
        ) : (
          hoursText(m.balance_outstanding)
        ),
    });
  }
  if (m.hours_remaining != null) {
    items.push({ label: 'Hours remaining', value: hoursText(m.hours_remaining) });
  }
  return items;
}

function partyItems(m: LookupMatchDto): KeyValueItem[] {
  const items: KeyValueItem[] = [];
  if (m.customer_id != null) {
    items.push({ label: 'Customer', value: nameOr(m.customer_name, m.customer_id) });
  }
  if (m.machine_id != null) {
    items.push({
      label: 'Machine',
      value: machineText(m.machine_code, m.machine_name, m.machine_id),
    });
  }
  if (m.staff_member_id != null) {
    items.push({ label: 'Staff member', value: nameOr(m.staff_member_name, m.staff_member_id) });
  }
  return items;
}

function Match({ match: m, timeZone }: { match: LookupMatchDto; timeZone: string }) {
  const title = m.reference ?? humanize(m.record_type);
  const when = (at: string | null | undefined) =>
    at == null ? '—' : formatInstantIn(at, timeZone);
  return (
    <Paper variant="outlined" className="p-3" component="article" aria-label={title}>
      <Typography variant="subtitle1" component="h2">
        {m.route === null ? (
          title
        ) : (
          <Link component={RouterLink} to={m.route}>
            {title}
          </Link>
        )}
      </Typography>
      <Typography variant="body2" color="text.secondary" className="mb-2">
        {humanize(m.record_type)}
        {m.status !== null && ` · ${humanize(m.status)}`}
      </Typography>
      <KeyValueGrid
        columns={3}
        items={[
          {
            label: 'Recorded by',
            value: <PersonName userId={m.recorded_by ?? null} name={m.recorded_by_name ?? null} />,
          },
          { label: 'Recorded', value: when(m.recorded_at) },
          {
            label: 'Decided by',
            value: <PersonName userId={m.decided_by ?? null} name={m.decided_by_name ?? null} />,
          },
          { label: 'Decided', value: when(m.decided_at) },
          ...(m.amount != null && m.currency != null
            ? [{ label: 'Amount', value: <MoneyText amount={m.amount} currency={m.currency} /> }]
            : []),
          ...partyItems(m),
          ...balanceItems(m),
        ]}
      />
    </Paper>
  );
}

/** Results of the top-bar "Find a reference" box: what happened, when, who, what is left. */
export function LookupResultsPage() {
  const [params] = useSearchParams();
  const reference = (params.get('reference') ?? '').trim();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    (signal: AbortSignal) => accountabilityService.lookup(reference, signal),
    [reference],
  );
  const res = useAsyncResource(load, [reference], reference !== '');
  return (
    <>
      <PageHeader
        title="Find a reference"
        {...(reference === '' ? {} : { subtitle: `Results for "${reference}"` })}
      />
      {reference === '' ? (
        <EmptyState title="Enter a reference in the box at the top of the page" />
      ) : (
        <AsyncContent
          resource={res}
          loadingLabel="Searching"
          errorTitle="Could not look that up"
          isEmpty={(r) => r.matches.length === 0}
          emptyTitle="No record has that reference"
        >
          {(r) => (
            <Stack spacing={2}>
              {r.matches.map((m) => (
                <Match key={`${m.record_type}-${m.id}`} match={m} timeZone={timeZone} />
              ))}
            </Stack>
          )}
        </AsyncContent>
      )}
    </>
  );
}
