import Add from '@mui/icons-material/Add';
import { Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { object, string, type ObjectSchema } from 'yup';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { newUuid } from '../../../api/ids';
import { customerService } from '../../../api/services/customerService';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { customerDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { integerField } from '../../platform/shared/validators';
import { withErrorCode } from '../shared/errorHints';
import { optionalText, orNull } from '../shared/formRules';
import { HoursOffNotice } from './HoursDialogs';
import { HOURS_ERROR_HINTS } from './hoursDisplay';
import { useHoursPolicy } from './useHoursPolicy';

interface WalkInValues {
  name: string;
  phone: string;
}

const walkInSchema: ObjectSchema<WalkInValues> = object({
  name: string().trim().required('Name is required').max(200, 'At most 200 characters'),
  phone: string()
    .trim()
    .ensure()
    .test(
      'phone',
      'Phone must be 3–40 characters',
      (v) => v === '' || (v.length >= 3 && v.length <= 40),
    ),
});

function WalkInDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  return (
    <FormDialog<WalkInValues>
      open
      title="New walk-in customer"
      initialValues={{ name: '', phone: '' }}
      validationSchema={walkInSchema}
      submitLabel="Create walk-in"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { name: v.name.trim(), phone: orNull(v.phone), client_id: clientId };
        try {
          await hoursService.createWalkIn(body, keyFor(body));
          onSaved();
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      <FormikTextField name="name" label="Name" required />
      <FormikTextField name="phone" label="Phone (optional)" />
    </FormDialog>
  );
}

interface RegisterValues {
  code: string;
  name: string;
  contact_name: string;
  contact_email: string;
  tax_id: string;
  payment_terms_days: string;
}

const registerSchema: ObjectSchema<RegisterValues> = object({
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(200, 'At most 200 characters'),
  contact_name: optionalText('Contact name', 200),
  contact_email: optionalText('Contact email', 320),
  tax_id: optionalText('Tax ID', 64),
  payment_terms_days: integerField('Payment terms', 0, 365),
});

/** Upgrade a walk-in to a registered customer (audited; history stays on the same customer). */
function RegisterDialog({
  customer,
  onClose,
  onSaved,
}: {
  customer: CustomerDto;
  onClose: () => void;
  onSaved: (c: CustomerDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<RegisterValues>
      open
      title={`Register ${customer.name}`}
      initialValues={{
        code: '',
        name: customer.name,
        contact_name: customer.contact_name ?? '',
        contact_email: customer.contact_email ?? '',
        tax_id: customer.tax_id ?? '',
        payment_terms_days: String(customer.payment_terms_days),
      }}
      validationSchema={registerSchema}
      submitLabel="Register customer"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          code: v.code.trim(),
          name: v.name.trim(),
          contact_name: orNull(v.contact_name),
          contact_email: orNull(v.contact_email),
          tax_id: orNull(v.tax_id),
          payment_terms_days: Number(v.payment_terms_days),
          version: customer.version,
        };
        try {
          onSaved(await hoursService.registerWalkIn(customer.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      <FormikTextField name="code" label="Customer code" required />
      <FormikTextField name="name" label="Name" required />
      <FormikTextField name="contact_name" label="Contact name" />
      <FormikTextField name="contact_email" label="Contact email" />
      <FormikTextField name="tax_id" label="Tax ID" />
      <FormikTextField name="payment_terms_days" label="Payment terms (days)" required />
    </FormDialog>
  );
}

/** Walk-in customers (WALK-… codes): search, create, register as a full customer, open. */
export function WalkInCustomersPage() {
  const notify = useNotify();
  const navigate = useNavigate();
  const hours = useHoursPolicy();
  const walkInsOn = hours.on && (hours.policy?.walkInAllowed ?? true);
  const canCreate = useCanMutate(PERMISSIONS.tenantHoursPurchase) && walkInsOn;
  const canRegister = useCanMutate(PERMISSIONS.tenantCustomerWrite);
  const [creating, setCreating] = useState(false);
  const [registering, setRegistering] = useState<CustomerDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CustomerDto>>(
    (query, signal) => customerService.list(query, signal),
    [],
  );
  const columns: DataColumn<CustomerDto>[] = [
    { id: 'code', header: 'Code', render: (c) => <strong>{c.code}</strong> },
    { id: 'name', header: 'Name', sortField: 'name', render: (c) => c.name },
    { id: 'phone', header: 'Phone', render: (c) => c.contact_phone ?? '—' },
    { id: 'state', header: 'State', render: (c) => <ActiveChip active={c.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) => (
        <RowActionsMenu
          label={`${c.code} · ${c.name}`}
          actions={[
            {
              key: 'view',
              label: 'View customer',
              onClick: () => {
                void navigate(customerDetailPath(c.id));
              },
            },
            {
              key: 'register',
              label: 'Register as customer',
              hidden: !canRegister || !c.is_active,
              onClick: () => {
                setRegistering(c);
              },
            },
          ]}
        />
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Walk-in customers"
        subtitle="Customers recorded with just a name and phone; register them when they become regulars"
        actions={
          canCreate && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New walk-in
            </Button>
          )
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          searchPlaceholder="Search code or name"
          reloadKey={reloadKey}
          filters={{ kind: 'WALK_IN' }}
          emptyTitle="No walk-in customers"
          isRowMuted={(c) => !c.is_active}
          onRowClick={(c) => {
            void navigate(customerDetailPath(c.id));
          }}
        />
      </Stack>
      {creating && (
        <WalkInDialog
          onClose={() => {
            setCreating(false);
          }}
          onSaved={() => {
            notify.success('Walk-in customer created.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {registering !== null && (
        <RegisterDialog
          customer={registering}
          onClose={() => {
            setRegistering(null);
          }}
          onSaved={(c) => {
            notify.success(`${c.name} is now a registered customer (${c.code}).`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
