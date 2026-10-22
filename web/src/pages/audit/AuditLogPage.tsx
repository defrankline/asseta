import SupportAgentOutlined from '@mui/icons-material/SupportAgentOutlined';
import { Box, Chip, TextField, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { PERMISSIONS } from '../../access/permissionCodes';
import { auditService, type AuditScope } from '../../api/services/auditService';
import { peopleService } from '../../api/services/peopleService';
import type { AuditEventDto, PersonDto, TenantDto } from '../../api/types';
import { AsyncAutocomplete } from '../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../components/data/ServerDataTable';
import type { ServerQuery } from '../../components/data/useServerPage';
import { PageHeader } from '../../components/feedback/PageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDisplayTimeZone } from '../../hooks/useDisplayTimeZone';
import { useSession } from '../../session/useSession';
import { isIsoDate } from '../../utils/dates';
import { formatInstantIn } from '../../utils/time';
import { searchTenants, tenantLabel } from '../platform/shared/platformLookups';
import { AuditDetails } from './AuditDetails';
import { mandateLabel, periodParams } from './auditDisplay';

const ACTION_PREFIX = /^[a-z0-9_.]+$/;

function ActorCell({ e }: { e: AuditEventDto }) {
  return (
    <Box className="flex flex-col items-start gap-1">
      <span>{e.actor_display_name ?? (e.actor_user_id === null ? 'System' : 'Unknown user')}</span>
      {e.mandate_reference !== null && (
        <Chip
          size="small"
          variant="outlined"
          icon={<SupportAgentOutlined />}
          label={mandateLabel(e.mandate_reference)}
        />
      )}
    </Box>
  );
}

function columns(scope: AuditScope, tz: string): DataColumn<AuditEventDto>[] {
  const cols: DataColumn<AuditEventDto>[] = [
    { id: 'when', header: 'When', render: (e) => formatInstantIn(e.occurred_at, tz, true) },
    { id: 'actor', header: 'Actor', render: (e) => <ActorCell e={e} /> },
    {
      id: 'action',
      header: 'Action',
      render: (e) => <Box sx={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>{e.action}</Box>,
    },
    {
      id: 'entity',
      header: 'Record',
      render: (e) => (
        <>
          <span>{e.entity_type}</span>
          <Typography variant="caption" color="text.secondary" component="div">
            {e.entity_id}
          </Typography>
        </>
      ),
    },
    { id: 'reason', header: 'Reason', render: (e) => e.reason ?? '—' },
  ];
  if (scope === 'platform') {
    cols.splice(3, 0, {
      id: 'tenant',
      header: 'Tenant',
      render: (e) => (e.tenant_id === null ? 'Platform' : e.tenant_id.slice(0, 8)),
    });
  }
  return cols;
}

/**
 * Audit log of the current console (`/tenant/audit`, `/platform/audit`): who changed what and when,
 * newest first, with server filters and the recorded values per event (expand a row).
 */
export function AuditLogPage({ scope }: { scope: AuditScope }) {
  const { hasPermission } = useSession();
  const tz = useDisplayTimeZone();
  const [actor, setActor] = useState<PersonDto | null>(null);
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const [actionInput, setActionInput] = useState('');
  const [entityTypeInput, setEntityTypeInput] = useState('');
  const [entityIdInput, setEntityIdInput] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const action = useDebouncedValue(actionInput.trim().toLowerCase(), 300);
  const entityType = useDebouncedValue(entityTypeInput.trim(), 300);
  const entityId = useDebouncedValue(entityIdInput.trim(), 300);
  const actionValid = action === '' || ACTION_PREFIX.test(action);
  const periodValid = !(isIsoDate(from) && isIsoDate(to) && to < from);
  const canSearchPeople = scope === 'tenant' && hasPermission(PERMISSIONS.tenantDirectoryRead);

  const filters = useMemo(
    () => ({
      actor_user_id: actor?.user_id,
      tenant_id: tenant?.id,
      action_prefix: actionValid ? action || undefined : undefined,
      entity_type: entityType || undefined,
      entity_id: entityId || undefined,
      ...(periodValid ? periodParams(from, to, tz) : {}),
    }),
    [actor, tenant, action, actionValid, entityType, entityId, from, to, periodValid, tz],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      auditService.list(
        scope,
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [scope],
  );
  const searchPeople = useCallback(
    (q: string, signal: AbortSignal) => peopleService.search(q, signal),
    [],
  );
  const cols = useMemo(() => columns(scope, tz), [scope, tz]);

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle={
          scope === 'tenant'
            ? `Who changed what in this tenant, and when · times in ${tz}`
            : `Platform and billing actions · times in ${tz}`
        }
      />
      <ServerDataTable<AuditEventDto>
        columns={cols}
        fetchPage={fetchPage}
        getRowId={(e) => e.id}
        filters={filters}
        searchPlaceholder="Search action or record"
        emptyTitle="No audit events match these filters"
        renderDetail={(e) => <AuditDetails event={e} />}
        detailLabel={(e) => `Show details of ${e.action}`}
        toolbar={
          <>
            {canSearchPeople && (
              <Box sx={{ minWidth: 220 }}>
                <AsyncAutocomplete<PersonDto>
                  label="Actor"
                  size="small"
                  value={actor}
                  onChange={setActor}
                  fetchOptions={searchPeople}
                  getOptionLabel={(p) => p.display_name}
                  isOptionEqualToValue={(a, b) => a.user_id === b.user_id}
                />
              </Box>
            )}
            {scope === 'platform' && (
              <Box sx={{ minWidth: 220 }}>
                <AsyncAutocomplete<TenantDto>
                  label="Tenant"
                  size="small"
                  value={tenant}
                  onChange={setTenant}
                  fetchOptions={searchTenants}
                  getOptionLabel={tenantLabel}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                />
              </Box>
            )}
            <TextField
              size="small"
              label="Action starts with"
              placeholder="e.g. finance."
              value={actionInput}
              onChange={(e) => {
                setActionInput(e.target.value);
              }}
              error={!actionValid}
              helperText={actionValid ? undefined : 'Lowercase letters, digits, "_" and "." only'}
            />
            <TextField
              size="small"
              label="Record type"
              value={entityTypeInput}
              onChange={(e) => {
                setEntityTypeInput(e.target.value);
              }}
            />
            <TextField
              size="small"
              label="Record id"
              value={entityIdInput}
              onChange={(e) => {
                setEntityIdInput(e.target.value);
              }}
            />
            <TextField
              size="small"
              type="date"
              label="From"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
              }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              type="date"
              label="To"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
              }}
              error={!periodValid}
              helperText={periodValid ? undefined : 'Must not be before From'}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </>
        }
      />
    </>
  );
}
