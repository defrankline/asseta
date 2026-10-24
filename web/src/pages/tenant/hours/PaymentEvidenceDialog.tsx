import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { newIdempotencyKey } from '../../../api/ids';
import { hoursService } from '../../../api/services/hoursService';
import type { AttachmentDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';

/**
 * Evidence (receipt photo, mobile-money screenshot) of one customer payment. Evidence never verifies
 * a payment: it stays claimed until someone else verifies it.
 */
export function PaymentEvidenceDialog({
  paymentId,
  canAttach,
  onClose,
}: {
  paymentId: string;
  canAttach: boolean;
  onClose: () => void;
}) {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [pending, setPending] = useState<AttachmentDto | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => hoursService.listEvidence(paymentId, signal),
    [paymentId],
  );
  const evidence = useAsyncResource(load);
  const attach = async (a: AttachmentDto) => {
    setBusy(true);
    try {
      await hoursService.attachEvidence(paymentId, { attachment_ids: [a.id] }, newIdempotencyKey());
      notify.success('Evidence attached.');
      setPending(null);
      evidence.reload();
    } catch (err) {
      notify.error(err, 'Could not attach the evidence.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="payment-evidence">
      <DialogTitle id="payment-evidence">Payment evidence</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <AsyncContent
            resource={evidence}
            isEmpty={(rows) => rows.length === 0}
            emptyTitle="No evidence attached"
            errorTitle="Could not load the evidence"
          >
            {(rows) => (
              <Stack spacing={1}>
                {rows.map((e) => (
                  <Box key={e.id} className="flex flex-wrap items-center gap-3">
                    <AttachmentPhoto
                      attachmentId={e.attachment_id}
                      fetchUrl={(id) => hoursService.evidenceUrl(paymentId, id)}
                      label="View evidence"
                    />
                    <Typography variant="body2" color="text.secondary">
                      {formatInstantIn(e.created_at, timeZone)} ·{' '}
                      <PersonName userId={e.created_by} />
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </AsyncContent>
          {canAttach && (
            <>
              <AttachmentUpload
                label="Add evidence photo"
                value={pending}
                onChange={setPending}
                upload={(file) => hoursService.uploadEvidence(file, newIdempotencyKey())}
                preview
              />
              {pending !== null && (
                <Button
                  variant="contained"
                  disabled={busy}
                  onClick={() => {
                    void attach(pending);
                  }}
                >
                  Attach to payment
                </Button>
              )}
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
