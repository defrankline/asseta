import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto, MachineDto } from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { MachineEngineHoursPanel } from '../engineHours/MachineEngineHoursPanel';
import { useMachineActions } from '../machines/useMachineActions';
import { labelOf, MACHINE_STATUS_OPTIONS, MACHINE_STATUS_TONES } from '../shared/display';
import { HistoryTab } from './HistoryTab';
import { LiveStatusTab } from './LiveStatusTab';
import { MachineInfo } from './MachineInfo';
import { StaffAssignmentsTab } from './StaffAssignmentsTab';
import { TrackerHistoryTab } from './TrackerHistoryTab';

type TabKey = 'live' | 'history' | 'staff' | 'trackers' | 'engineHours';

interface Loaded {
  machine: MachineDto;
  categories: CategoryDto[];
  areas: AreaDto[];
}

function MachineTabs({ machineId, timeZone }: { machineId: string; timeZone: string }) {
  const { hasPermission } = useSession();
  const engineHoursOn = useCapabilityEnabled(CAPABILITY.engineHours);
  const available: { key: TabKey; label: string }[] = [
    ...(hasPermission(PERMISSIONS.tenantFleetRead)
      ? [
          { key: 'live' as const, label: 'Live status' },
          { key: 'history' as const, label: 'History' },
        ]
      : []),
    ...(hasPermission(PERMISSIONS.tenantStaffRead)
      ? [{ key: 'staff' as const, label: 'Staff assignments' }]
      : []),
    ...(hasPermission(PERMISSIONS.tenantTrackerRead)
      ? [{ key: 'trackers' as const, label: 'Tracker history' }]
      : []),
    ...(engineHoursOn && hasPermission(PERMISSIONS.tenantMeterRead)
      ? [{ key: 'engineHours' as const, label: 'Engine hours' }]
      : []),
  ];
  const [tab, setTab] = useState<TabKey | null>(null);
  const active = available.find((t) => t.key === tab)?.key ?? available[0]?.key ?? null;
  if (active === null) return null;
  return (
    <Paper variant="outlined">
      <Tabs
        value={active}
        onChange={(_e, v: TabKey) => {
          setTab(v);
        }}
        variant="scrollable"
        aria-label="Machine details"
      >
        {available.map((t) => (
          <Tab key={t.key} value={t.key} label={t.label} />
        ))}
      </Tabs>
      <Box className="p-3">
        {active === 'live' && <LiveStatusTab machineId={machineId} timeZone={timeZone} />}
        {active === 'history' && <HistoryTab machineId={machineId} timeZone={timeZone} />}
        {active === 'staff' && <StaffAssignmentsTab machineId={machineId} timeZone={timeZone} />}
        {active === 'trackers' && <TrackerHistoryTab machineId={machineId} timeZone={timeZone} />}
        {active === 'engineHours' && <MachineEngineHoursPanel machineId={machineId} />}
      </Box>
    </Paper>
  );
}

/** Machine registry record, live status, route history, staff and tracker assignments. */
export function MachineDetailPage() {
  const { machineId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const [machine, categories, areas] = await Promise.all([
        machineService.get(machineId, signal),
        // Include inactive records so a machine's retired category / area still shows its name.
        machineService.listCategories(signal, undefined, true),
        machineService.listAreas(signal, undefined, true),
      ]);
      return { machine, categories, areas };
    },
    [machineId],
  );
  const resource = useAsyncResource(load);
  const machine = resource.data?.machine ?? null;
  const { actionsFor, dialogs } = useMachineActions({
    onChanged: resource.reload,
    onReload: resource.reload,
  });

  return (
    <>
      <EntityDetailsLayout
        title={machine === null ? 'Machine' : `${machine.asset_code} · ${machine.name}`}
        subtitle="Machine details"
        back={{ label: 'All machines', to: ROUTES.tenantMachines }}
        {...(machine !== null
          ? {
              status: (
                <StatusChip
                  status={machine.status}
                  tones={MACHINE_STATUS_TONES}
                  label={labelOf(MACHINE_STATUS_OPTIONS, machine.status)}
                />
              ),
              actions: <ActionButtons actions={actionsFor(machine)} />,
            }
          : {})}
        inactive={
          machine?.status === 'DISPOSED'
            ? {
                title: 'This machine is retired (disposed). Its history is kept read-only.',
                reason: machine.deactivation_reason ?? null,
                since:
                  machine.deactivated_at == null
                    ? null
                    : formatInstantIn(machine.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the machine"
          loadingLabel="Loading machine"
        >
          {(d) => (
            <Box className="flex flex-col gap-6">
              <DetailSection title="Registry record">
                <MachineInfo
                  machine={d.machine}
                  categories={d.categories}
                  areas={d.areas}
                  timeZone={timeZone}
                />
              </DetailSection>
              <MachineTabs machineId={d.machine.id} timeZone={timeZone} />
            </Box>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
