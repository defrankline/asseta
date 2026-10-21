import type { CustomerDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import type { CustomerFormValues } from './customerForm';

/** Review step content for a customer form. */
export function CustomerReview({ values: v }: { values: CustomerFormValues }) {
  return (
    <KeyValueGrid
      columns={2}
      items={[
        { label: 'Code', value: v.code.trim() },
        { label: 'Name', value: v.name.trim() },
        { label: 'Tax ID', value: v.tax_id.trim() || '—' },
        { label: 'Payment terms', value: `${v.payment_terms_days} days` },
        { label: 'Contact', value: v.contact_name.trim() || '—' },
        { label: 'Phone', value: v.contact_phone.trim() || '—' },
        { label: 'Email', value: v.contact_email.trim() || '—' },
      ]}
    />
  );
}

/** Read-only customer record (details page). */
export function CustomerFields({ customer: c }: { customer: CustomerDto }) {
  return (
    <KeyValueGrid
      columns={4}
      items={[
        { label: 'Code', value: c.code },
        { label: 'Name', value: c.name },
        { label: 'Tax ID', value: c.tax_id ?? '—' },
        { label: 'Payment terms', value: `${String(c.payment_terms_days)} days` },
        { label: 'Contact', value: c.contact_name ?? '—' },
        { label: 'Phone', value: c.contact_phone ?? '—' },
        { label: 'Email', value: c.contact_email ?? '—' },
        { label: 'Version', value: String(c.version) },
      ]}
    />
  );
}
