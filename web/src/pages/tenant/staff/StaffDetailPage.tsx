import { useCallback } from 'react';
import { useParams } from 'react-router';
import { staffService } from '../../../api/services/staffService';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
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
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';
import { useStaffActions } from './useStaffActions';

/** One staff member: identity, login link, state and lifecycle actions. */
export function StaffDetailPage() {
  const { staffId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback((signal: AbortSignal) => staffService.get(staffId, signal), [staffId]);
  const resource = useAsyncResource(load);
  const staff = resource.data;
  const { actionsFor, dialogs } = useStaffActions({
    onChanged: resource.reload,
    onReload: resource.reload,
  });

  return (
    <>
      <EntityDetailsLayout
        title={staff === null ? 'Staff member' : staff.full_name}
        subtitle="Staff member details"
        back={{ label: 'All staff', to: ROUTES.tenantStaff }}
        {...(staff !== null
          ? {
              status: <ActiveChip active={staff.is_active} />,
              actions: <ActionButtons actions={actionsFor(staff)} />,
            }
          : {})}
        inactive={
          staff !== null && !staff.is_active
            ? {
                title: 'This staff member is inactive.',
                reason: staff.deactivation_reason,
                since:
                  staff.deactivated_at === null
                    ? null
                    : formatInstantIn(staff.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the staff member"
          loadingLabel="Loading staff member"
        >
          {(s) => (
            <DetailSection title="Person">
              <KeyValueGrid
                columns={3}
                items={[
                  { label: 'Full name', value: s.full_name },
                  { label: 'Kind', value: labelOf(STAFF_KIND_OPTIONS, s.kind) },
                  { label: 'Employee code', value: s.employee_code ?? '—' },
                  { label: 'Phone', value: s.phone ?? '—' },
                  {
                    label: 'App login',
                    value: s.keycloak_subject === null ? 'Not linked' : s.keycloak_subject,
                  },
                  { label: 'Version', value: String(s.version) },
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
