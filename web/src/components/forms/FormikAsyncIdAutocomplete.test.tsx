import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form, Formik } from 'formik';
import { describe, expect, it, vi } from 'vitest';
import { FormikAsyncIdAutocomplete } from './FormikAsyncIdAutocomplete';

interface Site {
  id: string;
  name: string;
}
const SITES: Site[] = [
  { id: 's1', name: 'North quarry' },
  { id: 's2', name: 'South yard' },
];

function renderField(
  initial: string,
  fetchOptions: (q: string, signal: AbortSignal) => Promise<Site[]>,
  resolveOption?: (id: string, signal: AbortSignal) => Promise<Site | null>,
) {
  const onSubmit = vi.fn();
  const onOptionChange = vi.fn();
  render(
    <Formik initialValues={{ site_id: initial }} onSubmit={onSubmit}>
      <Form>
        <FormikAsyncIdAutocomplete<Site>
          name="site_id"
          label="Site"
          fetchOptions={fetchOptions}
          getOptionId={(s) => s.id}
          getOptionLabel={(s) => s.name}
          onOptionChange={onOptionChange}
          {...(resolveOption !== undefined ? { resolveOption } : {})}
        />
        <button type="submit">Save</button>
      </Form>
    </Formik>,
  );
  return { onSubmit, onOptionChange };
}

describe('FormikAsyncIdAutocomplete', () => {
  it('sends one debounced server query with the typed text and submits the picked id', async () => {
    const user = userEvent.setup();
    const fetchOptions = vi.fn((q: string) =>
      Promise.resolve(SITES.filter((s) => s.name.toLowerCase().includes(q.toLowerCase()))),
    );
    const { onSubmit, onOptionChange } = renderField('', fetchOptions);

    await user.type(screen.getByRole('combobox', { name: 'Site' }), 'south');
    await waitFor(() => {
      expect(fetchOptions).toHaveBeenLastCalledWith('south', expect.any(AbortSignal));
    });
    // Intermediate keystrokes are debounced away (only the open query '' may precede it).
    expect(fetchOptions.mock.calls.map(([q]) => q).filter((q) => q !== '')).toEqual(['south']);
    await user.click(await screen.findByRole('option', { name: 'South yard' }));
    expect(screen.getByRole('combobox', { name: 'Site' })).toHaveValue('South yard');
    expect(onOptionChange).toHaveBeenLastCalledWith(SITES[1]);

    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0]?.[0]).toEqual({ site_id: 's2' });
  });

  it('shows the label of an id already in the form (edit) without searching', async () => {
    const fetchOptions = vi.fn(() => Promise.resolve(SITES));
    const resolve = vi.fn((id: string) => Promise.resolve(SITES.find((s) => s.id === id) ?? null));
    const { onOptionChange } = renderField('s1', fetchOptions, resolve);
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Site' })).toHaveValue('North quarry');
    });
    expect(resolve).toHaveBeenCalledWith('s1', expect.any(AbortSignal));
    expect(onOptionChange).toHaveBeenCalledWith(SITES[0]);
    expect(fetchOptions).not.toHaveBeenCalled();
  });

  it('clears the id when the selection is cleared', async () => {
    const user = userEvent.setup();
    const resolve = (id: string) => Promise.resolve(SITES.find((s) => s.id === id) ?? null);
    const { onSubmit } = renderField('s1', () => Promise.resolve(SITES), resolve);
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Site' })).toHaveValue('North quarry');
    });
    await user.click(screen.getByRole('combobox', { name: 'Site' }));
    await user.click(await screen.findByRole('button', { name: 'Clear', hidden: true }));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(onSubmit.mock.calls[0]?.[0]).toEqual({ site_id: '' });
    });
  });

  it('shows "No matches" and server errors in the field', async () => {
    const user = userEvent.setup();
    const fetchOptions = vi
      .fn<(q: string, signal: AbortSignal) => Promise<Site[]>>()
      .mockResolvedValueOnce([])
      .mockRejectedValue(new Error('Service unavailable'));
    renderField('', fetchOptions);
    await user.click(screen.getByRole('combobox', { name: 'Site' }));
    expect(await screen.findByText('No matches')).toBeInTheDocument();
    await user.type(screen.getByRole('combobox', { name: 'Site' }), 'x');
    expect(await screen.findByText('Service unavailable')).toBeInTheDocument();
  });
});
