import { useCallback } from 'react';
import { useParams } from 'react-router';
import { customerService } from '../../../api/services/customerService';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { ContractsPanel } from './ContractsPanel';
import { CustomerFields } from './CustomerViews';
import { customerLabel, useCustomerActions } from './useCustomerActions';

/** Customer record with its contracts; edit, deactivate and reactivate. */
export function CustomerDetailPage() {
  const { customerId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    (signal: AbortSignal) => customerService.get(customerId, signal),
    [customerId],
  );
  const resource = useAsyncResource(load);
  const customer = resource.data;
  const { actionsFor, dialogs } = useCustomerActions({
    onChanged: resource.reload,
    onReload: resource.reload,
  });
  return (
    <>
      <EntityDetailsLayout
        title={customer === null ? 'Customer' : customerLabel(customer)}
        subtitle="Customer details"
        back={{ label: 'All customers', to: ROUTES.tenantCustomers }}
        {...(customer !== null
          ? {
              status: <ActiveChip active={customer.is_active} />,
              actions: <ActionButtons actions={actionsFor(customer)} />,
            }
          : {})}
        inactive={
          customer !== null && !customer.is_active
            ? {
                title:
                  'This customer is inactive: no new contracts or jobs. Its history, balance and statement are kept.',
                reason: customer.deactivation_reason ?? null,
                since:
                  customer.deactivated_at == null
                    ? null
                    : formatInstantIn(customer.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the customer"
          loadingLabel="Loading customer"
        >
          {(c) => (
            <div className="flex flex-col gap-6">
              <DetailSection title="Customer">
                <CustomerFields customer={c} />
              </DetailSection>
              <ContractsPanel key={c.id} customer={c} timeZone={timeZone} />
            </div>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
