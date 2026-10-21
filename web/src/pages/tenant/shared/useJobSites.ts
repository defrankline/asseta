import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { geofenceService } from '../../../api/services/geofenceService';
import type { JobSiteDto } from '../../../api/types';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';

export interface JobSites {
  /** null when the user cannot read job sites. */
  sites: readonly JobSiteDto[] | null;
  label: (id: string | null) => string;
}

const NONE: readonly JobSiteDto[] = [];

/** Job sites for selectors (only fetched with `tenant.geofence.read`). */
export function useJobSites(): JobSites {
  const { hasPermission } = useSession();
  const canRead = hasPermission(PERMISSIONS.tenantGeofenceRead);
  const load = useCallback((signal: AbortSignal) => geofenceService.listJobSites(signal), []);
  const res = useAsyncResource(load, [], canRead);
  const sites = canRead ? (res.data ?? NONE) : null;
  const label = useMemo(() => {
    const names = new Map((sites ?? NONE).map((s) => [s.id, `${s.code} · ${s.name}`]));
    return (id: string | null) => (id === null ? '—' : (names.get(id) ?? id));
  }, [sites]);
  return { sites, label };
}

export function siteOptions(sites: readonly JobSiteDto[] | null, emptyLabel: string) {
  return [
    { value: '', label: emptyLabel },
    ...(sites ?? NONE).map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` })),
  ];
}
