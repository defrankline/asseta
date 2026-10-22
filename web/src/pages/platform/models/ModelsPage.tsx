import { Box, Stack, TextField, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlModelVersionDto, TenantDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { modelDetailPath } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { searchTenants, tenantLabel } from '../shared/platformLookups';
import { InferenceSwitchCard } from './InferenceSwitchCard';
import {
  ALGORITHM_LABELS,
  MODEL_STATUS_LABELS,
  MODEL_STATUS_OPTIONS,
  MODEL_STATUS_TONES,
} from './modelDisplay';
import { ReadinessSection } from './ReadinessSection';

const EVALUATION_TONES = { PASSED: 'success', FAILED: 'warning', NONE: 'default' } as const;
const EVALUATION_LABELS = {
  PASSED: 'Passed',
  FAILED: 'Not passed',
  NONE: 'Not evaluated',
} as const;

function evaluationKey(m: MlModelVersionDto): keyof typeof EVALUATION_LABELS {
  if (m.evaluation_passed === true) return 'PASSED';
  return m.evaluation_passed === false ? 'FAILED' : 'NONE';
}

/**
 * Models (backend `platform.models` menu, `platform.ml.read`): the inference switch, model versions
 * per tenant and readiness with snapshot / training triggers. Actions need `platform.ml.manage`.
 */
export function ModelsPage() {
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformMlManage);
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const [status, setStatus] = useState('');
  const [name, setName] = useState('');
  const debouncedName = useDebouncedValue(name.trim(), 300);
  const [reloadKey, setReloadKey] = useState(0);
  const filters = useMemo(
    () => ({
      tenant_id: tenant?.id,
      status: status || undefined,
      name: debouncedName || undefined,
    }),
    [tenant, status, debouncedName],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      platformMlService.listModels(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<MlModelVersionDto>[] = [
    { id: 'tenant', header: 'Tenant', render: (m) => m.tenant_name ?? m.tenant_id },
    { id: 'name', header: 'Model', render: (m) => `${m.name} v${String(m.version)}` },
    { id: 'algorithm', header: 'Algorithm', render: (m) => ALGORITHM_LABELS[m.algorithm] },
    {
      id: 'status',
      header: 'Status',
      render: (m) => (
        <StatusChip
          status={m.status}
          tones={MODEL_STATUS_TONES}
          label={MODEL_STATUS_LABELS[m.status]}
        />
      ),
    },
    {
      id: 'evaluation',
      header: 'Evaluation',
      render: (m) => (
        <StatusChip
          status={evaluationKey(m)}
          tones={EVALUATION_TONES}
          label={EVALUATION_LABELS[evaluationKey(m)]}
        />
      ),
    },
    { id: 'created', header: 'Trained', render: (m) => formatInstantIn(m.created_at, timeZone) },
    {
      id: 'deployed',
      header: 'Deployed',
      render: (m) => formatInstantIn(m.deployed_at, timeZone),
    },
  ];
  return (
    <>
      <PageHeader
        title="Models"
        subtitle="Governed anomaly models: evaluation against the statistical baseline, approval and deployment"
      />
      <Stack spacing={3}>
        <InferenceSwitchCard timeZone={timeZone} canManage={canManage} />
        <Box component="section" aria-label="Model versions" className="flex flex-col gap-2">
          <Typography variant="h6" component="h2">
            Model versions
          </Typography>
          <ServerDataTable<MlModelVersionDto>
            columns={columns}
            fetchPage={fetchPage}
            getRowId={(m) => m.id}
            filters={filters}
            searchable={false}
            reloadKey={reloadKey}
            emptyTitle="No model versions match these filters"
            isRowMuted={(m) => ['RETIRED', 'DISABLED', 'REJECTED'].includes(m.status)}
            onRowClick={(m) => {
              void navigate(modelDetailPath(m.id));
            }}
            toolbar={
              <>
                <Box className="min-w-56">
                  <AsyncAutocomplete<TenantDto>
                    label="Tenant"
                    value={tenant}
                    onChange={setTenant}
                    fetchOptions={searchTenants}
                    getOptionLabel={tenantLabel}
                    isOptionEqualToValue={(a, b) => a.id === b.id}
                  />
                </Box>
                <StaticSelectFilter
                  label="Status"
                  value={status}
                  options={MODEL_STATUS_OPTIONS}
                  onChange={setStatus}
                  allLabel="All statuses"
                />
                <TextField
                  size="small"
                  label="Model name"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                  }}
                />
              </>
            }
          />
        </Box>
        <ReadinessSection
          timeZone={timeZone}
          canManage={canManage}
          onTrained={() => {
            setReloadKey((k) => k + 1);
          }}
        />
      </Stack>
    </>
  );
}
