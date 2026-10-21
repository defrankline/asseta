import { Alert, Card, CardContent, Stack, Typography } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { managedServiceService } from '../../../api/services/managedServiceService';
import type { ClientMandateDto, MandateActionDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { CloseMandateForm } from '../../../components/mandate/CloseMandateForm';
import { MandateStaffTable } from '../../../components/mandate/MandateStaffTable';
import { MandateTerms } from '../../../components/mandate/MandateTerms';
import { isOpenMandate } from '../../../components/mandate/mandateUi';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { isMandated } from '../../../session/permissions';
import { useSession } from '../../../session/useSession';
import { formatInstant } from '../../../utils/dates';
import { humanize } from '../../../utils/text';

const actionColumns: DataColumn<MandateActionDto>[] = [
  { id: 'time', header: 'Time', render: (a) => formatInstant(a.occurred_at) },
  { id: 'actor', header: 'Actor', render: (a) => a.actor },
  { id: 'action', header: 'Action', render: (a) => a.action },
  {
    id: 'entity',
    header: 'Entity',
    render: (a) => `${humanize(a.entity_type)} · ${a.entity_id}`,
  },
];

function CardSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          {children}
        </Stack>
      </CardContent>
    </Card>
  );
}

/** The client's view of the managed-service mandate: terms, who has access, what they did. */
export function ClientManagedServicePage() {
  const notify = useNotify();
  const { activeTenant, reload: reloadSession } = useSession();
  // Staff acting under the mandate cannot revoke it themselves (the API refuses: MANDATE_SELF_REVOKE).
  const actingUnderMandate = isMandated(activeTenant);
  const revokeKey = useIdempotencyKey();
  const load = useCallback((signal: AbortSignal) => managedServiceService.get(signal), []);
  const resource = useAsyncResource(load);
  const [updated, setUpdated] = useState<ClientMandateDto | null>(null);
  const shown = { ...resource, data: updated ?? resource.data };

  return (
    <>
      <PageHeader
        title="Managed service"
        subtitle="Asseta staff access to this account under a mandate you consented to"
      />
      <AsyncContent resource={shown} loadingLabel="Loading managed service">
        {({ mandate, recent_actions }) =>
          mandate === null ? (
            <EmptyState
              title="No managed-service mandate"
              description="Asseta staff have no access to this account. A mandate is only granted on your written consent."
            />
          ) : (
            <Stack spacing={3}>
              <CardSection title="Mandate">
                <MandateTerms mandate={mandate} />
              </CardSection>
              <CardSection title="Staff with access">
                <MandateStaffTable assignments={mandate.assignments} />
              </CardSection>
              <CardSection title="Recent actions under this mandate">
                {recent_actions.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    Nothing recorded yet.
                  </Typography>
                ) : (
                  <StaticTable
                    columns={actionColumns}
                    rows={recent_actions}
                    getRowId={(a) => `${a.occurred_at}|${a.action}|${a.entity_id}`}
                    ariaLabel="Recent actions under this mandate"
                  />
                )}
              </CardSection>
              {isOpenMandate(mandate.status) && !actingUnderMandate && (
                <Can permission={PERMISSIONS.tenantManagedServiceRevoke}>
                  <CardSection title="Revoke mandate">
                    <Alert severity="warning">
                      Revoking withdraws all Asseta staff access to this account immediately.
                    </Alert>
                    <CloseMandateForm
                      reasonLabel="Reason for revoking"
                      submitLabel="Revoke mandate"
                      onSubmit={async (reason) => {
                        const body = { version: mandate.version, reason };
                        setUpdated(
                          await managedServiceService.revoke(mandate.id, body, revokeKey(body)),
                        );
                        notify.success(`Mandate ${mandate.reference} revoked.`);
                        // The staff's /me contexts changed: refresh the session in the background.
                        reloadSession();
                      }}
                    />
                  </CardSection>
                </Can>
              )}
            </Stack>
          )
        }
      </AsyncContent>
    </>
  );
}
