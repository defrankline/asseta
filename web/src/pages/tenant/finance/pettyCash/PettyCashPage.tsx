import Add from '@mui/icons-material/Add';
import { Box, Button, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CanMutate } from '../../../../access/CanMutate';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import {
  pettyCashFundPath,
  pettyCashTabPath,
  type PettyCashTab,
} from '../../../../navigation/pettyCashRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { FundDialog } from './FundDialog';
import { useMyFunds, usePettyCashPolicy } from './pettyCashState';
import { FundsTab, MovementsTab } from './PettyCashTabs';
import { AdjustmentsTab, AdvancesTab, CountsTab, HolderChangesTab } from './RecordTabs';

const TABS: readonly { key: PettyCashTab; label: string }[] = [
  { key: 'funds', label: 'Funds' },
  { key: 'fundings', label: 'Fundings & top-ups' },
  { key: 'returns', label: 'Returns' },
  { key: 'counts', label: 'Counts' },
  { key: 'holder-changes', label: 'Holder changes' },
  { key: 'adjustments', label: 'Adjustments' },
  { key: 'advances', label: 'Advances' },
];

/**
 * Finance → Petty cash (DEC-033): funds with their balances, fundings and top-ups, returns, counts,
 * holder changes, adjustments and (when the tenant's policy switches them on) advances. URL:
 * `?tab=…&status=…`; list routes (`/tenant/finance/petty-cash/movements`, …) open on their tab.
 */
export function PettyCashPage({ tab: fixedTab }: { tab?: PettyCashTab } = {}) {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const policy = usePettyCashPolicy();
  const advancesOn = policy?.advancesEnabled === true;
  const tabs = TABS.filter((t) => t.key !== 'advances' || advancesOn || fixedTab === 'advances');
  const fromUrl = tabs.find((t) => t.key === params.get('tab'))?.key;
  const tab: PettyCashTab = fixedTab ?? fromUrl ?? 'funds';
  const status = params.get('status') ?? undefined;
  const [reloadKey, setReloadKey] = useState(0);
  const mine = useMyFunds(reloadKey);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const [creating, setCreating] = useState(false);
  const changeTab = (v: PettyCashTab) => {
    if (fixedTab === undefined) setParams({ tab: v });
    else void navigate(pettyCashTabPath(v));
  };
  const common = {
    timeZone,
    holds: mine.holds,
    reloadKey,
    onChanged: reload,
    initialStatus: status,
  };
  return (
    <>
      <PageHeader
        title="Petty cash"
        subtitle="Cash boxes with one accountable holder each: balances, money in and out, counts and corrections"
        actions={
          <CanMutate permission={PERMISSIONS.tenantPettyCashManage}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New fund
            </Button>
          </CanMutate>
        }
      />
      <Paper variant="outlined">
        <Tabs
          value={tab}
          variant="scrollable"
          aria-label="Petty cash"
          onChange={(_e, v: PettyCashTab) => {
            changeTab(v);
          }}
        >
          {tabs.map((t) => (
            <Tab key={t.key} value={t.key} label={t.label} />
          ))}
        </Tabs>
        <Box className="p-3">
          {tab === 'funds' && (
            <FundsTab holds={mine.holds} reloadKey={reloadKey} onChanged={reload} />
          )}
          {tab === 'fundings' && <MovementsTab {...common} group="fundings" />}
          {tab === 'returns' && <MovementsTab {...common} group="returns" />}
          {tab === 'counts' && <CountsTab {...common} />}
          {tab === 'holder-changes' && <HolderChangesTab {...common} />}
          {tab === 'adjustments' && <AdjustmentsTab {...common} />}
          {tab === 'advances' && <AdvancesTab {...common} />}
        </Box>
      </Paper>
      {creating && (
        <FundDialog
          onClose={() => {
            setCreating(false);
          }}
          onSaved={(f) => {
            notify.success(`${f.name} created.`);
            void navigate(pettyCashFundPath(f.id));
          }}
        />
      )}
    </>
  );
}
