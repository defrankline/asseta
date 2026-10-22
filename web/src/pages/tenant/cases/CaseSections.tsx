import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import { Form, Formik } from 'formik';
import { Link as RouterLink } from 'react-router';
import { object, string, type ObjectSchema } from 'yup';
import { caseService } from '../../../api/services/caseService';
import type {
  AnomalyCaseDetailDto,
  CaseNoteDto,
  CaseOutcomeDto,
  CaseSignalDto,
} from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { applySubmitError, statusMessage } from '../../../components/forms/submitHandling';
import {
  caseSignalLabel,
  explainCaseSignal,
  SOURCE_TYPE_LABELS,
} from '../../../components/intelligence/signalText';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { PersonName } from '../shared/PersonName';
import {
  CASE_ERROR_HINTS,
  NOTE_MAX,
  OUTCOME_LABELS,
  OUTCOME_TONES,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  sourceLinks,
} from './caseDisplay';

interface EvidenceProps {
  detail: AnomalyCaseDetailDto;
  timeZone: string;
  /** Opens an expense's evidence (receipts, GPS) in a drawer. */
  onOpenExpense: (expenseId: string) => void;
}

function EvidenceItem({
  signal: s,
  detail,
  timeZone,
  onOpenExpense,
}: EvidenceProps & { signal: CaseSignalDto }) {
  const links = sourceLinks(s, detail.case);
  return (
    <Paper variant="outlined" component="li" className="list-none p-3">
      <Box className="flex flex-wrap items-center gap-2">
        <Typography variant="subtitle2" component="h3">
          {caseSignalLabel(s)}
        </Typography>
        <Chip size="small" variant="outlined" label={SOURCE_TYPE_LABELS[s.source_type]} />
        <StatusChip
          status={s.severity}
          tones={SEVERITY_TONES}
          label={SEVERITY_LABELS[s.severity]}
        />
        <Typography variant="caption" color="text.secondary">
          Observed {formatInstantIn(s.observed_at, timeZone)}
        </Typography>
      </Box>
      <Typography variant="body2" className="mt-2">
        {explainCaseSignal(s, timeZone)}
      </Typography>
      {links.length > 0 && (
        <Box className="mt-2 flex flex-wrap gap-2">
          {links.map((l) =>
            l.kind === 'route' ? (
              <Button key={`${l.label}:${l.to}`} size="small" component={RouterLink} to={l.to}>
                {l.label}
              </Button>
            ) : (
              <Button
                key={`${l.label}:${l.expenseId}`}
                size="small"
                onClick={() => {
                  onOpenExpense(l.expenseId);
                }}
              >
                {l.label}
              </Button>
            ),
          )}
        </Box>
      )}
    </Paper>
  );
}

/** Every linked piece of evidence (any source) with a neutral sentence and links to its source. */
export function EvidenceSection(props: EvidenceProps) {
  const { signals } = props.detail;
  return (
    <DetailSection title="Evidence">
      {signals.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No evidence is linked to this case.
        </Typography>
      ) : (
        <Stack component="ul" spacing={1.5} className="m-0 p-0" aria-label="Linked evidence">
          {signals.map((s) => (
            <EvidenceItem key={s.id} signal={s} {...props} />
          ))}
        </Stack>
      )}
    </DetailSection>
  );
}

interface NoteValues {
  body: string;
}

const noteSchema: ObjectSchema<NoteValues> = object({
  body: string()
    .trim()
    .required('Write a note')
    .max(NOTE_MAX, `At most ${String(NOTE_MAX)} characters`),
});

function AddNoteForm({ caseId, onAdded }: { caseId: string; onAdded: (n: CaseNoteDto) => void }) {
  const keyFor = useIdempotencyKey();
  return (
    <Formik<NoteValues>
      initialValues={{ body: '' }}
      validationSchema={noteSchema}
      onSubmit={async (v, helpers) => {
        helpers.setStatus(undefined);
        const body = { body: v.body.trim() };
        try {
          onAdded(await caseService.addNote(caseId, body, keyFor({ caseId, ...body })));
          helpers.resetForm();
        } catch (err) {
          applySubmitError(withErrorCode(err, CASE_ERROR_HINTS), helpers);
        }
      }}
    >
      {(formik) => (
        <Form noValidate aria-label="Add note">
          <Stack spacing={1}>
            {statusMessage(formik.status) !== null && (
              <Alert severity="error">{statusMessage(formik.status)}</Alert>
            )}
            <FormikTextField name="body" label="Add a note" multiline minRows={2} />
            <Box>
              <Button type="submit" variant="outlined" size="small" loading={formik.isSubmitting}>
                Add note
              </Button>
            </Box>
          </Stack>
        </Form>
      )}
    </Formik>
  );
}

interface NotesProps {
  caseId: string;
  notes: readonly CaseNoteDto[];
  timeZone: string;
  /** May add notes (permission and tenant not read-only). */
  canAdd: boolean;
  onAdded: () => void;
}

/** Append-only notes, oldest first; reopen reasons are marked. */
export function NotesSection({ caseId, notes, timeZone, canAdd, onAdded }: NotesProps) {
  return (
    <DetailSection title="Notes">
      <Stack spacing={1.5}>
        {notes.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No notes yet.
          </Typography>
        )}
        {notes.length > 0 && (
          <Stack component="ol" spacing={1.5} className="m-0 p-0" aria-label="Case notes">
            {notes.map((n) => (
              <Box component="li" key={n.id} className="list-none border-l-2 border-gray-300 pl-3">
                <Typography variant="caption" color="text.secondary">
                  {formatInstantIn(n.created_at, timeZone)} ·{' '}
                  {n.author_name ?? <PersonName userId={n.author_user_id} empty="System" />}
                  {n.kind === 'REOPEN' && ' · Reopened the case'}
                </Typography>
                <Typography variant="body2" className="whitespace-pre-wrap">
                  {n.body}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}
        {canAdd && <AddNoteForm caseId={caseId} onAdded={onAdded} />}
        <Typography variant="caption" color="text.secondary">
          Notes cannot be edited or removed once added.
        </Typography>
      </Stack>
    </DetailSection>
  );
}

/** Every recorded outcome (one per resolution), never changed. */
export function OutcomesSection({
  outcomes,
  timeZone,
}: {
  outcomes: readonly CaseOutcomeDto[];
  timeZone: string;
}) {
  return (
    <DetailSection title="Outcomes">
      {outcomes.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No outcome recorded yet.
        </Typography>
      ) : (
        <Stack component="ol" spacing={1.5} className="m-0 p-0" aria-label="Case outcomes">
          {outcomes.map((o) => (
            <Box component="li" key={o.id} className="list-none">
              <Box className="flex flex-wrap items-center gap-2">
                <StatusChip
                  status={o.outcome}
                  tones={OUTCOME_TONES}
                  label={OUTCOME_LABELS[o.outcome]}
                />
                <Typography variant="caption" color="text.secondary">
                  #{o.sequence} · {formatInstantIn(o.decided_at, timeZone)} ·{' '}
                  {o.decided_by_name ?? <PersonName userId={o.decided_by} />}
                </Typography>
              </Box>
              <Typography variant="body2" className="mt-1 whitespace-pre-wrap">
                {o.explanation}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </DetailSection>
  );
}
