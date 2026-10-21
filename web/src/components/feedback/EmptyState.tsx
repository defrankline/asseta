import InboxOutlined from '@mui/icons-material/InboxOutlined';
import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <Box className="flex flex-col items-center gap-2 py-12 text-center">
      <Box color="text.disabled" aria-hidden>
        {icon ?? <InboxOutlined fontSize="large" />}
      </Box>
      <Typography variant="subtitle1">{title}</Typography>
      {description !== undefined && (
        <Typography variant="body2" color="text.secondary" className="max-w-md">
          {description}
        </Typography>
      )}
      {action}
    </Box>
  );
}
