import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { machineLabel } from '../shared/display';
import { MACHINE_ERROR_HINTS, type MachineStatusAction } from './machineLifecycle';
import { toUpdatePayload, valuesFromMachine } from './machineForm';

interface MachineStatusDialogProps {
  machine: MachineDto;
  action: MachineStatusAction;
  onClose: () => void;
  onDone: (machine: MachineDto) => void;
  onReload: () => void;
}

/**
 * Confirm a machine status change. The current contract has no reason field for machine status, so
 * this is a confirmation; the full record is re-sent with the `version` that was read.
 */
export function MachineStatusDialog({
  machine,
  action,
  onClose,
  onDone,
  onReload,
}: MachineStatusDialogProps) {
  return (
    <LifecycleActionDialog<MachineDto>
      title={`${action.label} · ${machineLabel(machine)}`}
      description={action.description}
      confirmLabel={action.label}
      destructive={action.destructive}
      reason="none"
      errorHints={MACHINE_ERROR_HINTS}
      onConfirm={(_reason, key) =>
        machineService.update(
          machine.id,
          toUpdatePayload(
            { ...valuesFromMachine(machine), status: action.target },
            machine.version,
          ),
          key,
        )
      }
      onDone={onDone}
      onClose={onClose}
      onReload={onReload}
    />
  );
}
