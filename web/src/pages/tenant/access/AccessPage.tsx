import PersonAdd from '@mui/icons-material/PersonAdd';
import { Alert, Button, Chip, Stack, Tooltip } from '@mui/material';
import { useCallback, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { tenantAccessService } from '../../../api/services/tenantAccessService';
import type { MemberDto, TenantRoleDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ConfirmDialog } from '../../../components/forms/ConfirmDialog';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstant } from '../../../utils/dates';
import { roleLabel } from './accessForm';
import { OneTimePasswordDialog } from './OneTimePasswordDialog';
import { AddUserDialog, EditUserDialog } from './UserDialogs';

type Confirming = { kind: 'deactivate' | 'reset'; member: MemberDto };

interface ShownPassword {
  title: string;
  person: string;
  password: string;
}

const NO_ROLES: readonly TenantRoleDto[] = [];

/**
 * The company's users: add (one-time password for a new account), edit name and roles, deactivate /
 * reactivate, reset a password. Roles held under a managed-service mandate end with the mandate.
 */
export function AccessPage() {
  const notify = useNotify();
  const { hasPermission, isReadOnly, me } = useSession();
  const canAssignApprovers = hasPermission(PERMISSIONS.tenantAccessAssignApprovers);
  const canManage = hasPermission(PERMISSIONS.tenantAccessManage) && !isReadOnly;
  const keyFor = useIdempotencyKey();
  const [showInactive, setShowInactive] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) =>
      // reloadKey: a new function reloads the list after a change.
      tenantAccessService.listMembers(showInactive ? 'ALL' : 'ACTIVE', signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [showInactive, reloadKey],
  );
  const resource = useAsyncResource(load);
  const loadRoles = useCallback((signal: AbortSignal) => tenantAccessService.listRoles(signal), []);
  const roles = useAsyncResource(loadRoles).data ?? NO_ROLES;
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<MemberDto | null>(null);
  const [confirming, setConfirming] = useState<Confirming | null>(null);
  const [password, setPassword] = useState<ShownPassword | null>(null);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const myId = me?.user_id ?? null;

  const actionsFor = (m: MemberDto): RowAction[] => {
    const active = m.status === 'ACTIVE';
    const mandated = m.roles.some((r) => (r.mandate_reference ?? null) !== null);
    const self = m.user_id === myId;
    return [
      {
        key: 'edit',
        label: 'Edit',
        hidden: !canManage || !active || mandated,
        onClick: () => {
          setEditing(m);
        },
      },
      {
        key: 'reset',
        label: 'Reset password',
        hidden: !canManage || !active || mandated || self,
        onClick: () => {
          setConfirming({ kind: 'reset', member: m });
        },
      },
      {
        key: 'deactivate',
        label: 'Deactivate',
        destructive: true,
        hidden: !canManage || !active || mandated || self,
        onClick: () => {
          setConfirming({ kind: 'deactivate', member: m });
        },
      },
      {
        key: 'reactivate',
        label: 'Reactivate',
        hidden: !canManage || active,
        onClick: () => {
          const payload = { reactivate: m.user_id };
          tenantAccessService
            .reactivate(m.user_id, keyFor(payload))
            .then(() => {
              notify.success(`${m.display_name} is active again.`);
              reload();
            })
            .catch((err: unknown) => {
              notify.error(err instanceof Error ? err.message : 'Could not reactivate.');
            });
        },
      },
    ];
  };

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
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
          {m.roles.map((r) => {
            const ref = r.mandate_reference ?? null;
            return (
              <Stack key={r.role_key} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Tooltip title={`Since ${formatInstant(r.since)}`}>
                  <Chip size="small" label={roleLabel(r.role_key)} />
                </Tooltip>
                {ref !== null && (
                  <Chip
                    size="small"
                    color="info"
                    variant="outlined"
                    label={`Managed service · ${ref}`}
                  />
                )}
              </Stack>
            );
          })}
        </Stack>
      ),
    },
    {
      id: 'state',
      header: 'State',
      render: (m) =>
        m.status === 'ACTIVE' ? (
          <ActiveChip active />
        ) : (
          <Tooltip
            title={
              m.deactivated_at ? `Deactivated ${formatInstant(m.deactivated_at)}` : 'Deactivated'
            }
          >
            <span>
              <ActiveChip active={false} />
            </span>
          </Tooltip>
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (m) => <RowActionsMenu label={m.display_name} actions={actionsFor(m)} />,
    },
  ];

  const confirm = confirming;
  return (
    <>
      <PageHeader
        title="Users & roles"
        subtitle="Who can sign in to this account and what they can do. Managed-service roles end with their mandate."
        actions={
          <CanMutate permission={PERMISSIONS.tenantAccessManage}>
            <Button
              variant="contained"
              startIcon={<PersonAdd />}
              onClick={() => {
                setAdding(true);
              }}
            >
              Add user
            </Button>
          </CanMutate>
        }
      />
      {!canAssignApprovers && hasPermission(PERMISSIONS.tenantAccessManage) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Only the company owner can give someone a role that approves things.
        </Alert>
      )}
      <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
      <AsyncContent
        resource={resource}
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
      {adding && (
        <AddUserDialog
          roles={roles}
          canAssignApprovers={canAssignApprovers}
          onClose={() => {
            setAdding(false);
          }}
          onAdded={(result, v) => {
            const name = `${v.first_name.trim()} ${v.last_name.trim()}`;
            reload();
            if (result.temporary_password) {
              setPassword({
                title: `${name} added`,
                person: name,
                password: result.temporary_password,
              });
            } else {
              notify.success(
                `${name} already uses Asseta; they sign in with their usual password and now have the ${roleLabel(v.role_key)} role here.`,
              );
            }
          }}
        />
      )}
      {editing !== null && (
        <EditUserDialog
          member={editing}
          roles={roles}
          canAssignApprovers={canAssignApprovers}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(latest) => {
            reload();
            if (latest !== null) notify.success(`${editing.display_name} updated.`);
          }}
        />
      )}
      {confirm !== null && (
        <ConfirmDialog
          open
          title={
            confirm.kind === 'deactivate'
              ? `Deactivate ${confirm.member.display_name}?`
              : `Reset ${confirm.member.display_name}'s password?`
          }
          message={
            confirm.kind === 'deactivate'
              ? 'They lose their roles here and are signed out of the apps and the website. Their sales, reports and other records stay. You can reactivate them later.'
              : 'They are signed out of the apps and the website. You get a one-time password to give them; they choose their own when they sign in.'
          }
          confirmLabel={confirm.kind === 'deactivate' ? 'Deactivate' : 'Reset password'}
          destructive={confirm.kind === 'deactivate'}
          onClose={() => {
            setConfirming(null);
          }}
          onConfirm={async () => {
            const m = confirm.member;
            if (confirm.kind === 'deactivate') {
              await tenantAccessService.deactivate(m.user_id, keyFor({ deactivate: m.user_id }));
              notify.success(`${m.display_name} deactivated.`);
              reload();
              return;
            }
            const result = await tenantAccessService.resetPassword(
              m.user_id,
              keyFor({ reset: m.user_id, at: Date.now() }),
            );
            setPassword({
              title: 'Password reset',
              person: m.display_name,
              password: result.temporary_password,
            });
          }}
        />
      )}
      {password !== null && (
        <OneTimePasswordDialog
          {...password}
          onClose={() => {
            setPassword(null);
          }}
        />
      )}
    </>
  );
}
