import { Button } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { meterService } from '../../../api/services/meterService';
import type { BaselineDto, ClassificationDto, CorrectionDto } from '../../../api/types';
import type { KeyValueItem } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, jobDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { machineText } from '../shared/names';
import { PersonName } from '../shared/PersonName';
import type { HistoryEvent } from '../shared/RecordDetail';
import {
  DecideBaselineDialog,
  DecideClassificationDialog,
  DecideCorrectionDialog,
} from './DecideDialogs';
import {
  hoursText,
  OUTCOME_LABELS,
  OWN_PROPOSAL_TEXT,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_TONES,
} from './engineHoursDisplay';
import { DecideButton } from './MeterDecisionDialog';

/** Fields every engine-hour proposal carries. */
interface Proposal {
  id: string;
  status: BaselineDto['status'];
  machine_id: string;
  machine_code?: string | null;
  machine_name?: string | null;
  proposed_by: string | null;
  proposed_by_name?: string | null;
  proposed_at: string;
  decided_by: string | null;
  decided_by_name?: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

export const proposalChip = (r: Proposal) => (
  <StatusChip
    status={r.status}
    tones={PROPOSAL_STATUS_TONES}
    label={PROPOSAL_STATUS_LABELS[r.status]}
  />
);

export const machineOf = (r: Proposal) => machineText(r.machine_code, r.machine_name, r.machine_id);

/** "Engine hours" link to the record's machine ledger. */
export const engineHoursLink = (r: Proposal) => (
  <Button component={RouterLink} to={engineHoursMachinePath(r.machine_id)}>
    Engine hours
  </Button>
);

/** Decide command, dialog, details and history of one kind of engine-hour proposal. */
export interface EngineKit<T> {
  /** List cell: the Decide button (disabled with an explanation on your own proposal). */
  decideCell: (r: T) => ReactNode;
  /** The same command for a detail page. */
  actionsFor: (r: T) => RowAction[];
  dialog: ReactNode;
  items: (r: T) => KeyValueItem[];
  history: (r: T) => HistoryEvent[];
}

type DialogProps<T> = {
  timeZone: string;
  onClose: () => void;
  onDecided: (r: T) => void;
};

function useEngineKit<T extends Proposal>(
  permission: string,
  noun: string,
  renderDialog: (r: T, props: DialogProps<T>) => ReactNode,
  ownItems: (r: T, timeZone: string) => KeyValueItem[],
  onChanged: (r: T) => void,
): EngineKit<T> {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { me } = useSession();
  const canDecide = useCanMutate(permission);
  const [deciding, setDeciding] = useState<T | null>(null);
  const own = (r: T) => me !== null && r.proposed_by === me.user_id;
  const decideCell = (r: T) =>
    canDecide && r.status === 'PROPOSED' ? (
      <DecideButton
        proposedBy={r.proposed_by}
        onClick={() => {
          setDeciding(r);
        }}
      />
    ) : null;
  const actionsFor = (r: T): RowAction[] => [
    {
      key: 'decide',
      label: 'Decide',
      hidden: !canDecide || r.status !== 'PROPOSED',
      disabled: own(r),
      disabledReason: OWN_PROPOSAL_TEXT,
      onClick: () => {
        setDeciding(r);
      },
    },
  ];
  const items = (r: T): KeyValueItem[] => [
    { label: 'Machine', value: machineOf(r) },
    ...ownItems(r, timeZone),
    {
      label: 'Proposed by',
      value: <PersonName userId={r.proposed_by} name={r.proposed_by_name} />,
    },
    { label: 'Proposed', value: formatInstantIn(r.proposed_at, timeZone) },
    { label: 'Decided by', value: <PersonName userId={r.decided_by} name={r.decided_by_name} /> },
    {
      label: 'Decided',
      value: r.decided_at === null ? '—' : formatInstantIn(r.decided_at, timeZone),
    },
    { label: 'Decision note', value: r.decision_note ?? '—' },
  ];
  const history = (r: T): HistoryEvent[] => [
    {
      key: 'proposed',
      at: r.proposed_at,
      label: 'Proposed',
      by: <PersonName userId={r.proposed_by} name={r.proposed_by_name} />,
    },
    {
      key: 'decided',
      at: r.status === 'PROPOSED' ? null : r.decided_at,
      label: PROPOSAL_STATUS_LABELS[r.status],
      by: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
      note: r.decision_note,
    },
  ];
  const dialog =
    deciding === null
      ? null
      : renderDialog(deciding, {
          timeZone,
          onClose: () => {
            setDeciding(null);
          },
          onDecided: (r) => {
            notify.success(`${noun} ${PROPOSAL_STATUS_LABELS[r.status].toLowerCase()}.`);
            onChanged(r);
          },
        });
  return { decideCell, actionsFor, dialog, items, history };
}

const gps = (b: BaselineDto) =>
  b.latitude === null || b.longitude === null
    ? 'No fix'
    : `${String(b.latitude)}, ${String(b.longitude)}${
        b.accuracy_m === null ? '' : ` (±${String(b.accuracy_m)} m)`
      }`;

export const baselineSource = (b: BaselineDto) =>
  b.source === 'READING' ? 'Existing reading' : 'New reading';

/** Meter baselines: decided by someone other than the proposer (meter approve permission). */
export function useBaselineKit(onChanged: (b: BaselineDto) => void): EngineKit<BaselineDto> {
  return useEngineKit<BaselineDto>(
    PERMISSIONS.tenantMeterApprove,
    'Baseline',
    (b, props) => <DecideBaselineDialog baseline={b} {...props} />,
    (b, timeZone) => [
      { label: 'Reading', value: hoursText(b.reading) },
      { label: 'Taken', value: formatInstantIn(b.captured_at, timeZone) },
      { label: 'Source', value: baselineSource(b) },
      { label: 'Note', value: b.note ?? '—' },
      { label: 'GPS', value: gps(b) },
      {
        label: 'Photo',
        value:
          b.photo_attachment_id === null ? (
            'None'
          ) : (
            <AttachmentPhoto
              attachmentId={b.photo_attachment_id}
              fetchUrl={(id) => meterService.attachmentUrl(id)}
              label="View photo"
            />
          ),
      },
    ],
    onChanged,
  );
}

/** Reading corrections: decided by someone other than the proposer (meter approve permission). */
export function useCorrectionKit(onChanged: (c: CorrectionDto) => void): EngineKit<CorrectionDto> {
  return useEngineKit<CorrectionDto>(
    PERMISSIONS.tenantMeterApprove,
    'Correction',
    (c, props) => <DecideCorrectionDialog correction={c} {...props} />,
    (c) => [
      { label: 'Old reading', value: c.old_reading },
      { label: 'New reading', value: c.new_reading },
      { label: 'Reason', value: c.reason },
      {
        label: 'Job',
        value:
          c.job_id === null ? (
            'None (daily reading)'
          ) : (
            <RouterLink to={jobDetailPath(c.job_id)}>{c.job_number ?? 'Open job'}</RouterLink>
          ),
      },
      { label: 'Policy', value: c.policy_version },
    ],
    onChanged,
  );
}

/** Explanations of unallocated hours: decided by someone else (meter classify permission). */
export function useClassificationKit(
  onChanged: (c: ClassificationDto) => void,
): EngineKit<ClassificationDto> {
  return useEngineKit<ClassificationDto>(
    PERMISSIONS.tenantMeterClassify,
    'Explanation',
    (c, props) => <DecideClassificationDialog classification={c} {...props} />,
    (c, timeZone) => [
      { label: 'Hours', value: hoursText(c.hours) },
      { label: 'From', value: formatInstantIn(c.start_at, timeZone) },
      { label: 'To', value: formatInstantIn(c.end_at, timeZone) },
      { label: 'Explained as', value: OUTCOME_LABELS[c.outcome] },
      { label: 'Category / reason', value: c.reason_name ?? '—' },
      { label: 'What happened', value: c.note },
      { label: 'Policy', value: c.policy_version },
    ],
    onChanged,
  );
}
