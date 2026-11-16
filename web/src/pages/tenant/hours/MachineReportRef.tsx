import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { machineReportPath } from '../../../navigation/routes';

/** The machine report an hours entry came from (MR-…), linked; "—" when there is none. */
export function MachineReportRef({
  id,
  number,
}: {
  id?: string | null | undefined;
  number?: string | null | undefined;
}) {
  if (id == null) return <>—</>;
  return (
    <Link component={RouterLink} to={machineReportPath(id)}>
      {number ?? 'Machine report'}
    </Link>
  );
}
