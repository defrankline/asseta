import { Alert, Stack, Typography } from '@mui/material';
import type { ExceptionType } from '../../api/types';
import { humanize } from '../../utils/text';
import { KeyValueGrid } from '../display/KeyValueGrid';
import { EVIDENCE_KEY_LABELS, evidenceText, explainException } from './exceptionText';

interface EvidenceKeyValuesProps {
  type: ExceptionType;
  evidence: Record<string, unknown>;
  columns?: 1 | 2 | 3;
}

/** Recorded exception evidence as labelled key/values with a plain-language explanation. */
export function EvidenceKeyValues({ type, evidence, columns = 2 }: EvidenceKeyValuesProps) {
  const items = Object.entries(evidence).map(([key, value]) => ({
    label: EVIDENCE_KEY_LABELS[key] ?? humanize(key),
    value: <span className="font-mono">{evidenceText(value)}</span>,
  }));
  return (
    <Stack spacing={1.5}>
      <Alert severity="info" icon={false}>
        {explainException(type, evidence)}
      </Alert>
      {items.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No evidence values recorded.
        </Typography>
      ) : (
        <KeyValueGrid columns={columns} items={items} />
      )}
    </Stack>
  );
}
