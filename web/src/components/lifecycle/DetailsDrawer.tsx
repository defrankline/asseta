import Close from '@mui/icons-material/Close';
import { Box, Divider, Drawer, IconButton, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface DetailsDrawerProps {
  title: string;
  status?: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}

/** Side panel for viewing a record without leaving its list. Mount only while open. */
export function DetailsDrawer({ title, status, actions, onClose, children }: DetailsDrawerProps) {
  return (
    <Drawer
      anchor="right"
      open
      onClose={onClose}
      slotProps={{ paper: { sx: { width: { xs: '100%', sm: 560 } } } }}
    >
      <Box className="flex items-center justify-between gap-2 p-3">
        <Box className="flex flex-wrap items-center gap-2">
          <Typography variant="h6" component="h2">
            {title}
          </Typography>
          {status}
        </Box>
        <IconButton aria-label="Close" onClick={onClose}>
          <Close />
        </IconButton>
      </Box>
      <Divider />
      <Stack spacing={2} className="p-3">
        {actions}
        {children}
      </Stack>
    </Drawer>
  );
}
