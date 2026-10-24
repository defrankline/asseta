import { engineHoursService } from '../../../api/services/engineHoursService';
import type { BaselineDto, ClassificationDto, CorrectionDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { meterService } from '../../../api/services/meterService';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';
import { hoursText, OUTCOME_LABELS } from './engineHoursDisplay';
import { MeterDecisionDialog } from './MeterDecisionDialog';

const machineText = (code: string | null | undefined, name?: string | null) =>
  code == null ? '—' : name == null ? code : `${code} · ${name}`;

interface DecideProps<T> {
  timeZone: string;
  onClose: () => void;
  onDecided: (result: T) => void;
}

/** Approve or reject a proposed meter baseline (never one's own). */
export function DecideBaselineDialog({
  baseline,
  timeZone,
  onClose,
  onDecided,
}: DecideProps<BaselineDto> & { baseline: BaselineDto }) {
  return (
    <MeterDecisionDialog<BaselineDto>
      title={`Decide baseline · ${machineText(baseline.machine_code, baseline.machine_name)}`}
      summary={
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Reading', value: hoursText(baseline.reading) },
            { label: 'Taken', value: formatInstantIn(baseline.captured_at, timeZone) },
            { label: 'Proposed by', value: <PersonName userId={baseline.proposed_by} /> },
            {
              label: 'Source',
              value: baseline.source === 'READING' ? 'An existing reading' : 'New reading',
            },
            { label: 'Note', value: baseline.note ?? '—' },
            {
              label: 'Photo',
              value:
                baseline.photo_attachment_id === null ? (
                  'None'
                ) : (
                  <AttachmentPhoto
                    attachmentId={baseline.photo_attachment_id}
                    fetchUrl={(id) => meterService.attachmentUrl(id)}
                    label="View photo"
                  />
                ),
            },
          ]}
        />
      }
      explanation="Approving makes this reading the machine's starting point: engine hours are reconciled from it. Rejecting leaves the machine without a baseline until a new one is proposed."
      onDecide={(body, key) => engineHoursService.decideBaseline(baseline.id, body, key)}
      onDone={onDecided}
      onClose={onClose}
    />
  );
}

/** Approve or reject a proposed explanation of unallocated hours (never one's own). */
export function DecideClassificationDialog({
  classification: c,
  timeZone,
  onClose,
  onDecided,
}: DecideProps<ClassificationDto> & { classification: ClassificationDto }) {
  return (
    <MeterDecisionDialog<ClassificationDto>
      title={`Decide explanation · ${hoursText(c.hours)} · ${machineText(c.machine_code)}`}
      summary={
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Hours', value: hoursText(c.hours) },
            {
              label: 'Period',
              value: `${formatInstantIn(c.start_at, timeZone)} → ${formatInstantIn(c.end_at, timeZone)}`,
            },
            { label: 'Explained as', value: OUTCOME_LABELS[c.outcome] },
            { label: 'Category / reason', value: c.reason_name ?? '—' },
            { label: 'What happened', value: c.note },
            { label: 'Proposed by', value: <PersonName userId={c.proposed_by} /> },
          ]}
        />
      }
      explanation="Approving records these hours with this explanation. Rejecting leaves them not yet explained, so they can be explained again."
      onDecide={(body, key) => engineHoursService.decideClassification(c.id, body, key)}
      onDone={onDecided}
      onClose={onClose}
    />
  );
}

/** Approve or reject a proposed reading correction (never one's own). */
export function DecideCorrectionDialog({
  correction: c,
  timeZone,
  onClose,
  onDecided,
}: DecideProps<CorrectionDto> & { correction: CorrectionDto }) {
  return (
    <MeterDecisionDialog<CorrectionDto>
      title={`Decide correction · ${machineText(c.machine_code)}`}
      summary={
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Reading (old → new)', value: `${c.old_reading} → ${c.new_reading}` },
            { label: 'Proposed', value: formatInstantIn(c.proposed_at, timeZone) },
            { label: 'Reason', value: c.reason },
            { label: 'Proposed by', value: <PersonName userId={c.proposed_by} /> },
          ]}
        />
      }
      explanation="Approving supersedes the old reading with the corrected one (both stay on record) and the engine-hour ledger is recalculated. Rejecting keeps the old reading."
      onDecide={(body, key) => engineHoursService.decideCorrection(c.id, body, key)}
      onDone={onDecided}
      onClose={onClose}
    />
  );
}
