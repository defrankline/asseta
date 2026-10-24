import { Alert, Box, Chip, Stack, Typography } from '@mui/material';
import type { CaptureResultDto } from '../../../api/types';
import { CaptureStateChip } from '../../../components/meter/CaptureStateChip';
import {
  EXCEPTION_TYPE_LABELS,
  explainException,
  NEUTRAL_REVIEW_NOTICE,
} from '../../../components/meter/exceptionText';
import { humanize } from '../../../utils/text';

const OUTCOME: Readonly<
  Record<string, { severity: 'success' | 'warning' | 'error'; text: string }>
> = {
  ACCEPTED: { severity: 'success', text: 'The reading was accepted.' },
  PROVISIONAL: {
    severity: 'warning',
    text: 'The reading was kept and counts for the job, and the findings below are listed for office review.',
  },
  REJECTED: {
    severity: 'error',
    text: 'The reading was stored as evidence but not accepted under the policy. Record it again (for example once a GPS fix is available).',
  },
};

interface CaptureResultPanelProps {
  result: CaptureResultDto;
  onDismiss: () => void;
}

/** The server's verdict on the reading just submitted: state plus each finding, explained neutrally. */
export function CaptureResultPanel({ result, onDismiss }: CaptureResultPanelProps) {
  const c = result.capture;
  const outcome = OUTCOME[c.state] ?? { severity: 'warning' as const, text: humanize(c.state) };
  return (
    <Alert
      severity={outcome.severity}
      onClose={onDismiss}
      aria-label="Reading result"
      sx={{ '& .MuiAlert-message': { width: '100%' } }}
    >
      <Stack spacing={1}>
        <Box className="flex flex-wrap items-center gap-2">
          <Typography variant="subtitle2" component="span">
            {humanize(c.kind)} reading {c.reading} submitted
          </Typography>
          <CaptureStateChip state={c.state} />
        </Box>
        <Typography variant="body2">{outcome.text}</Typography>
        {result.findings.length > 0 && (
          <>
            <Box component="ul" className="m-0 flex flex-col gap-1 pl-5">
              {result.findings.map((f) => (
                <li key={f.type}>
                  <Typography variant="body2" component="span" sx={{ fontWeight: 600 }}>
                    {EXCEPTION_TYPE_LABELS[f.type]}
                  </Typography>
                  {f.blocking && (
                    <Chip
                      size="small"
                      variant="outlined"
                      label="Requires review"
                      className="ml-2"
                    />
                  )}
                  <Typography variant="body2" component="div">
                    {explainException(f.type, f.evidence)}
                  </Typography>
                </li>
              ))}
            </Box>
            <Typography variant="caption">{NEUTRAL_REVIEW_NOTICE}</Typography>
          </>
        )}
      </Stack>
    </Alert>
  );
}
