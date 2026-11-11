import { Box, Button, Link, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { PettyCashFundDto } from '../../../api/pettyCashTypes';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { pettyCashFundPath } from '../../../navigation/pettyCashRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { pettyCashService } from '../../../api/services/pettyCashService';
import { RecordExpenseDialog } from '../expenses/RecordExpenseDialog';
import { useFundActions } from '../finance/pettyCash/pettyCashActions';
import { usePettyCashPolicy } from '../finance/pettyCash/pettyCashState';
import { MovementsTab } from '../finance/pettyCash/PettyCashTabs';
import { AdvancesTab, CountsTab, HolderChangesTab } from '../finance/pettyCash/RecordTabs';

type TabKey = 'received' | 'changes' | 'returns' | 'counts' | 'advances';

/** One fund the caller holds: balance, available to spend and the holder's commands. */
function FundCard({
  fund: f,
  actions,
  onExpense,
  canExpense,
}: {
  fund: PettyCashFundDto;
  actions: ReturnType<ReturnType<typeof useFundActions>['actionsFor']>;
  onExpense: () => void;
  canExpense: boolean;
}) {
  const b = f.balance;
  const c = f.currency;
  return (
    <Paper variant="outlined" className="p-3">
      <Stack spacing={1}>
        <Box className="flex flex-wrap items-center justify-between gap-2">
          <Typography variant="h6" component="h2">
            <Link component={RouterLink} to={pettyCashFundPath(f.id)}>
              {f.code} · {f.name}
            </Link>
          </Typography>
          <Box className="flex flex-wrap gap-2">
            {canExpense && f.is_active && (
              <Button variant="contained" onClick={onExpense}>
                Record an expense
              </Button>
            )}
          </Box>
        </Box>
        {b != null && (
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Balance', value: <MoneyText amount={b.balance} currency={c} strong /> },
              {
                label: 'Available to spend',
                value: <MoneyText amount={b.available_to_spend} currency={c} strong />,
              },
              {
                label: 'Approved limit',
                value: <MoneyText amount={b.approved_limit} currency={c} />,
              },
              {
                label: 'Spending waiting for approval',
                value: <MoneyText amount={b.pending_spending} currency={c} />,
              },
              {
                label: 'Handed to you, not yet confirmed',
                value: <MoneyText amount={b.awaiting_acknowledgement} currency={c} />,
              },
              {
                label: 'Returns waiting for the office',
                value: <MoneyText amount={b.returns_claimed} currency={c} />,
              },
            ]}
          />
        )}
        {b?.below_low_balance === true && (
          <Typography variant="body2" color="warning.main">
            Running low: request a top-up.
          </Typography>
        )}
        <ActionButtons actions={actions.filter((a) => a.key !== 'view')} primaryKey="request" />
      </Stack>
    </Paper>
  );
}

/**
 * Field work → Petty cash (DEC-033): the funds the caller holds, with balance and available to
 * spend; record an expense paid from a fund, confirm or dispute money received, request a top-up,
 * return money, record a count and take over a fund handed to them.
 */
export function FieldPettyCashPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const policy = usePettyCashPolicy();
  const canExpense = useCanMutate(PERMISSIONS.tenantExpenseWrite);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const load = useCallback((signal: AbortSignal) => pettyCashService.myFunds(signal), []);
  const res = useAsyncResource(load, [reloadKey]);
  const ids = new Set((res.data ?? []).map((f) => f.id));
  const holds = (fundId: string) => ids.has(fundId);
  const { actionsFor, dialogs } = useFundActions({ holds, onChanged: reload });
  const [expenseFund, setExpenseFund] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>('received');
  const common = { timeZone, holds, reloadKey, onChanged: reload };
  return (
    <>
      <PageHeader
        title="My petty cash"
        subtitle="The funds you hold, what you can spend, and money to confirm"
      />
      <Stack spacing={2}>
        <AsyncContent
          resource={res}
          isEmpty={(funds) => funds.length === 0}
          emptyTitle="You hold no petty cash fund"
          emptyDescription="When the office gives you a fund, or hands one over to you, it appears here."
          errorTitle="Could not load your petty cash"
        >
          {(funds) => (
            <Stack spacing={2}>
              {funds.map((f) => (
                <FundCard
                  key={f.id}
                  fund={f}
                  actions={actionsFor(f)}
                  canExpense={canExpense}
                  onExpense={() => {
                    setExpenseFund(f.id);
                  }}
                />
              ))}
            </Stack>
          )}
        </AsyncContent>
        <Paper variant="outlined">
          <Tabs
            value={tab}
            variant="scrollable"
            aria-label="My petty cash records"
            onChange={(_e, v: TabKey) => {
              setTab(v);
            }}
          >
            <Tab value="received" label="Money to you" />
            <Tab value="changes" label="Funds handed to you" />
            <Tab value="returns" label="Returns" />
            <Tab value="counts" label="Counts" />
            {policy?.advancesEnabled === true && <Tab value="advances" label="Advances" />}
          </Tabs>
          <Box className="p-3">
            {tab === 'received' && (
              <MovementsTab {...common} group="fundings" initialStatus="ISSUED" />
            )}
            {tab === 'changes' && <HolderChangesTab {...common} initialStatus="PENDING" />}
            {tab === 'returns' && <MovementsTab {...common} group="returns" />}
            {tab === 'counts' && <CountsTab {...common} />}
            {tab === 'advances' && <AdvancesTab {...common} />}
          </Box>
        </Paper>
      </Stack>
      {dialogs}
      {expenseFund !== null && (
        <RecordExpenseDialog
          variant="field"
          pettyCashFundId={expenseFund}
          timeZone={timeZone}
          onClose={() => {
            setExpenseFund(null);
          }}
          onRecorded={(e) => {
            notify.success(
              e.status === 'APPROVED'
                ? 'Expense recorded and approved under the policy limit.'
                : 'Expense recorded; it is waiting for approval.',
            );
            reload();
          }}
        />
      )}
    </>
  );
}
