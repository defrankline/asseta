import { Box, Paper, Typography } from '@mui/material';
import { CONNECTIVITY_INFO, CONNECTIVITY_ORDER, markerStyle } from './connectivity';

/** Map legend: marker swatch + label for each connectivity state. */
export function ConnectivityLegend() {
  return (
    <Paper variant="outlined" className="p-2" aria-label="Map legend" component="section">
      <Typography variant="caption" component="h2" sx={{ fontWeight: 600 }}>
        Connectivity
      </Typography>
      <Box component="ul" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
        {CONNECTIVITY_ORDER.map((c) => {
          const s = markerStyle(c, c === 'LIVE');
          return (
            <Box component="li" key={c} className="flex items-center gap-1">
              <Box
                aria-hidden
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  border: `2px solid ${s.color}`,
                  bgcolor: s.hollow ? 'transparent' : s.color,
                  opacity: s.hollow ? s.opacity : Math.max(s.fillOpacity, 0.6),
                }}
              />
              <Typography variant="caption">
                {CONNECTIVITY_INFO[c].label}
                {s.live ? '' : ' (last known)'}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
