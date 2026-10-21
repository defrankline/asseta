import ArrowBack from '@mui/icons-material/ArrowBack';
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';

export interface InactiveNotice {
  /** e.g. `This machine is retired.` */
  title: string;
  reason?: string | null;
  /** Already formatted for display. */
  since?: string | null;
}

interface EntityDetailsLayoutProps {
  title: string;
  subtitle?: string;
  back?: { label: string; to: string };
  /** Status chip(s) shown next to the title. */
  status?: ReactNode;
  /** Primary record commands (usually `<ActionButtons>`). */
  actions?: ReactNode;
  /** Shown as a banner when the record is inactive (deactivated, retired, closed, cancelled). */
  inactive?: InactiveNotice | null;
  children: ReactNode;
}

/** Details page frame: back link, title with status, actions, inactive banner and sections. */
export function EntityDetailsLayout({
  title,
  subtitle,
  back,
  status,
  actions,
  inactive = null,
  children,
}: EntityDetailsLayoutProps) {
  return (
    <Stack spacing={3}>
      {back !== undefined && (
        <Box>
          <Button component={RouterLink} to={back.to} startIcon={<ArrowBack />} size="small">
            {back.label}
          </Button>
        </Box>
      )}
      <Box className="flex flex-wrap items-start justify-between gap-4">
        <Box>
          <Box className="flex flex-wrap items-center gap-2">
            <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }}>
              {title}
            </Typography>
            {status}
          </Box>
          {subtitle !== undefined && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions !== undefined && <Box>{actions}</Box>}
      </Box>
      {inactive !== null && (
        <Alert severity="info" role="status">
          <strong>{inactive.title}</strong>
          {inactive.since != null && ` Since ${inactive.since}.`}
          {inactive.reason != null && inactive.reason !== '' && ` Reason: ${inactive.reason}`}
        </Alert>
      )}
      {children}
    </Stack>
  );
}

interface DetailSectionProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}

/** One titled block of a details page (fields, related records, history). */
export function DetailSection({ title, actions, children }: DetailSectionProps) {
  return (
    <Paper variant="outlined" component="section" aria-label={title} className="p-4">
      <Box className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
        {actions}
      </Box>
      {children}
    </Paper>
  );
}
