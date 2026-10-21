import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
} from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { ExceptionDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { EvidenceKeyValues } from '../../../components/meter/EvidenceKeyValues';
import {
  EXCEPTION_TYPE_LABELS,
  NEUTRAL_REVIEW_NOTICE,
} from '../../../components/meter/exceptionText';
import { jobDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { humanize } from '../../../utils/text';
import { EXCEPTION_STATUS_LABELS, EXCEPTION_STATUS_TONES } from './exceptionDisplay';
import { ReviewExceptionDialog } from './ReviewExceptionDialog';

interface ExceptionDetailDialogProps {
  exception: ExceptionDto;
  machineName: string;
  timeZone: string;
  onClose: () => void;
  onReviewed: (exception: ExceptionDto) => void;
}

/** Evidence of one exception as labelled values with a plain-language explanation, plus review. */
export function ExceptionDetailDialog({
  exception: e,
  machineName,
  timeZone,
  onClose,
  onReviewed,
}: ExceptionDetailDialogProps) {
  const canReview = useCanMutate(PERMISSIONS.tenantMeterReview);
  const [reviewing, setReviewing] = useState(false);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" aria-labelledby="exception-detail-title">
      <DialogTitle id="exception-detail-title">
        {EXCEPTION_TYPE_LABELS[e.exception_type]}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Alert severity="info">{NEUTRAL_REVIEW_NOTICE}</Alert>
          <Box className="flex flex-wrap items-center gap-2">
            <StatusChip
              status={e.status}
              tones={EXCEPTION_STATUS_TONES}
              label={EXCEPTION_STATUS_LABELS[e.status]}
            />
            <Chip size="small" variant="outlined" label={`Severity: ${humanize(e.severity)}`} />
            {e.blocking && (
              <Chip size="small" variant="outlined" label="Blocks billing until reviewed" />
            )}
          </Box>
          <EvidenceKeyValues type={e.exception_type} evidence={e.evidence} />
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Machine', value: machineName },
              { label: 'Recorded', value: formatInstantIn(e.created_at, timeZone) },
              {
                label: 'Policy version',
                value: <span className="font-mono">{e.policy_version ?? '—'}</span>,
              },
              { label: 'Reviewed', value: formatInstantIn(e.reviewed_at, timeZone) },
              { label: 'Review note', value: e.review_note ?? '—' },
            ]}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        {e.job_id !== null && (
          <Button component={RouterLink} to={jobDetailPath(e.job_id)}>
            Open job
          </Button>
        )}
        <Button onClick={onClose}>Close</Button>
        {canReview && e.status === 'OPEN' && (
          <Button
            variant="contained"
            onClick={() => {
              setReviewing(true);
            }}
          >
            Review
          </Button>
        )}
      </DialogActions>
      {reviewing && (
        <ReviewExceptionDialog
          exception={e}
          onClose={() => {
            setReviewing(false);
          }}
          onReviewed={(r) => {
            onReviewed(r);
            onClose();
          }}
        />
      )}
    </Dialog>
  );
}
