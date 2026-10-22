import { Box, useTheme } from '@mui/material';

export interface MiniBar {
  /** Stable key (e.g. the week end). */
  key: string;
  value: number;
  /** Hover text for this bar, e.g. `Week ending 12 Oct: 31.5 h`. */
  title: string;
}

interface MiniBarsProps {
  bars: readonly MiniBar[];
  /** Accessible summary of the whole series (the table next to it carries the values). */
  label: string;
  width?: number;
  height?: number;
}

const GAP = 2;

/**
 * Small single-series bar chart (inline SVG, theme colours, no chart library). Negative values hang
 * below a zero baseline. Each bar has a native tooltip; the series is summarised by `label`.
 */
export function MiniBars({ bars, label, width = 160, height = 40 }: MiniBarsProps) {
  const theme = useTheme();
  if (bars.length === 0) return null;
  const max = Math.max(0, ...bars.map((b) => b.value));
  const min = Math.min(0, ...bars.map((b) => b.value));
  const span = max - min || 1;
  const zeroY = (max / span) * height;
  const barWidth = Math.max(2, (width - GAP * (bars.length - 1)) / bars.length);
  return (
    <Box component="span" sx={{ display: 'inline-block', lineHeight: 0 }}>
      <svg width={width} height={height} role="img" aria-label={label}>
        {bars.map((b, i) => {
          const h = Math.max(1, (Math.abs(b.value) / span) * height);
          const y = b.value >= 0 ? zeroY - h : zeroY;
          return (
            <rect
              key={b.key}
              x={i * (barWidth + GAP)}
              y={y}
              width={barWidth}
              height={h}
              rx={Math.min(2, barWidth / 2)}
              fill={theme.palette.primary.main}
              opacity={b.value === 0 ? 0.35 : 1}
            >
              <title>{b.title}</title>
            </rect>
          );
        })}
        <line x1={0} x2={width} y1={zeroY} y2={zeroY} stroke={theme.palette.divider} />
      </svg>
    </Box>
  );
}
