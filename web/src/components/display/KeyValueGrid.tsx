import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export interface KeyValueItem {
  label: string;
  value: ReactNode;
}

interface KeyValueGridProps {
  items: readonly KeyValueItem[];
  /** Columns at the widest breakpoint (default 3). */
  columns?: 1 | 2 | 3 | 4;
}

/** Read-only labelled values laid out in a responsive grid (definition list semantics). */
export function KeyValueGrid({ items, columns = 3 }: KeyValueGridProps) {
  return (
    <Box
      component="dl"
      sx={{
        display: 'grid',
        gap: 2,
        m: 0,
        gridTemplateColumns: {
          xs: '1fr',
          sm: `repeat(${String(Math.min(columns, 2))}, minmax(0, 1fr))`,
          md: `repeat(${String(columns)}, minmax(0, 1fr))`,
        },
      }}
    >
      {items.map((item) => (
        <Box key={item.label} sx={{ minWidth: 0 }}>
          <Typography component="dt" variant="caption" color="text.secondary">
            {item.label}
          </Typography>
          <Typography component="dd" variant="body2" sx={{ m: 0, overflowWrap: 'anywhere' }}>
            {item.value ?? '—'}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
