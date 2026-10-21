import Add from '@mui/icons-material/Add';
import {
  Box,
  Button,
  MenuItem,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { geofenceService } from '../../../api/services/geofenceService';
import { policyService } from '../../../api/services/policyService';
import type { JobSiteDto, MachineDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { MachinePicker } from '../shared/MachinePicker';
import { EffectivePolicyView } from './EffectivePolicyView';
import type { OverrideScope } from './policyFields';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import { PolicyVersionsTable } from './PolicyVersionsTable';

const NO_SITES: readonly JobSiteDto[] = [];

/** Effective TRACKING policy (tenant / machine / site) and its version history. */
export function PoliciesPage() {
  const tz = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canSites = hasPermission(PERMISSIONS.tenantGeofenceRead);
  const [scope, setScope] = useState<OverrideScope>('TENANT');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [siteId, setSiteId] = useState('');
  const [creating, setCreating] = useState(false);
  const [version, setVersion] = useState(0);

  const loadSites = useCallback((signal: AbortSignal) => geofenceService.listJobSites(signal), []);
  const sites = useAsyncResource(loadSites, [], canSites);
  const siteList = canSites ? (sites.data ?? NO_SITES) : null;

  const target =
    scope === 'MACHINE' ? (machine?.id ?? null) : scope === 'SITE' ? siteId || null : 'tenant';
  const loadEffective = useCallback(
    (signal: AbortSignal) =>
      policyService.effective(
        'TRACKING',
        {
          machine_id: scope === 'MACHINE' ? machine?.id : undefined,
          site_id: scope === 'SITE' ? siteId : undefined,
        },
        signal,
      ),
    [scope, machine, siteId],
  );
  const effective = useAsyncResource(loadEffective, [version], target !== null);
  const loadVersions = useCallback(
    (signal: AbortSignal) => policyService.versions('TRACKING', signal),
    [],
  );
  const versions = useAsyncResource(loadVersions, [version]);

  const refLabels = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of siteList ?? []) m.set(s.id, `${s.code} · ${s.name}`);
    if (machine !== null) m.set(machine.id, machineLabel(machine));
    return m;
  }, [siteList, machine]);

  return (
    <>
      <PageHeader
        title="Policies"
        subtitle="TRACKING policy: tenant defaults with machine / site overrides"
        actions={
          <CanMutate permission={PERMISSIONS.tenantPolicyManage}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New override
            </Button>
          </CanMutate>
        }
      />
      <Stack spacing={3}>
        <Paper variant="outlined" className="p-4">
          <Stack spacing={2}>
            <Box className="flex flex-wrap items-center gap-3">
              <ToggleButtonGroup
                exclusive
                size="small"
                value={scope}
                onChange={(_e, v: OverrideScope | null) => {
                  if (v !== null) setScope(v);
                }}
                aria-label="Policy scope"
              >
                <ToggleButton value="TENANT">Tenant</ToggleButton>
                <ToggleButton value="MACHINE">Machine</ToggleButton>
                {canSites && <ToggleButton value="SITE">Site</ToggleButton>}
              </ToggleButtonGroup>
              {scope === 'MACHINE' && (
                <Box className="min-w-72">
                  <MachinePicker value={machine} onChange={setMachine} />
                </Box>
              )}
              {scope === 'SITE' && (
                <TextField
                  select
                  size="small"
                  label="Job site"
                  value={siteId}
                  onChange={(e) => {
                    setSiteId(e.target.value);
                  }}
                  sx={{ minWidth: 240 }}
                >
                  {(siteList ?? []).map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.code} · {s.name}
                    </MenuItem>
                  ))}
                </TextField>
              )}
            </Box>
            <Typography variant="subtitle1" component="h2">
              Effective policy
            </Typography>
            {target === null ? (
              <EmptyState
                title={scope === 'MACHINE' ? 'Select a machine' : 'Select a job site'}
                description="The effective policy combines platform, tenant and override versions."
              />
            ) : (
              <AsyncContent resource={effective} errorTitle="Could not resolve the policy">
                {(p) => <EffectivePolicyView policy={p} />}
              </AsyncContent>
            )}
          </Stack>
        </Paper>
        <Paper variant="outlined" className="p-4">
          <Typography variant="subtitle1" component="h2" className="mb-2">
            Version history
          </Typography>
          <AsyncContent
            resource={versions}
            isEmpty={(v) => v.length === 0}
            emptyTitle="No tenant policy versions yet"
            emptyDescription="Platform defaults apply until the tenant creates a version."
          >
            {(v) => (
              <PolicyVersionsTable
                versions={v}
                timeZone={tz}
                refLabel={(id) => refLabels.get(id) ?? id}
              />
            )}
          </AsyncContent>
        </Paper>
      </Stack>
      {creating && (
        <PolicyOverrideDialog
          initialScope={scope}
          initialMachine={machine}
          initialSiteId={siteId}
          current={effective.data?.values ?? null}
          sites={siteList}
          timeZone={tz}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(v) => {
            notify.success(`Policy version v${String(v.version)} created.`);
            setVersion((x) => x + 1);
          }}
        />
      )}
    </>
  );
}
