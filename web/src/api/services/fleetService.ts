import type { HistoryDto, MachineMapDto } from '../types';
import { historySchema, machineMapSchema } from './geoSchemas';
import { seg, tenantGet, tenantList } from './tenantRequest';

export const fleetService = {
  /** GET /tenant/fleet/map (getFleetMap): one entry per non-disposed machine. */
  map(signal?: AbortSignal): Promise<MachineMapDto[]> {
    return tenantList('/tenant/fleet/map', machineMapSchema, 'fleet map', signal);
  },
  /** GET /tenant/fleet/machines/{id} (getMachineStatus). */
  machineStatus(machineId: string, signal?: AbortSignal): Promise<MachineMapDto> {
    return tenantGet(
      `/tenant/fleet/machines/${seg(machineId)}`,
      machineMapSchema,
      'machine status',
      signal,
    );
  },
  /** GET /tenant/fleet/machines/{id}/history (getMachineHistory). `from`/`to` are UTC ISO (≤31 days). */
  history(machineId: string, from: string, to: string, signal?: AbortSignal): Promise<HistoryDto> {
    return tenantGet(
      `/tenant/fleet/machines/${seg(machineId)}/history`,
      historySchema,
      'machine history',
      signal,
      { from, to },
    );
  },
};
