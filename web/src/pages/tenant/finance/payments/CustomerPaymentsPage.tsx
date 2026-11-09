import { PageHeader } from '../../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { PaymentsTab } from './PaymentsTab';

/** Standalone customer payments list: where dashboard figures link (status, method, period). */
export function CustomerPaymentsPage() {
  const timeZone = useDisplayTimeZone();
  return (
    <>
      <PageHeader
        title="Customer payments"
        subtitle="Payments recorded against customers: claimed until someone other than the recorder verifies them"
      />
      <PaymentsTab timeZone={timeZone} />
    </>
  );
}
