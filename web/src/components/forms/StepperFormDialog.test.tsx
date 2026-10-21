import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { object, string } from 'yup';
import { FormikTextField } from './FormikTextField';
import { StepperFormDialog } from './StepperFormDialog';

const schema = object({
  name: string().required('Name is required'),
  serial: string().required('Serial is required'),
});

describe('StepperFormDialog', () => {
  it('validates per step and submits from the Review step', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn(() => Promise.resolve());
    render(
      <StepperFormDialog
        open
        title="Register"
        initialValues={{ name: '', serial: '' }}
        validationSchema={schema}
        onSubmit={onSubmit}
        onClose={vi.fn()}
        steps={[
          {
            label: 'Identity',
            fields: ['name'],
            render: () => <FormikTextField name="name" label="Name" />,
          },
          {
            label: 'Device',
            fields: ['serial'],
            render: () => <FormikTextField name="serial" label="Serial" />,
          },
        ]}
        renderReview={(v) => (
          <p>
            Review {v.name} / {v.serial}
          </p>
        )}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Name'), 'Dozer 1');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.type(await screen.findByLabelText('Serial'), 'SN-9');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Review Dozer 1 / SN-9')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
  });
});
