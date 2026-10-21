import LockOutlined from '@mui/icons-material/LockOutlined';
import { Button } from '@mui/material';
import { Link } from 'react-router';
import { EmptyState } from '../components/feedback/EmptyState';

export function ForbiddenPage() {
  return (
    <EmptyState
      icon={<LockOutlined fontSize="large" />}
      title="403 — You do not have access"
      description="Your role in the selected console does not include this page. Switch console or ask an administrator."
      action={
        <Button component={Link} to="/" variant="outlined">
          Go home
        </Button>
      }
    />
  );
}
