import { Alert, Box, Typography } from '@mui/material';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { humanize } from '../../../utils/text';
import { KpiCard } from '../dashboard/KpiCard';
import { buildTiles, TILE_LABELS, type Can } from './accountabilityModel';

/** The accountability tiles plus a note of tiles hidden by policy or unavailable here. */
export function AccountabilityTiles({ data, can }: { data: AccountabilitySummaryDto; can: Can }) {
  const tiles = buildTiles(data, can);
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
      {data.hidden_tiles.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          Hidden by your organisation’s oversight policy: {names(data.hidden_tiles)}.
        </Typography>
      )}
      {data.unavailable_tiles.length > 0 && (
        <Typography variant="body2" color="text.secondary">
          Not available yet: {names(data.unavailable_tiles)}.
        </Typography>
      )}
    </Box>
  );
}
