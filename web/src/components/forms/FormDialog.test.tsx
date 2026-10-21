import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { object, string } from 'yup';
import { ApiError } from '../../api/ApiError';
import { FormDialog } from './FormDialog';
import { FormikTextField } from './FormikTextField';

const schema = object({
  name: string().trim().required('Name is required'),
  email: string().email('Enter a valid email').required('Email is required'),
});

function setup(
  onSubmit = vi.fn<(values: { name: string; email: string }) => Promise<void>>(() =>
    Promise.resolve(),
  ),
) {
  const onClose = vi.fn();
  render(
    <FormDialog
      open
      title="Invite user"
      initialValues={{ name: '', email: '' }}
      validationSchema={schema}
      onSubmit={onSubmit}
      onClose={onClose}
    >
      <FormikTextField name="name" label="Name" />
      <FormikTextField name="email" label="Email" />
    </FormDialog>,
  );
  return { onSubmit, onClose, user: userEvent.setup() };
}

describe('FormDialog', () => {
  it('blocks submit and shows Yup errors for invalid input', async () => {
    const { onSubmit, user } = setup();
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    expect(screen.getByText('Email is required')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Email'), 'not-an-email');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Enter a valid email')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits valid values and closes', async () => {
    const { onSubmit, onClose, user } = setup();
    await user.type(screen.getByLabelText('Name'), 'Ada');
    await user.type(screen.getByLabelText('Email'), 'ada@example.test');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0]?.[0]).toEqual({ name: 'Ada', email: 'ada@example.test' });
    expect(onClose).toHaveBeenCalled();
  });

  it('maps server field errors and keeps the dialog open', async () => {
    const failing = vi.fn(() =>
      Promise.reject(
        new ApiError({
          status: 409,
          code: 'conflict',
          message: 'User already exists',
          correlationId: 'corr-9',
          details: [{ field: 'email', issue: 'Email already invited' }],
        }),
      ),
    );
    const { onClose, user } = setup(failing);
    await user.type(screen.getByLabelText('Name'), 'Ada');
    await user.type(screen.getByLabelText('Email'), 'ada@example.test');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Email already invited')).toBeInTheDocument();
    expect(screen.getByText('User already exists (ref corr-9)')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
