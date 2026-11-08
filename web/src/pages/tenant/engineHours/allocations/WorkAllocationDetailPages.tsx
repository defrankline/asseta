import { Link, Typography } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { AllocationCorrectionDto, WorkAllocationDto } from '../../../../api/allocationTypes';
import { allocationService } from '../../../../api/services/allocationService';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { DetailSection } from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../../navigation/recordRoutes';
import { engineHoursMachinePath, jobDetailPath, ROUTES } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { useSession } from '../../../../session/useSession';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { machineText } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import { RecordDetail } from '../../shared/RecordDetail';
import { useRecordById } from '../../shared/useRecordById';
import { hoursText, OWN_PROPOSAL_TEXT } from '../engineHoursDisplay';
import { MeterDecisionDialog } from '../MeterDecisionDialog';
import { allocationTarget, sourceText } from './allocationDisplay';
import { AllocationStatusChip, KindChip, LotsList } from './allocationKit';
import { AllocationCorrectionDialog } from './AllocationCorrectionDialog';
import { EvidenceList } from './EvidenceUpload';

const loadAllocation = (id: string, signal: AbortSignal) => allocationService.get(id, signal);
const loadCorrection = (id: string, signal: AbortSignal) =>
  allocationService.getCorrection(id, signal);

const machineOf = (a: WorkAllocationDto) =>
  machineText(a.machine_code, a.machine_name, a.machine_id);

/** Longest chain of earlier entries walked back from a corrected entry. */
const MAX_CHAIN = 20;

interface ChainRow {
  role: string;
  entry: WorkAllocationDto;
}

/** Entries this one replaced (back to the original) and the entries that replaced it. */
function SupersededHistory({ allocation }: { allocation: WorkAllocationDto }) {
  const navigate = useNavigate();
  const load = useCallback(
    async (signal: AbortSignal): Promise<ChainRow[]> => {
      const rows: ChainRow[] = [];
      let previous = allocation.supersedes_id;
      for (let n = 0; previous !== null && n < MAX_CHAIN; n += 1) {
        const entry: WorkAllocationDto = await allocationService.get(previous, signal);
        rows.push({ role: 'Earlier entry', entry });
        previous = entry.supersedes_id;
      }
      const later = await Promise.all(
        (allocation.superseded_by_ids ?? []).map((id) => allocationService.get(id, signal)),
      );
      return [...later.map((entry) => ({ role: 'Replaced by', entry })), ...rows];
    },
    [allocation.supersedes_id, allocation.superseded_by_ids],
  );
  const chain = useAsyncResource(load, [allocation.id, allocation.status]);
  const columns: DataColumn<ChainRow>[] = [
    { id: 'role', header: 'Relation', render: (r) => r.role },
    {
      id: 'range',
      header: 'Readings',
      render: (r) => (
        <span className="font-mono">
          {r.entry.start_reading} → {r.entry.end_reading}
        </span>
      ),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (r) => <span className="font-mono">{r.entry.hours}</span>,
    },
    { id: 'kind', header: 'Kind', render: (r) => <KindChip kind={r.entry.kind} /> },
    { id: 'for', header: 'For', render: (r) => allocationTarget(r.entry) },
    { id: 'reason', header: 'Why', render: (r) => r.entry.correction_reason ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (r) => <AllocationStatusChip status={r.entry.status} />,
    },
  ];
  return (
    <DetailSection title="Superseded history">
      <AsyncContent resource={chain} errorTitle="Could not load the earlier entries">
        {(rows) =>
          rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Not corrected: this is the original entry.
            </Typography>
          ) : (
            <StaticTable
              ariaLabel="Superseded history"
              columns={columns}
              rows={rows}
              getRowId={(r) => r.entry.id}
              onRowClick={(r) => {
                void navigate(recordPath('WORK_ALLOCATION', r.entry.id));
              }}
            />
          )
        }
      </AsyncContent>
    </DetailSection>
  );
}

const jobLink = (a: WorkAllocationDto): ReactNode =>
  a.job_id === null ? (
    '—'
  ) : (
    <Link component={RouterLink} to={jobDetailPath(a.job_id)}>
      {a.job_number ?? 'Open job'}
    </Link>
  );

function allocationItems(a: WorkAllocationDto, timeZone: string): KeyValueItem[] {
  return [
    { label: 'Machine', value: machineOf(a) },
    { label: 'Work date', value: formatDate(a.work_date) },
    { label: 'Hours', value: hoursText(a.hours) },
    { label: 'Kind', value: <KindChip kind={a.kind} /> },
    {
      label: 'Start reading',
      value: `${a.start_reading} · ${formatInstantIn(a.start_at, timeZone)}`,
    },
    { label: 'End reading', value: `${a.end_reading} · ${formatInstantIn(a.end_at, timeZone)}` },
    { label: 'For', value: allocationTarget(a) },
    { label: 'Job', value: jobLink(a) },
    { label: 'Prepaid lots', value: <LotsList lots={a.lots} /> },
    { label: 'Source', value: sourceText(a.source) },
    {
      label: 'Recorded by',
      value: <PersonName userId={a.recorded_by} name={a.recorded_by_name} />,
    },
    { label: 'Correction reason', value: a.correction_reason ?? '—' },
    { label: 'Policy', value: a.policy_version },
  ];
}

/** One ledger entry: its meter range, lots, what it replaced or was replaced by, and a correction. */
export function WorkAllocationDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const navigate = useNavigate();
  const res = useRecordById(loadAllocation, id);
  const canPropose = useCanMutate(PERMISSIONS.tenantMeterReview);
  const [correcting, setCorrecting] = useState(false);
  return (
    <>
      <RecordDetail
        resource={res}
        what="work allocation"
        back={{ label: 'Work allocations', to: ROUTES.tenantWorkAllocations }}
        timeZone={timeZone}
        title={(a) => `Allocation · ${hoursText(a.hours)} · ${machineOf(a)}`}
        status={(a) => <AllocationStatusChip status={a.status} />}
        actions={(a) => [
          {
            key: 'correct',
            label: 'Propose correction',
            hidden: !canPropose || a.status !== 'ACTIVE',
            onClick: () => {
              setCorrecting(true);
            },
          },
        ]}
        primaryKey="correct"
        links={(a) => (
          <Link component={RouterLink} to={engineHoursMachinePath(a.machine_id)}>
            Engine hours
          </Link>
        )}
        items={(a) => allocationItems(a, timeZone)}
        history={(a) => [
          {
            key: 'recorded',
            at: a.created_at,
            label: 'Recorded',
            by: <PersonName userId={a.recorded_by} name={a.recorded_by_name} />,
          },
          {
            key: 'decided',
            at: a.decided_at,
            label: 'Decided',
            by: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
            note: a.decision_note,
          },
          { key: 'superseded', at: a.superseded_at, label: 'Superseded' },
        ]}
      >
        {(a) => (
          <>
            {a.correction_group_id !== null && (
              <DetailSection title="Correction">
                <Link
                  component={RouterLink}
                  to={recordPath('WORK_ALLOCATION_CORRECTION', a.correction_group_id)}
                >
                  Open the correction request
                </Link>
              </DetailSection>
            )}
            <SupersededHistory allocation={a} />
            <DetailSection title="Evidence">
              <EvidenceList ids={a.evidence_attachment_ids} />
            </DetailSection>
          </>
        )}
      </RecordDetail>
      {correcting && res.data !== null && (
        <AllocationCorrectionDialog
          allocation={res.data}
          onClose={() => {
            setCorrecting(false);
          }}
          onProposed={(c) => {
            notify.success(
              c.status === 'ACTIVE'
                ? 'Allocation corrected.'
                : 'Correction proposed; a second person decides it.',
            );
            void navigate(recordPath('WORK_ALLOCATION_CORRECTION', c.group_id));
          }}
        />
      )}
    </>
  );
}

/** One correction request (exact-record link): the proposed parts, the original, decide. */
export function AllocationCorrectionDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const { me } = useSession();
  const res = useRecordById(loadCorrection, id);
  const canDecide = useCanMutate(PERMISSIONS.tenantMeterApprove);
  const [deciding, setDeciding] = useState(false);
  const first = (c: AllocationCorrectionDto) => c.entries[0];
  const columns: DataColumn<WorkAllocationDto>[] = [
    {
      id: 'range',
      header: 'Readings',
      render: (a) => (
        <span className="font-mono">
          {a.start_reading} → {a.end_reading}
        </span>
      ),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (a) => <span className="font-mono">{a.hours}</span>,
    },
    { id: 'kind', header: 'Kind', render: (a) => <KindChip kind={a.kind} /> },
    { id: 'for', header: 'For', render: allocationTarget },
  ];
  return (
    <>
      <RecordDetail
        resource={res}
        what="allocation correction"
        back={{ label: 'Work allocations', to: ROUTES.tenantWorkAllocations }}
        timeZone={timeZone}
        title={(c) => {
          const e = first(c);
          return e === undefined ? 'Allocation correction' : `Correction · ${machineOf(e)}`;
        }}
        status={(c) => <AllocationStatusChip status={c.status} />}
        actions={(c) => {
          const proposer = first(c)?.recorded_by ?? null;
          return [
            {
              key: 'decide',
              label: 'Decide',
              hidden: !canDecide || c.status !== 'PROPOSED',
              disabled: me !== null && proposer === me.user_id,
              disabledReason: OWN_PROPOSAL_TEXT,
              onClick: () => {
                setDeciding(true);
              },
            },
          ];
        }}
        primaryKey="decide"
        items={(c) => {
          const e = first(c);
          return [
            {
              label: 'Original entry',
              value:
                c.supersedes_id === null ? (
                  '—'
                ) : (
                  <Link component={RouterLink} to={recordPath('WORK_ALLOCATION', c.supersedes_id)}>
                    Open the original
                  </Link>
                ),
            },
            { label: 'Work date', value: formatDate(e?.work_date) },
            { label: 'Reason', value: e?.correction_reason ?? '—' },
            {
              label: 'Proposed by',
              value: <PersonName userId={e?.recorded_by ?? null} name={e?.recorded_by_name} />,
            },
            {
              label: 'Decided by',
              value: <PersonName userId={e?.decided_by ?? null} name={e?.decided_by_name} />,
            },
            { label: 'Decision note', value: e?.decision_note ?? '—' },
          ];
        }}
        history={(c) => {
          const e = first(c);
          return [
            {
              key: 'proposed',
              at: e?.created_at,
              label: 'Proposed',
              by: <PersonName userId={e?.recorded_by ?? null} name={e?.recorded_by_name} />,
              note: e?.correction_reason,
            },
            {
              key: 'decided',
              at: e?.decided_at,
              label: 'Decided',
              by: <PersonName userId={e?.decided_by ?? null} name={e?.decided_by_name} />,
              note: e?.decision_note,
            },
          ];
        }}
      >
        {(c) => (
          <>
            <DetailSection title="Proposed entries">
              <StaticTable
                ariaLabel="Proposed entries"
                columns={columns}
                rows={c.entries}
                getRowId={(a) => a.id}
              />
            </DetailSection>
            <DetailSection title="Evidence">
              <EvidenceList ids={first(c)?.evidence_attachment_ids ?? []} />
            </DetailSection>
          </>
        )}
      </RecordDetail>
      {deciding && res.data !== null && (
        <MeterDecisionDialog
          title="Decide this correction"
          summary={null}
          explanation="Approving replaces the original entry with these parts; the original stays on record. Rejecting leaves the ledger as it is."
          onDecide={(body, key) =>
            allocationService.decideCorrection(res.data?.group_id ?? id ?? '', body, key)
          }
          onDone={() => {
            notify.success('Decision recorded.');
            res.reload();
          }}
          onClose={() => {
            setDeciding(false);
          }}
        />
      )}
    </>
  );
}
