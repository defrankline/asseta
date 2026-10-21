import SearchOff from '@mui/icons-material/SearchOff';
import { Button } from '@mui/material';
import { Link } from 'react-router';
import { EmptyState } from '../components/feedback/EmptyState';

export function NotFoundPage() {
  return (
    <EmptyState
      icon={<SearchOff fontSize="large" />}
      title="404 — Page not found"
      description="This page does not exist or is not available in this release."
      action={
        <Button component={Link} to="/" variant="outlined">
          Go home
        </Button>
      }
    />
  );
}
