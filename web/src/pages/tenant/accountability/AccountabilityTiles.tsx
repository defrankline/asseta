import { Alert, Box, Typography } from '@mui/material';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { humanize } from '../../../utils/text';
import { KpiCard } from '../dashboard/KpiCard';
import { buildTiles, CUSTOMER_HOURS_TILES, TILE_LABELS, type Can } from './accountabilityModel';

/** The accountability tiles plus a note of tiles hidden by policy or unavailable here. */
export function AccountabilityTiles({ data, can }: { data: AccountabilitySummaryDto; can: Can }) {
  const customerHours = useCapabilityEnabled(CAPABILITY.customerHours);
  const tiles = buildTiles(data, can, { customerHours });
  /** Tiles of a capability the tenant switched off are not mentioned at all. */
  const mentioned = (keys: readonly string[]) =>
    customerHours ? keys : keys.filter((k) => !CUSTOMER_HOURS_TILES.has(k));
  const hidden = mentioned(data.hidden_tiles);
  const unavailable = mentioned(data.unavailable_tiles);
  const names = (keys: readonly string[]) =>
    keys.map((k) => TILE_LABELS[k] ?? humanize(k)).join(', ');
  return (
    <Box className="flex flex-col gap-3">
      {tiles.length === 0 ? (
        <Alert severity="info">Your organisation’s oversight policy hides every tile.</Alert>
      ) : (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {tiles.map((t) => (
            <KpiCard
              key={t.key}
              title={t.title}
              value={t.value}
              {...(t.valueText !== undefined ? { valueText: t.valueText } : {})}
              to={t.to}
              {...(t.description !== undefined ? { description: t.description } : {})}
              rows={t.rows ?? []}
            />
          ))}
        </Box>
      )}
      {hidden.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          Hidden by your organisation’s oversight policy: {names(hidden)}.
        </Typography>
      )}
      {unavailable.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          Not available yet: {names(unavailable)}.
        </Typography>
      )}
    </Box>
  );
}
