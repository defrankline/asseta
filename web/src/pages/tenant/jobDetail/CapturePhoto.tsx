import { Stack, Typography } from '@mui/material';
import { meterService } from '../../../api/services/meterService';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';

interface CapturePhotoProps {
  attachmentId: string | null;
  sha256: string | null;
}

/** Capture photo opened on demand (short-lived URL) with its content hash as secondary info. */
export function CapturePhoto({ attachmentId, sha256 }: CapturePhotoProps) {
  if (attachmentId === null && sha256 === null) return <>No photo</>;
  return (
    <Stack spacing={0.5} className="items-start">
      {attachmentId !== null && (
        <AttachmentPhoto
          attachmentId={attachmentId}
          fetchUrl={(id) => meterService.attachmentUrl(id)}
        />
      )}
      {sha256 !== null && (
        <Typography variant="caption" color="text.secondary" className="font-mono" title={sha256}>
          SHA-256 {sha256.slice(0, 12)}…
        </Typography>
      )}
    </Stack>
  );
}
