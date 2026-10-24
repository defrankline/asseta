import { PERMISSIONS } from '../../../access/permissionCodes';
import type { DiscountDto } from '../../../api/hoursTypes';
import { discountService } from '../../../api/services/hoursService';
import { DiscountFormDialog } from './proposalForms';
import { ProposalsPage } from './ProposalsPage';
import { useHoursPolicy } from './useHoursPolicy';

/** Predefined customer discounts: proposed by one person, approved by another, applied automatically. */
export function CustomerDiscountsPage() {
  const hours = useHoursPolicy();
  return (
    <ProposalsPage<DiscountDto>
      title="Customer discounts"
      subtitle="Approved discounts apply automatically to new hours purchases; nobody types a price"
      noun="discount"
      calls={discountService}
      proposePermission={PERMISSIONS.tenantHoursDiscount}
      approvePermission={PERMISSIONS.tenantHoursDiscountApprove}
      allowed={() => true}
      valueColumns={[
        { id: 'percent', header: 'Discount', align: 'right', render: (d) => `${d.percent} %` },
      ]}
      valueItems={(d) => [{ label: 'Discount', value: `${d.percent} %` }]}
      approveExplanation="Once approved, the discount applies automatically to the customer’s new purchases while it is in effect."
      renderForm={(props) => (
        <DiscountFormDialog
          {...props}
          reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
          maxPercent={hours.policy?.maxDiscountPercent ?? '100'}
        />
      )}
    />
  );
}
