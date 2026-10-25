import { useParams } from 'react-router';
import { hoursRequestService } from '../../../api/services/hoursService';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { HOURS_ROUTES } from '../../../navigation/hoursRoutes';
import { nameOr } from '../shared/names';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import {
  requestStatusChip,
  transferTitle,
  useCancellationRequests,
  useTransferRequests,
} from './useHoursRequests';

const loadTransfer = (id: string, signal: AbortSignal) =>
  hoursRequestService.getTransfer(id, signal);
const loadCancellation = (id: string, signal: AbortSignal) =>
  hoursRequestService.getCancellation(id, signal);

/** One hours transfer between machines (exact-record link): details, decide / withdraw, history. */
export function HoursTransferDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadTransfer, id);
  const kit = useTransferRequests(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="hours transfer"
        back={{ label: 'Hours transfers', to: HOURS_ROUTES.transfers }}
        timeZone={timeZone}
        title={transferTitle}
        subtitle={(t) => `${t.purchase_number ?? 'Purchase'} · ${nameOr(t.customer_name, null)}`}
        status={(t) => requestStatusChip(t.status)}
        actions={kit.actionsFor}
        primaryKey="decide"
        items={kit.items}
        history={kit.history}
      />
      {kit.dialogs}
    </>
  );
}

/** One hours purchase cancellation request (exact-record link): details, decide / withdraw, history. */
export function HoursCancellationDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadCancellation, id);
  const kit = useCancellationRequests(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="cancellation request"
        back={{ label: 'Hours cancellations', to: HOURS_ROUTES.cancellations }}
        timeZone={timeZone}
        title={(c) => `Cancellation · ${c.purchase_number ?? 'hours purchase'}`}
        subtitle={(c) => nameOr(c.customer_name, null)}
        status={(c) => requestStatusChip(c.status)}
        actions={kit.actionsFor}
        primaryKey="decide"
        items={kit.items}
        history={kit.history}
      />
      {kit.dialogs}
    </>
  );
}
