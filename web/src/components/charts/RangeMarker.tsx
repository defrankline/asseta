import { Box, useTheme } from '@mui/material';

interface RangeMarkerProps {
  value: number;
  low: number;
  high: number;
  median?: number | null;
  /** Accessible description, e.g. `14.2 L/h; usual range 10.1–13.0`. */
  label: string;
  width?: number;
}

const HEIGHT = 16;

/**
 * A value against a usual band: the band is shaded, the median is a tick and the value a dot
 * (outlined when outside the band, so the state is not colour alone). Inline SVG, theme colours.
 */
export function RangeMarker({
  value,
  low,
  high,
  median = null,
  label,
  width = 120,
}: RangeMarkerProps) {
  const theme = useTheme();
  const lo = Math.min(low, value);
  const hi = Math.max(high, value);
  const pad = (hi - lo || 1) * 0.1;
  const x = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * width;
  const outside = value < low || value > high;
  const mid = HEIGHT / 2;
  return (
    <Box component="span" sx={{ display: 'inline-block', lineHeight: 0 }}>
      <svg width={width} height={HEIGHT} role="img" aria-label={label}>
        <title>{label}</title>
        <line x1={0} x2={width} y1={mid} y2={mid} stroke={theme.palette.divider} />
        <rect
          x={x(low)}
          y={mid - 4}
          width={Math.max(2, x(high) - x(low))}
          height={8}
          rx={4}
          fill={theme.palette.action.selected}
        />
        {median !== null && (
          <line
            x1={x(median)}
            x2={x(median)}
            y1={mid - 6}
            y2={mid + 6}
            stroke={theme.palette.text.secondary}
            strokeWidth={2}
          />
        )}
        <circle
          cx={x(value)}
          cy={mid}
          r={5}
          fill={outside ? theme.palette.background.paper : theme.palette.primary.main}
          stroke={theme.palette.primary.main}
          strokeWidth={2}
        />
      </svg>
    </Box>
  );
}
