import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto } from '../../../api/types';
import { DeactivateDialog, ReactivateDialog } from '../../../components/lifecycle/DeactivateDialog';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useNotify } from '../../../notifications/useNotify';
import { labelOf, TRACKER_STATE_OPTIONS } from '../shared/display';
import { AssignTrackerDialog } from './AssignTrackerDialog';
import { EditTrackerDialog } from './EditTrackerDialog';
import { UnassignTrackerDialog } from './TrackerActionDialogs';
import {
  canTransition,
  RETIRE_CONSEQUENCES,
  SUSPEND_DESCRIPTION,
  TRACKER_ERROR_HINTS,
  TRACKER_STATE_ACTIONS,
  type TrackerStateActionKey,
} from './trackerLifecycle';

type OpenDialog = {
  kind: 'edit' | 'assign' | 'unassign' | TrackerStateActionKey;
  tracker: TrackerDto;
} | null;

interface UseTrackerActionsOptions {
  timeZone: string;
  /** Something changed (assignment or state); refresh what shows the tracker. */
  onChanged: (tracker?: TrackerDto) => void;
  onView?: (tracker: TrackerDto) => void;
}

/**
 * Tracker commands (view, edit, assign / swap, unassign, suspend, reactivate, retire) gated by
 * `tenant.tracker.write` and tenant access, plus their dialogs. Shared by list rows and details.
 */
export function useTrackerActions({ timeZone, onChanged, onView }: UseTrackerActionsOptions): {
  actionsFor: (tracker: TrackerDto) => RowAction[];
  dialogs: ReactNode;
} {
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantTrackerWrite);
  const [open, setOpen] = useState<OpenDialog>(null);
  const close = () => {
    setOpen(null);
  };
  const done = (message: string, tracker?: TrackerDto) => {
    notify.success(message);
    onChanged(tracker);
  };

  const actionsFor = (t: TrackerDto): RowAction[] => {
    const openFor = (kind: NonNullable<OpenDialog>['kind']) => () => {
      setOpen({ kind, tracker: t });
    };
    return [
      ...(onView !== undefined
        ? [
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                onView(t);
              },
            },
          ]
        : []),
      {
        key: 'edit',
        label: 'Edit',
        hidden: !canWrite || t.provisioning_state === 'RETIRED',
        onClick: openFor('edit'),
      },
      {
        key: 'assign',
        label: 'Assign / swap',
        hidden: !canWrite || t.provisioning_state === 'RETIRED',
        onClick: openFor('assign'),
      },
      {
        key: 'unassign',
        label: 'Unassign',
        hidden: !canWrite || t.current_assignment == null,
        onClick: openFor('unassign'),
      },
      ...TRACKER_STATE_ACTIONS.map((a) => ({
        key: a.key,
        label: a.label,
        destructive: a.key === 'retire',
        hidden: !canWrite || !canTransition(t.provisioning_state, a.target),
        onClick: openFor(a.key),
      })),
    ];
  };

  const changeState = (t: TrackerDto, key: TrackerStateActionKey) => {
    const target = TRACKER_STATE_ACTIONS.find((a) => a.key === key)?.target ?? 'SUSPENDED';
    return (reason: string, idempotencyKey: string) =>
      trackerService.changeState(t.id, { state: target, reason }, idempotencyKey);
  };
  const stateDone = (next: TrackerDto) => {
    done(
      `Tracker ${next.label} is now ${labelOf(TRACKER_STATE_OPTIONS, next.provisioning_state).toLowerCase()}.`,
      next,
    );
  };
  const reload = () => {
    close();
    onChanged();
  };

  let dialogs: ReactNode = null;
  const t = open?.tracker;
  if (t !== undefined) {
    switch (open?.kind) {
      case 'edit':
        dialogs = (
          <EditTrackerDialog
            tracker={t}
            onClose={close}
            onReloadRequested={reload}
            onSaved={(next) => {
              done(`Tracker ${next.label} updated.`, next);
            }}
          />
        );
        break;
      case 'assign':
        dialogs = (
          <AssignTrackerDialog
            tracker={t}
            timeZone={timeZone}
            onClose={close}
            onAssigned={(a) => {
              done(a.is_primary ? 'Tracker assigned as primary.' : 'Tracker assigned.');
            }}
          />
        );
        break;
      case 'unassign':
        dialogs = (
          <UnassignTrackerDialog
            tracker={t}
            timeZone={timeZone}
            onClose={close}
            onDone={(next) => {
              done('Tracker unassigned.', next);
            }}
          />
        );
        break;
      case 'suspend':
        dialogs = (
          <LifecycleActionDialog<TrackerDto>
            title={`Suspend tracker ${t.label}`}
            description={SUSPEND_DESCRIPTION}
            confirmLabel="Suspend"
            errorHints={TRACKER_ERROR_HINTS}
            onConfirm={changeState(t, 'suspend')}
            onDone={stateDone}
            onClose={close}
            onReload={reload}
          />
        );
        break;
      case 'reactivate':
        dialogs = (
          <ReactivateDialog<TrackerDto>
            entityLabel={t.label}
            noun="tracker"
            description="The tracker returns to Registered and its data is accepted again; it becomes Verified reporting after its next valid report."
            errorHints={TRACKER_ERROR_HINTS}
            onConfirm={changeState(t, 'reactivate')}
            onDone={stateDone}
            onClose={close}
            onReload={reload}
          />
        );
        break;
      case 'retire':
        dialogs = (
          <DeactivateDialog<TrackerDto>
            entityLabel={t.label}
            noun="tracker"
            confirmLabel="Retire tracker"
            title={`Retire (decommission) tracker ${t.label}`}
            description={RETIRE_CONSEQUENCES}
            errorHints={TRACKER_ERROR_HINTS}
            onConfirm={changeState(t, 'retire')}
            onDone={stateDone}
            onClose={close}
            onReload={reload}
          />
        );
        break;
      default:
        break;
    }
  }
  return { actionsFor, dialogs };
}
