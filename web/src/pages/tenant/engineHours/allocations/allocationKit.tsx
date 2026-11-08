import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { AllocationLotDto } from '../../../../api/allocationTypes';
import { StatusChip } from '../../../../components/display/StatusChip';
import { hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { useSession } from '../../../../session/useSession';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type { AllocationKind, AllocationStatus } from '../../../../api/allocationTypes';
import { KIND_LABELS, KIND_TONES, STATUS_LABELS, STATUS_TONES } from './allocationDisplay';

export const KindChip = ({ kind }: { kind: AllocationKind }) => (
  <StatusChip status={kind} tones={KIND_TONES} label={KIND_LABELS[kind]} />
);

export const AllocationStatusChip = ({ status }: { status: AllocationStatus }) => (
  <StatusChip status={status} tones={STATUS_TONES} label={STATUS_LABELS[status]} />
);

/** Prepaid lots drawn by an entry (per lot hours); links to the purchase for those who can read it. */
export function LotsList({ lots }: { lots: readonly AllocationLotDto[] }) {
  const { hasPermission } = useSession();
  if (lots.length === 0) return <>—</>;
  const canOpen = hasPermission(PERMISSIONS.tenantHoursRead);
  return (
    <span className="flex flex-col gap-0.5">
      {lots.map((l) => {
        const name = `${l.purchase_number ?? 'Lot'} · ${l.hours} h`;
        return canOpen ? (
          <Link
            key={l.purchase_id}
            component={RouterLink}
            to={hoursPurchasePath(l.purchase_id)}
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation();
            }}
          >
            {name}
          </Link>
        ) : (
          <span key={l.purchase_id}>{name}</span>
        );
      })}
    </span>
  );
}
