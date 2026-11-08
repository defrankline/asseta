import { Box, Chip, Typography } from '@mui/material';
import { meterService } from '../../../../api/services/meterService';
import type { AttachmentDto } from '../../../../api/types';
import { AttachmentPhoto } from '../../../../components/meter/AttachmentPhoto';
import { AttachmentUpload } from '../../../../components/meter/AttachmentUpload';
import { useMeterPhotoUpload } from '../../jobDetail/readingEvidenceKit';

/** The server keeps at most this many evidence attachments per record. */
const MAX_EVIDENCE = 10;

interface EvidenceUploadProps {
  value: AttachmentDto[];
  onChange: (value: AttachmentDto[]) => void;
  label?: string;
  helperText?: string;
}

/** Several evidence photos on one record: each file uploads at once; a chip removes it again. */
export function EvidenceUpload({
  value,
  onChange,
  label = 'Evidence (photos)',
  helperText = 'Photos are stored unchanged with their SHA-256 hash.',
}: EvidenceUploadProps) {
  const upload = useMeterPhotoUpload();
  return (
    <Box className="flex flex-col gap-1">
      {value.length < MAX_EVIDENCE && (
        <AttachmentUpload
          key={value.length}
          label={label}
          value={null}
          onChange={(a) => {
            if (a !== null) onChange([...value, a]);
          }}
          upload={upload}
          helperText={helperText}
        />
      )}
      {value.length > 0 && (
        <Box className="flex flex-wrap gap-1" aria-label="Attached evidence">
          {value.map((a, i) => (
            <Chip
              key={a.id}
              size="small"
              label={`Photo ${String(i + 1)}`}
              onDelete={() => {
                onChange(value.filter((x) => x.id !== a.id));
              }}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}

/** Read-only evidence photos of a record, each fetched on demand. */
export function EvidenceList({ ids }: { ids: readonly string[] }) {
  if (ids.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        None attached.
      </Typography>
    );
  }
  return (
    <Box className="flex flex-col gap-2">
      {ids.map((id, i) => (
        <AttachmentPhoto
          key={id}
          attachmentId={id}
          fetchUrl={(a) => meterService.attachmentUrl(a)}
          label={`View evidence ${String(i + 1)}`}
        />
      ))}
    </Box>
  );
}
