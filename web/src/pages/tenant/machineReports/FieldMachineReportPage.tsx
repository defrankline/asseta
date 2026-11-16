import Add from '@mui/icons-material/Add';
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { MachineReportDto, MachineReportStatusDto } from '../../../api/machineReportTypes';
import { machineReportService } from '../../../api/services/machineReportService';
import type { MachineDto } from '../../../api/types';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { machineReportPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { machineText } from '../shared/names';
import { StatusChip } from '../../../components/display/StatusChip';
import { useHoursPolicy } from '../hours/useHoursPolicy';
import {
  hoursLabel,
  MACHINE_STATE_LABELS,
  MACHINE_STATE_TONES,
  machineReportState,
} from './machineReportDisplay';
import { MachineReportDialog } from './MachineReportDialog';
import { reportColumns } from './reportColumns';

type Opened = { machineId: string; corrects: MachineReportDto | null } | null;

/**
 * Field work › Machine report: the caller's machines with their report status, a new report (reading
 * → account for hours → review), corrections of rejected reports and the caller's own reports.
 */
export function FieldMachineReportPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const canSubmit = useCanMutate(PERMISSIONS.tenantMachineReportSubmit);
  const canReportAny = hasPermission(PERMISSIONS.tenantMachineReportApprove);
  const canOpen = hasPermission(PERMISSIONS.tenantMachineReportRead);
  const hours = useHoursPolicy();
  // The company's reminder days (default 3; null = only never-reported machines are due).
  const reminderDays = hours.policy === null ? 3 : hours.policy.machineReportReminderDays;
  const [opened, setOpened] = useState<Opened>(null);
  const [other, setOther] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const loadStatus = useCallback(
    (signal: AbortSignal) => machineReportService.status(undefined, signal),
    [],
  );
  const status = useAsyncResource(loadStatus, [reloadKey]);
  const fetchPage = useCallback<FetchPage<MachineReportDto>>(
    (query, signal) => machineReportService.list(query, signal),
    [],
  );
  const correct = (reportId: string, machineId: string) => {
    setError(null);
    machineReportService.get(reportId).then(
      (r) => {
        setOpened({ machineId, corrects: r });
      },
      () => {
        setError('Could not load the rejected report. Try again.');
      },
    );
  };
  return (
    <>
      <PageHeader
        title="Machine report"
        subtitle="Account for every engine hour of your machines: customers' hours and non-productive time"
      />
      <Stack spacing={3}>
        <Paper variant="outlined" className="p-4">
          <Stack spacing={2}>
            <Typography variant="h6" component="h2">
              My machines
            </Typography>
            {error !== null && (
              <Typography color="error" role="alert">
                {error}
              </Typography>
            )}
            <AsyncContent
              resource={status}
              isEmpty={(rows) => rows.length === 0}
              emptyTitle="No machine is assigned to you"
              emptyDescription="Ask the office to assign your machines to you."
              errorTitle="Could not load your machines"
            >
              {(rows) => (
                <StaticTable<MachineReportStatusDto>
                  ariaLabel="My machines"
                  rows={rows}
                  getRowId={(s) => s.machine_id}
                  columns={[
                    {
                      id: 'machine',
                      header: 'Machine',
                      render: (s) => machineText(s.machine_code, s.machine_name, s.machine_id),
                    },
                    {
                      id: 'last',
                      header: 'Last approved reading',
                      render: (s) =>
                        s.last_approved_reading === null
                          ? '—'
                          : `${hoursLabel(s.last_approved_reading)}${
                              s.last_approved_at === null
                                ? ''
                                : ` · ${formatInstantIn(s.last_approved_at, timeZone)}`
                            }`,
                    },
                    {
                      id: 'days',
                      header: 'Days since report',
                      align: 'right',
                      render: (s) =>
                        s.days_since_report === null ? 'Never' : String(s.days_since_report),
                    },
                    {
                      id: 'state',
                      header: 'Report',
                      render: (s) => {
                        const state = machineReportState(s, reminderDays);
                        return (
                          <StatusChip
                            status={state}
                            tones={MACHINE_STATE_TONES}
                            label={
                              state === 'AWAITING' && s.pending_report_number !== null
                                ? `${MACHINE_STATE_LABELS[state]} · ${s.pending_report_number}`
                                : state === 'DUE' && s.previous_reading == null
                                  ? `${MACHINE_STATE_LABELS[state]} · first reading`
                                  : MACHINE_STATE_LABELS[state]
                            }
                          />
                        );
                      },
                    },
                    {
                      id: 'action',
                      header: '',
                      render: (s) => {
                        if (s.pending_report_id !== null) {
                          const id = s.pending_report_id;
                          return canOpen ? (
                            <Button
                              size="small"
                              onClick={() => {
                                void navigate(machineReportPath(id));
                              }}
                            >
                              View
                            </Button>
                          ) : null;
                        }
                        if (!canSubmit) return null;
                        if (s.rejected_report_id !== null) {
                          const id = s.rejected_report_id;
                          return (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => {
                                correct(id, s.machine_id);
                              }}
                            >
                              Correct report
                            </Button>
                          );
                        }
                        return (
                          <Button
                            size="small"
                            variant="contained"
                            onClick={() => {
                              setOpened({ machineId: s.machine_id, corrects: null });
                            }}
                          >
                            New report
                          </Button>
                        );
                      },
                    },
                  ]}
                />
              )}
            </AsyncContent>
            {canSubmit && canReportAny && (
              <Box className="flex flex-wrap items-center gap-2">
                <Box sx={{ minWidth: 260 }}>
                  <MachineFilter label="Another machine" value={other} onChange={setOther} />
                </Box>
                <Button
                  variant="outlined"
                  startIcon={<Add />}
                  disabled={other === null}
                  onClick={() => {
                    if (other !== null) setOpened({ machineId: other.id, corrects: null });
                  }}
                >
                  Report on this machine
                </Button>
              </Box>
            )}
          </Stack>
        </Paper>
        <Stack spacing={1}>
          <Typography variant="h6" component="h2">
            My reports
          </Typography>
          <ServerDataTable
            columns={reportColumns(timeZone, { submitter: false })}
            fetchPage={fetchPage}
            getRowId={(r) => r.id}
            searchPlaceholder="Search report number or machine"
            initialSort="-submitted_at"
            filters={{ mine: 'true' }}
            reloadKey={reloadKey}
            emptyTitle="No reports yet"
            {...(canOpen
              ? {
                  onRowClick: (r: MachineReportDto) => {
                    void navigate(machineReportPath(r.id));
                  },
                }
              : {})}
          />
        </Stack>
      </Stack>
      {opened !== null && (
        <MachineReportDialog
          machineId={opened.machineId}
          corrects={opened.corrects}
          onClose={() => {
            setOpened(null);
          }}
          onSubmitted={(r) => {
            notify.success(`Report ${r.report_number} sent for approval.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
