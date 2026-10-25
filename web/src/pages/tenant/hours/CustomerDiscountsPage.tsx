import { PERMISSIONS } from '../../../access/permissionCodes';
import type { DiscountDto } from '../../../api/hoursTypes';
import { discountService } from '../../../api/services/hoursService';
import { DiscountFormDialog } from './proposalForms';
import type { ProposalConfig } from './proposalKit';
import { ProposalDetailPage, ProposalsPage } from './ProposalsPage';
import { useHoursPolicy } from './useHoursPolicy';

/** Discount proposals as the list and detail pages need them (limits from the tenant policy). */
function useDiscountConfig(): ProposalConfig<DiscountDto> {
  const hours = useHoursPolicy();
  return {
    kind: 'HOURS_DISCOUNT',
    title: 'Customer discounts',
    subtitle: 'Approved discounts apply automatically to new hours purchases; nobody types a price',
    noun: 'discount',
    calls: discountService,
    proposePermission: PERMISSIONS.tenantHoursDiscount,
    approvePermission: PERMISSIONS.tenantHoursDiscountApprove,
    allowed: () => true,
    valueColumns: [
      { id: 'percent', header: 'Discount', align: 'right', render: (d) => `${d.percent} %` },
    ],
    valueItems: (d) => [{ label: 'Discount', value: `${d.percent} %` }],
    approveExplanation:
      'Once approved, the discount applies automatically to the customer’s new purchases while it is in effect.',
    renderForm: (props) => (
      <DiscountFormDialog
        {...props}
        reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
        maxPercent={hours.policy?.maxDiscountPercent ?? '100'}
      />
    ),
  };
}

/** Predefined customer discounts: proposed by one person, approved by another, applied automatically. */
export function CustomerDiscountsPage() {
  return <ProposalsPage<DiscountDto> {...useDiscountConfig()} />;
}

/** One customer discount (exact-record link). */
export function CustomerDiscountDetailPage() {
  return <ProposalDetailPage<DiscountDto> {...useDiscountConfig()} />;
}
