import { Box, CircularProgress, Typography } from '@mui/material';

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = 'Loading' }: LoadingStateProps) {
  return (
    <Box role="status" aria-live="polite" className="flex flex-col items-center gap-3 py-12">
      <CircularProgress size={32} aria-hidden />
      <Typography variant="body2" color="text.secondary">
        {label}…
      </Typography>
    </Box>
  );
}
