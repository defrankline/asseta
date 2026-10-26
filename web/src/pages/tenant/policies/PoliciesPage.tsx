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
import type { CategoryDto, JobSiteDto, MachineDto, PolicyType, StaffDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { StaffFilter } from '../shared/financePickers';
import { CategoryFilter, JobSiteFilter } from '../shared/lookupPickers';
import { MachinePicker } from '../shared/MachinePicker';
import { EffectivePolicyView } from './EffectivePolicyView';
import { POLICY_TYPE_LABELS, scopesFor, type OverrideScope } from './policyFields';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import { PolicyVersionsTable } from './PolicyVersionsTable';

const NO_SITES: readonly JobSiteDto[] = [];
const POLICY_TYPES: readonly PolicyType[] = [
  'TRACKING',
  'METER_CAPTURE',
  'HIRE_BILLING',
  'DEVICE_SYNC',
  'EXPENSE_CAPTURE',
  'FRAUD_CONTROLS',
  'CASH_CUSTODY',
  'OVERSIGHT',
  'ENGINE_HOURS',
  'CUSTOMER_HOURS',
  'REVENUE_RECONCILIATION',
];
const SUBTITLES: Readonly<Record<PolicyType, string>> = {
  TRACKING: 'Tracking: tenant defaults with machine / site overrides',
  METER_CAPTURE:
    'Meter capture: opening and closing modes, photo/OCR, GPS and plausibility rules (machine / site overrides)',
  HIRE_BILLING: 'Hire billing: how meter hours become billable hours (tenant-wide only)',
  DEVICE_SYNC: 'Device sync: bounded offline operation for field devices (tenant-wide only)',
  EXPENSE_CAPTURE:
    'Expense capture: receipts, GPS and approval limits for field expenses (tenant-wide only)',
  FRAUD_CONTROLS:
    'Risk signals: thresholds for deterministic checks that open investigation cases (machine category / machine overrides)',
  CASH_CUSTODY:
    'Cash custody: recording for custodians, acknowledgements, remittance evidence, write-off approval and the cash holding allowance (site / staff overrides)',
  OVERSIGHT: 'Oversight: accountability dashboard tiles and windows (tenant-wide only)',
  ENGINE_HOURS:
    'Engine hours: baselines, daily reports, explanations and corrections of engine hours (machine overrides)',
  CUSTOMER_HOURS:
    'Customer hours: prepaid hours, activation, expiry, approvals and walk-ins (tenant-wide only)',
  REVENUE_RECONCILIATION:
    'Revenue checks: movement hours, daily machine sheet and matching engine hours with money (tenant-wide only)',
};

/** Effective policy per type (tenant / machine / site) and its version history. */
export function PoliciesPage() {
  const tz = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canSites = hasPermission(PERMISSIONS.tenantGeofenceRead);
  const canStaff = hasPermission(PERMISSIONS.tenantStaffRead);
  const [ptype, setPtype] = useState<PolicyType>('TRACKING');
  const [rawScope, setScope] = useState<OverrideScope>('TENANT');
  const scopes = scopesFor(ptype);
  const scope: OverrideScope = scopes.includes(rawScope) ? rawScope : 'TENANT';
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const siteId = site?.id ?? '';
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const staffId = staff?.id ?? '';
  const [category, setCategory] = useState<CategoryDto | null>(null);
  const categoryId = category?.id ?? '';
  const [creating, setCreating] = useState(false);
  const [version, setVersion] = useState(0);

  const loadSites = useCallback((signal: AbortSignal) => geofenceService.listJobSites(signal), []);
  const sites = useAsyncResource(loadSites, [], canSites);
  const siteList = canSites ? (sites.data ?? NO_SITES) : null;

  const target =
    scope === 'MACHINE'
      ? (machine?.id ?? null)
      : scope === 'SITE'
        ? siteId || null
        : scope === 'STAFF'
          ? staffId || null
          : scope === 'MACHINE_CATEGORY'
            ? categoryId || null
            : 'tenant';
  const loadEffective = useCallback(
    (signal: AbortSignal) =>
      policyService.effective(
        ptype,
        {
          machine_id: scope === 'MACHINE' ? machine?.id : undefined,
          site_id: scope === 'SITE' ? siteId : undefined,
          staff_id: scope === 'STAFF' ? staffId : undefined,
          category_id: scope === 'MACHINE_CATEGORY' ? categoryId : undefined,
        },
        signal,
      ),
    [ptype, scope, machine, siteId, staffId, categoryId],
  );
  const effective = useAsyncResource(loadEffective, [version], target !== null);
  const loadVersions = useCallback(
    (signal: AbortSignal) => policyService.versions(ptype, signal),
    [ptype],
  );
  const versions = useAsyncResource(loadVersions, [version]);

  const refLabels = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of siteList ?? []) m.set(s.id, `${s.code} · ${s.name}`);
    if (machine !== null) m.set(machine.id, machineLabel(machine));
    if (staff !== null) m.set(staff.id, staff.full_name);
    if (category !== null) m.set(category.id, category.name);
    return m;
  }, [siteList, machine, staff, category]);

  return (
    <>
      <PageHeader
        title="Policies"
        subtitle={SUBTITLES[ptype]}
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
              <TextField
                select
                size="small"
                label="Policy type"
                value={ptype}
                onChange={(e) => {
                  setPtype(e.target.value as PolicyType);
                }}
                sx={{ minWidth: 180 }}
              >
                {POLICY_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {POLICY_TYPE_LABELS[t]}
                  </MenuItem>
                ))}
              </TextField>
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
                {scopes.includes('MACHINE_CATEGORY') && (
                  <ToggleButton value="MACHINE_CATEGORY">Machine category</ToggleButton>
                )}
                {scopes.includes('MACHINE') && <ToggleButton value="MACHINE">Machine</ToggleButton>}
                {canSites && scopes.includes('SITE') && (
                  <ToggleButton value="SITE">Site</ToggleButton>
                )}
                {canStaff && scopes.includes('STAFF') && (
                  <ToggleButton value="STAFF">Staff member</ToggleButton>
                )}
              </ToggleButtonGroup>
              {scope === 'MACHINE_CATEGORY' && (
                <Box sx={{ minWidth: 260 }}>
                  <CategoryFilter
                    label="Machine category"
                    value={category}
                    onChange={setCategory}
                  />
                </Box>
              )}
              {scope === 'MACHINE' && (
                <Box className="min-w-72">
                  <MachinePicker value={machine} onChange={setMachine} />
                </Box>
              )}
              {scope === 'SITE' && (
                <Box sx={{ minWidth: 260 }}>
                  <JobSiteFilter label="Job site" value={site} onChange={setSite} />
                </Box>
              )}
              {scope === 'STAFF' && (
                <Box sx={{ minWidth: 260 }}>
                  <StaffFilter
                    label="Staff member"
                    placeholder="Choose a staff member"
                    value={staff}
                    onChange={setStaff}
                  />
                </Box>
              )}
            </Box>
            <Typography variant="subtitle1" component="h2">
              Effective policy
            </Typography>
            {target === null ? (
              <EmptyState
                title={
                  scope === 'MACHINE'
                    ? 'Select a machine'
                    : scope === 'STAFF'
                      ? 'Select a staff member'
                      : scope === 'MACHINE_CATEGORY'
                        ? 'Select a machine category'
                        : 'Select a job site'
                }
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
          policyType={ptype}
          initialScope={scope}
          initialMachine={machine}
          initialSiteId={siteId}
          initialStaffId={staffId}
          initialCategoryId={categoryId}
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
