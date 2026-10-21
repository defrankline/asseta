import CheckCircle from '@mui/icons-material/CheckCircle';
import { Alert, Box, Chip, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import type { Capability, CapabilityDto } from '../../api/types';
import { formatAge, ageSecondsSince, formatInstantIn } from '../../utils/time';

interface CapabilityMatrixProps {
  capabilities: readonly CapabilityDto[];
  /** Display labels per capability code. */
  labels: Readonly<Record<Capability, string>>;
  timeZone: string;
  now: number;
}

export const DECLARED_VS_VERIFIED_NOTE =
  'Declared ≠ verified: a capability is only used for decisions after the device has actually reported it (verified).';

/** Declared (vendor/model) vs verified (observed from the device) capability matrix. */
export function CapabilityMatrix({ capabilities, labels, timeZone, now }: CapabilityMatrixProps) {
  return (
    <Box>
      <Alert severity="info" className="mb-2">
        {DECLARED_VS_VERIFIED_NOTE}
      </Alert>
      {capabilities.length === 0 ? (
        <Alert severity="warning">No capabilities declared or observed for this tracker.</Alert>
      ) : (
        <Table size="small" aria-label="Capability matrix">
          <TableHead>
            <TableRow>
              <TableCell>Capability</TableCell>
              <TableCell>Declared</TableCell>
              <TableCell>Verified</TableCell>
              <TableCell>Last observed</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {capabilities.map((c) => (
              <TableRow key={c.capability} data-testid={`capability-${c.capability}`}>
                <TableCell>{labels[c.capability]}</TableCell>
                <TableCell>{c.declared ? 'Yes' : 'No'}</TableCell>
                <TableCell>
                  {c.verified_at !== null ? (
                    <Box component="span" className="inline-flex items-center gap-1">
                      <CheckCircle fontSize="small" color="success" aria-hidden />
                      <span>Verified {formatInstantIn(c.verified_at, timeZone)}</span>
                    </Box>
                  ) : c.declared ? (
                    <Chip
                      size="small"
                      color="warning"
                      variant="outlined"
                      label="Declared only · not verified"
                    />
                  ) : (
                    'Not verified'
                  )}
                </TableCell>
                <TableCell>
                  {c.last_observed_at === null
                    ? '—'
                    : formatAge(ageSecondsSince(c.last_observed_at, now))}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
}
