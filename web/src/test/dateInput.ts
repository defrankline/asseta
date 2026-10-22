import { screen, within } from '@testing-library/react';
import type { UserEvent } from '@testing-library/user-event';

/** Types an ISO date (YYYY-MM-DD) into a MUI X date field (sectioned `YYYY-MM-DD` format). */
export async function typeIsoDate(
  user: UserEvent,
  label: string | RegExp,
  iso: string,
  container: HTMLElement = document.body,
): Promise<void> {
  const group = within(container).getByRole('group', { name: label });
  const [year] = within(group).getAllByRole('spinbutton');
  if (year === undefined) throw new Error('date field has no sections');
  await user.click(year);
  await user.keyboard(iso.replace(/-/g, ''));
}

export const dateGroup = (label: string | RegExp) => screen.getByRole('group', { name: label });
