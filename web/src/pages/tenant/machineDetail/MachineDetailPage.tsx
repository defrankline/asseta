import ArrowBack from '@mui/icons-material/ArrowBack';
import Edit from '@mui/icons-material/Edit';
import { Box, Button, Paper, Stack, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto, MachineDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { EditMachineDialog } from '../machines/EditMachineDialog';
import { HistoryTab } from './HistoryTab';
import { LiveStatusTab } from './LiveStatusTab';
import { MachineInfo } from './MachineInfo';
import { StaffAssignmentsTab } from './StaffAssignmentsTab';
import { TrackerHistoryTab } from './TrackerHistoryTab';

type TabKey = 'live' | 'history' | 'staff' | 'trackers';

interface Loaded {
  machine: MachineDto;
  categories: CategoryDto[];
  areas: AreaDto[];
}

function MachineTabs({ machineId, timeZone }: { machineId: string; timeZone: string }) {
  const { hasPermission } = useSession();
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
      </Box>
    </Paper>
  );
}

/** Machine registry record, live status, route history, staff and tracker assignments. */
export function MachineDetailPage() {
  const { machineId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const [editing, setEditing] = useState(false);
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const [machine, categories, areas] = await Promise.all([
        machineService.get(machineId, signal),
        machineService.listCategories(signal),
        machineService.listAreas(signal),
      ]);
      return { machine, categories, areas };
    },
    [machineId],
  );
  const resource = useAsyncResource(load);
  const machine = resource.data?.machine ?? null;

  return (
    <>
      <PageHeader
        title={machine === null ? 'Machine' : `${machine.asset_code} · ${machine.name}`}
        subtitle="Machine details"
        actions={
          <>
            <Button component={RouterLink} to={ROUTES.tenantMachines} startIcon={<ArrowBack />}>
              All machines
            </Button>
            {machine !== null && machine.status !== 'DISPOSED' && (
              <CanMutate permission={PERMISSIONS.tenantMachineWrite}>
                <Button
                  variant="contained"
                  startIcon={<Edit />}
                  onClick={() => {
                    setEditing(true);
                  }}
                >
                  Edit
                </Button>
              </CanMutate>
            )}
          </>
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load the machine"
        loadingLabel="Loading machine"
      >
        {(d) => (
          <Stack spacing={3}>
            <Paper variant="outlined" className="p-4">
              <MachineInfo
                machine={d.machine}
                categories={d.categories}
                areas={d.areas}
                timeZone={timeZone}
              />
            </Paper>
            <MachineTabs machineId={d.machine.id} timeZone={timeZone} />
          </Stack>
        )}
      </AsyncContent>
      {editing && machine !== null && (
        <EditMachineDialog
          machine={machine}
          onClose={() => {
            setEditing(false);
          }}
          onSaved={() => {
            notify.success('Machine updated.');
            resource.reload();
          }}
          onReloadRequested={() => {
            setEditing(false);
            resource.reload();
          }}
        />
      )}
    </>
  );
}
