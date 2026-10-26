import { useCallback } from 'react';
import { useParams } from 'react-router';
import { depositAccountService } from '../../../../api/services/depositAccountService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../../components/lifecycle/ActiveChip';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../../navigation/routes';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { DEPOSIT_ACCOUNT_TYPE_LABELS } from './depositAccountForm';
import { useDepositAccountActions } from './useDepositAccountActions';

/** One deposit account: type, masked number, currency, who created it, state and lifecycle actions. */
export function DepositAccountDetailPage() {
  const { accountId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    (signal: AbortSignal) => depositAccountService.get(accountId, signal),
    [accountId],
  );
  const resource = useAsyncResource(load);
  const account = resource.data;
  const { actionsFor, dialogs } = useDepositAccountActions({
    onChanged: resource.reload,
    onReload: resource.reload,
  });
  return (
    <>
      <EntityDetailsLayout
        title={account === null ? 'Deposit account' : account.name}
        subtitle="Company account remittances are paid into"
        back={{ label: 'Deposit accounts', to: ROUTES.tenantDepositAccounts }}
        {...(account !== null
          ? {
              status: <ActiveChip active={account.is_active} />,
              actions: <ActionButtons actions={actionsFor(account)} />,
            }
          : {})}
        inactive={
          account !== null && !account.is_active
            ? {
                title: 'This deposit account is inactive; new remittances cannot name it.',
                reason: account.deactivation_reason,
                since:
                  account.deactivated_at === null
                    ? null
                    : formatInstantIn(account.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the deposit account"
          loadingLabel="Loading deposit account"
        >
          {(a) => (
            <DetailSection title="Account">
              <KeyValueGrid
                columns={3}
                items={[
                  { label: 'Name', value: a.name },
                  { label: 'Type', value: DEPOSIT_ACCOUNT_TYPE_LABELS[a.account_type] },
                  { label: 'Bank or operator', value: a.institution ?? '—' },
                  { label: 'Account number', value: a.account_number_masked ?? '—' },
                  { label: 'Currency', value: a.currency },
                  { label: 'Note', value: a.note ?? '—' },
                  {
                    label: 'Created by',
                    value: <PersonName userId={a.created_by} name={a.created_by_name} />,
                  },
                  { label: 'Created', value: formatInstantIn(a.created_at, timeZone) },
                  { label: 'Updated', value: formatInstantIn(a.updated_at, timeZone) },
                  ...(a.is_active
                    ? []
                    : [
                        {
                          label: 'Deactivated by',
                          value: (
                            <PersonName userId={a.deactivated_by} name={a.deactivated_by_name} />
                          ),
                        },
                      ]),
                ]}
              />
            </DetailSection>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
