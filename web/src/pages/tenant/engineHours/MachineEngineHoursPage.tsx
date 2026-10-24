import { Button } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import { EntityDetailsLayout } from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { machineDetailPath, ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { MachineEngineHoursPanel } from './MachineEngineHoursPanel';

/** One machine's engine-hour ledger: baseline, totals and the interval / segment timeline. */
export function MachineEngineHoursPage() {
  const { machineId = '' } = useParams();
  const { hasPermission } = useSession();
  const canReadMachine = hasPermission(PERMISSIONS.tenantMachineRead);
  const load = useCallback(
    (signal: AbortSignal) => machineService.get(machineId, signal),
    [machineId],
  );
  const machine = useAsyncResource(load, [], canReadMachine);
  return (
    <EntityDetailsLayout
      title={
        machine.data === null ? 'Engine hours' : `Engine hours · ${machineLabel(machine.data)}`
      }
      subtitle="Intervals between consecutive readings, split into customer work and unallocated hours"
      back={{ label: 'Engine-hour reconciliation', to: ROUTES.tenantEngineHours }}
      {...(canReadMachine
        ? {
            actions: (
              <Button component={RouterLink} to={machineDetailPath(machineId)} variant="outlined">
                Machine record
              </Button>
            ),
          }
        : {})}
    >
      <MachineEngineHoursPanel machineId={machineId} />
    </EntityDetailsLayout>
  );
}
