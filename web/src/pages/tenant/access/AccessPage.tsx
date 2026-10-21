import { Button, Chip, Stack, Tooltip } from '@mui/material';
import { useCallback, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { tenantAccessService } from '../../../api/services/tenantAccessService';
import type { MemberDto, MemberRoleDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ConfirmDialog } from '../../../components/forms/ConfirmDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstant } from '../../../utils/dates';

interface Revoking {
  member: MemberDto;
  role: MemberRoleDto;
}

/** Whether the role is held by platform staff under a managed-service mandate. */
function mandateRef(role: MemberRoleDto): string | null {
  return role.mandate_reference ?? null;
}

/** Tenant users and their roles. Roles held under a mandate are revoked with the mandate. */
export function AccessPage() {
  const notify = useNotify();
  const keyFor = useIdempotencyKey();
  const load = useCallback((signal: AbortSignal) => tenantAccessService.listMembers(signal), []);
  const resource = useAsyncResource(load);
  const [updated, setUpdated] = useState<MemberDto[] | null>(null);
  const [revoking, setRevoking] = useState<Revoking | null>(null);
  const shown = { ...resource, data: updated ?? resource.data };

  const columns: DataColumn<MemberDto>[] = [
    {
      id: 'user',
      header: 'User',
      render: (m) => (
        <>
          <strong>{m.display_name}</strong>
          <br />
          {m.email}
        </>
      ),
    },
    {
      id: 'roles',
      header: 'Roles',
      render: (m) => (
        <Stack spacing={1}>
          {m.roles.map((r) => {
            const ref = mandateRef(r);
            return (
              <Stack key={r.role_key} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Tooltip title={`Since ${formatInstant(r.since)}`}>
                  <Chip size="small" label={r.role_key} />
                </Tooltip>
                {ref !== null && (
                  <Chip
                    size="small"
                    color="info"
                    variant="outlined"
                    label={`Managed service · ${ref}`}
                  />
                )}
                {ref === null && (
                  <CanMutate permission={PERMISSIONS.tenantAccessManage}>
                    <Button
                      size="small"
                      color="error"
                      aria-label={`Revoke ${r.role_key} from ${m.display_name}`}
                      onClick={() => {
                        setRevoking({ member: m, role: r });
                      }}
                    >
                      Revoke
                    </Button>
                  </CanMutate>
                )}
              </Stack>
            );
          })}
        </Stack>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Users & roles"
        subtitle="Who can sign in to this account and what they can do. Managed-service roles end with their mandate."
      />
      <AsyncContent
        resource={shown}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No users"
        loadingLabel="Loading users"
      >
        {(rows) => (
          <StaticTable
            columns={columns}
            rows={rows}
            getRowId={(m) => m.user_id}
            ariaLabel="Users"
          />
        )}
      </AsyncContent>
      {revoking !== null && (
        <ConfirmDialog
          open
          title="Revoke role"
          message={`${revoking.member.display_name} loses the ${revoking.role.role_key} role.`}
          confirmLabel="Revoke"
          destructive
          onClose={() => {
            setRevoking(null);
          }}
          onConfirm={async () => {
            const { member, role } = revoking;
            const payload = { user: member.user_id, role: role.role_key };
            setUpdated(
              await tenantAccessService.revokeRole(member.user_id, role.role_key, keyFor(payload)),
            );
            notify.success(`Role ${role.role_key} revoked.`);
          }}
        />
      )}
    </>
  );
}
