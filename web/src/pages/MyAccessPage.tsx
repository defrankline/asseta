import { Box, Chip, Paper, Stack, Typography } from '@mui/material';
import type { MenuDto, TenantAccess } from '../api/types';
import { EmptyState } from '../components/feedback/EmptyState';
import { PageHeader } from '../components/feedback/PageHeader';
import { useSession } from '../session/useSession';

function formatMenus(menus: readonly MenuDto[]): string {
  if (menus.length === 0) return 'None';
  return [...menus]
    .sort((a, b) => a.order - b.order)
    .map((m) => `${m.label} (${m.path})`)
    .join(' · ');
}

function PermissionChips({ codes }: { codes: readonly string[] }) {
  if (codes.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        None
      </Typography>
    );
  }
  return (
    <Box className="flex flex-wrap gap-1">
      {[...codes].sort().map((c) => (
        <Chip key={c} label={c} size="small" variant="outlined" className="font-mono" />
      ))}
    </Box>
  );
}

function TenantCard({ tenant, active }: { tenant: TenantAccess; active: boolean }) {
  return (
    <Paper variant="outlined" className="p-4">
      <Box className="mb-2 flex flex-wrap items-center gap-2">
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {tenant.name}
        </Typography>
        <Chip label={tenant.status} size="small" />
        <Chip
          label={tenant.access_state.replace('_', ' ').toLowerCase()}
          size="small"
          color={
            tenant.access_state === 'FULL'
              ? 'success'
              : tenant.access_state === 'READ_ONLY'
                ? 'warning'
                : 'error'
          }
        />
        {active && <Chip label="Active" color="secondary" size="small" />}
      </Box>
      <Typography variant="caption" color="text.secondary" className="font-mono">
        {tenant.tenant_id}
      </Typography>
      <Typography variant="subtitle2" className="mt-3 mb-1">
        Permissions
      </Typography>
      <PermissionChips codes={tenant.permissions} />
      <Typography variant="subtitle2" className="mt-3 mb-1">
        Menus
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {formatMenus(tenant.menus)}
      </Typography>
    </Paper>
  );
}

/** Shows the signed-in user's identity, platform permissions and tenant memberships from /me. */
export function MyAccessPage() {
  const { me, mode } = useSession();
  if (me === null) return null;
  return (
    <>
      <PageHeader title="My access" subtitle="What you can see and do, as granted by Asseta." />
      <Stack spacing={3}>
        <Paper variant="outlined" className="p-4">
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {me.display_name}
          </Typography>
          <Typography variant="body2">{me.email}</Typography>
          <Typography variant="caption" color="text.secondary" className="font-mono">
            {me.user_id}
          </Typography>
          <Typography variant="subtitle2" className="mt-3 mb-1">
            Platform permissions
          </Typography>
          <PermissionChips codes={me.platform_permissions} />
          <Typography variant="subtitle2" className="mt-3 mb-1">
            Platform menus
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatMenus(me.platform_menus)}
          </Typography>
        </Paper>
        <Typography variant="h6" component="h2">
          Tenants
        </Typography>
        {me.tenants.length === 0 ? (
          <EmptyState
            title="No tenant memberships"
            description="Ask a tenant administrator to invite you."
          />
        ) : (
          me.tenants.map((t) => (
            <TenantCard
              key={t.tenant_id}
              tenant={t}
              active={mode.kind === 'tenant' && mode.tenantId === t.tenant_id}
            />
          ))
        )}
      </Stack>
    </>
  );
}
