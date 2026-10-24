import { Alert } from '@mui/material';
import { useCallback, useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type {
  AttachmentDto,
  BaselineDto,
  BaselineFromReadingIn,
  BaselineIn,
  MeterCaptureDto,
} from '../../../api/types';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { FormikFieldMachineIdPicker } from '../field/fieldPickers';
import { CONSOLE_DEVICE_ID } from '../jobDetail/capturePolicy';
import type { ReadingMachine } from '../jobDetail/ConsoleCaptureDialog';
import { PhotoAndGps } from '../jobDetail/ReadingEvidence';
import { gpsPendingError, readingField, useBrowserGps } from '../jobDetail/readingEvidenceKit';
import { withErrorCode } from '../shared/errorHints';
import { optionId } from '../shared/lookups';
import { ENGINE_HOURS_ERROR_HINTS } from './engineHoursDisplay';
import { readingOptionLabel, searchMachineReadings } from './engineHoursLookups';

interface BaselineValues {
  machine_id: string;
  reading: string;
  note: string;
}

const NOTE_MAX = 2000;

const baselineSchema = (needsMachine: boolean): ObjectSchema<BaselineValues> =>
  object({
    machine_id: needsMachine ? string().required('Choose the machine') : string().ensure(),
    reading: readingField(),
    note: string()
      .trim()
      .ensure()
      .max(NOTE_MAX, `At most ${String(NOTE_MAX)} characters`),
  });

const SECOND_PERSON =
  'A second person approves the baseline. Until then the machine has no approved starting point for its engine-hour reconciliation.';

interface ProposeBaselineDialogProps {
  /** The machine; omit to let the user choose one. */
  machine?: ReadingMachine;
  onClose: () => void;
  onProposed: (baseline: BaselineDto) => void;
}

/**
 * Propose a machine's initial engine-hour reading with evidence (photo + this browser's GPS outcome).
 * The proposal id is generated once per dialog so retries never create a second proposal.
 */
export function ProposeBaselineDialog({
  machine,
  onClose,
  onProposed,
}: ProposeBaselineDialogProps) {
  const [baselineId] = useState(newUuid);
  const [capturedAt] = useState(() => new Date().toISOString());
  const keyFor = useIdempotencyKey();
  const { gps, retry } = useBrowserGps();
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);
  const needsMachine = machine === undefined;
  return (
    <FormDialog<BaselineValues>
      open
      title={`Propose meter baseline${machine === undefined ? '' : ` · ${machine.label}`}`}
      initialValues={{ machine_id: '', reading: '', note: '' }}
      validationSchema={baselineSchema(needsMachine)}
      submitLabel="Propose baseline"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        if (gps === null) throw gpsPendingError();
        const note = v.note.trim();
        const body: BaselineIn = {
          id: baselineId,
          machine_id: machine?.id ?? v.machine_id,
          reading: v.reading.trim(),
          captured_at: capturedAt,
          photo_attachment_id: photo?.id ?? null,
          gps,
          device_id: CONSOLE_DEVICE_ID,
          note: note === '' ? null : note,
        };
        try {
          onProposed(await engineHoursService.proposeBaseline(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      <Alert severity="info">
        Photograph the hour meter and type the reading shown on it. {SECOND_PERSON}
      </Alert>
      {needsMachine && <FormikFieldMachineIdPicker name="machine_id" label="Machine" required />}
      <FormikTextField
        name="reading"
        label="Meter reading (hours)"
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikTextField name="note" label="Note" multiline minRows={2} />
      <PhotoAndGps
        photo={photo}
        onPhotoChange={setPhoto}
        photoRequired={false}
        gps={gps}
        onRetryGps={retry}
      />
    </FormDialog>
  );
}

interface FromReadingValues {
  capture_id: string;
  note: string;
}

const fromReadingSchema: ObjectSchema<FromReadingValues> = object({
  capture_id: string().ensure(),
  note: string()
    .trim()
    .ensure()
    .max(NOTE_MAX, `At most ${String(NOTE_MAX)} characters`),
});

interface ProposeBaselineFromReadingDialogProps {
  machine: ReadingMachine;
  onClose: () => void;
  onProposed: (baseline: BaselineDto) => void;
}

/** For a machine with earlier readings: propose one of them (default the earliest) as its baseline. */
export function ProposeBaselineFromReadingDialog({
  machine,
  onClose,
  onProposed,
}: ProposeBaselineFromReadingDialogProps) {
  const keyFor = useIdempotencyKey();
  const timeZone = useDisplayTimeZone();
  const search = useCallback(
    (q: string, signal: AbortSignal) => searchMachineReadings(machine.id)(q, signal),
    [machine.id],
  );
  const label = useCallback(
    (c: MeterCaptureDto) => readingOptionLabel(c, (iso) => formatInstantIn(iso, timeZone)),
    [timeZone],
  );
  return (
    <FormDialog<FromReadingValues>
      open
      title={`Baseline from an existing reading · ${machine.label}`}
      initialValues={{ capture_id: '', note: '' }}
      validationSchema={fromReadingSchema}
      submitLabel="Propose baseline"
      onClose={onClose}
      onSubmit={async (v) => {
        const note = v.note.trim();
        const body: BaselineFromReadingIn = {
          machine_id: machine.id,
          capture_id: v.capture_id === '' ? null : v.capture_id,
          note: note === '' ? null : note,
        };
        try {
          onProposed(await engineHoursService.proposeBaselineFromReading(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      <Alert severity="info">
        Leave the reading empty to use the machine&apos;s earliest live reading. {SECOND_PERSON}
      </Alert>
      <FormikAsyncIdAutocomplete<MeterCaptureDto>
        name="capture_id"
        label="Reading (optional)"
        fetchOptions={search}
        getOptionId={optionId}
        getOptionLabel={label}
        noOptionsText="No accepted readings for this machine"
      />
      <FormikTextField name="note" label="Note" multiline minRows={2} />
    </FormDialog>
  );
}
