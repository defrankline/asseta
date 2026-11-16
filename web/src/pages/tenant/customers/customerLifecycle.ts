export const CUSTOMER_ERROR_HINTS: Readonly<Record<string, string>> = {
  ALREADY_INACTIVE: 'The customer is already inactive; reload to see the latest state.',
  ALREADY_ACTIVE: 'The customer is already active; reload to see the latest state.',
  DUPLICATE_CODE: 'Another customer already uses this code.',
};

export const CUSTOMER_DEACTIVATE_CONSEQUENCES =
  'No new hours can be sold to it. Its balance and statement stay available.';
