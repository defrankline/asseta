import ChevronRight from '@mui/icons-material/ChevronRight';
import { Box, Card, CardContent, Link, Typography } from '@mui/material';
import { useId, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';

export interface KpiRow {
  key: string;
  label: string;
  /** Rendered figure (number or money). */
  value: ReactNode;
  /** Plain-text figure for the link's accessible name. */
  valueText: string;
  /** Filtered list page; omitted when the viewer may not open it. */
  to?: string | undefined;
  /** Show the label as a status chip with this tone (text + tone, never colour alone). */
  tone?: StatusTone;
}

interface KpiCardProps {
  title: string;
  /** Headline figure. */
  value?: ReactNode;
  valueText?: string;
  /** Link for the headline figure. */
  to?: string | undefined;
  description?: string;
  rows?: readonly KpiRow[];
}

const focusRing = {
  '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 },
} as const;

function RowLabel({ row }: { row: KpiRow }) {
  return row.tone !== undefined ? (
    <StatusChip status={row.key} tones={{ [row.key]: row.tone }} label={row.label} />
  ) : (
    <span>{row.label}</span>
  );
}

/** One dashboard figure (or a small breakdown); each figure opens the list it summarises. */
export function KpiCard({ title, value, valueText, to, description, rows = [] }: KpiCardProps) {
  const titleId = useId();
  const headline =
    value === undefined ? null : to !== undefined ? (
      <Link
        component={RouterLink}
        to={to}
        underline="hover"
        color="inherit"
        aria-label={`${title}: ${valueText ?? ''}. Open the list`}
        sx={focusRing}
      >
        {value}
      </Link>
    ) : (
      value
    );
  return (
    <Card variant="outlined" component="article" aria-labelledby={titleId} className="h-full">
      <CardContent>
        <Typography id={titleId} variant="subtitle2" component="h3" color="text.secondary">
          {title}
        </Typography>
        {headline !== null && (
          <Typography
            variant="h4"
            component="p"
            sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}
          >
            {headline}
          </Typography>
        )}
        {description !== undefined && (
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        )}
        {rows.length > 0 && (
          <Box component="ul" className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
            {rows.map((row) => (
              <Box component="li" key={row.key} className="flex items-center justify-between gap-2">
                <RowLabel row={row} />
                {row.to !== undefined ? (
                  <Link
                    component={RouterLink}
                    to={row.to}
                    underline="hover"
                    color="inherit"
                    aria-label={`${title}, ${row.label}: ${row.valueText}. Open the filtered list`}
                    className="inline-flex items-center"
                    sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, ...focusRing }}
                  >
                    {row.value}
                    <ChevronRight fontSize="small" aria-hidden />
                  </Link>
                ) : (
                  <Box
                    component="span"
                    sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}
                  >
                    {row.value}
                  </Box>
                )}
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
