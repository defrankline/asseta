import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { object, string } from 'yup';
import { FormikTextField } from './FormikTextField';
import { StepperFormDialog } from './StepperFormDialog';

interface Values {
  name: string;
}

function renderDialog(onSubmit: () => Promise<void>) {
  render(
    <StepperFormDialog<Values>
      open
      title="Guarded"
      initialValues={{ name: 'Kilimanjaro' }}
      validationSchema={object({ name: string().required() })}
      steps={[
        {
          label: 'Only step',
          fields: ['name'],
          render: () => <FormikTextField name="name" label="Name" />,
        },
      ]}
      renderReview={(v) => <p>Reviewing {v.name}</p>}
      onSubmit={onSubmit}
      onClose={() => undefined}
      submitLabel="Create"
    />,
  );
}

describe('StepperFormDialog review guard', () => {
  it('the click that reaches Review never submits; only the explicit submit does', async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    renderDialog(onSubmit);
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Reviewing Kilimanjaro')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('pressing Enter in a field before Review advances instead of submitting', async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    renderDialog(onSubmit);
    await userEvent.type(screen.getByLabelText(/Name/), '{Enter}');
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
