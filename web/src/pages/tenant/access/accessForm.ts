import { array, object, string, type ObjectSchema } from 'yup';
import type { InviteIn, MemberDto } from '../../../api/types';

/** "site-manager" → "Site manager". */
export function roleLabel(key: string): string {
  const words = key.replace(/-/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const name = (label: string) =>
  string().trim().required(`Enter the ${label}`).max(100, `${label} is too long`);

export interface AddUserValues {
  first_name: string;
  last_name: string;
  email: string;
  role_key: string;
}

export const PERSON_FIELDS = ['first_name', 'last_name', 'email'] as const;

export const addUserSchema: ObjectSchema<AddUserValues> = object({
  first_name: name('first name'),
  last_name: name('last name'),
  email: string().trim().required('Enter the email').email('Enter a valid email'),
  role_key: string().required('Choose a role'),
});

export function toInvite(v: AddUserValues): InviteIn {
  return {
    first_name: v.first_name.trim(),
    last_name: v.last_name.trim(),
    email: v.email.trim().toLowerCase(),
    role_key: v.role_key,
  };
}

export interface EditUserValues {
  first_name: string;
  last_name: string;
  roles: string[];
}

export const editUserSchema: ObjectSchema<EditUserValues> = object({
  first_name: name('first name'),
  last_name: name('last name'),
  roles: array(string().required())
    .min(1, 'Keep at least one role, or deactivate this person')
    .required(),
});

/** "Daudi Mollel" → first "Daudi", last "Mollel"; everything before the last word is the first name. */
export function splitName(displayName: string): { first_name: string; last_name: string } {
  const parts = displayName.trim().split(/\s+/);
  if (parts.length < 2) return { first_name: parts[0] ?? '', last_name: '' };
  return { first_name: parts.slice(0, -1).join(' '), last_name: parts[parts.length - 1] ?? '' };
}

export function editValuesOf(m: MemberDto): EditUserValues {
  return { ...splitName(m.display_name), roles: m.roles.map((r) => r.role_key) };
}

/** Roles to give and to take away to go from the member's roles to `wanted`. */
export function roleChanges(
  m: MemberDto,
  wanted: readonly string[],
): { grant: string[]; revoke: string[] } {
  const now = new Set(m.roles.map((r) => r.role_key));
  const next = new Set(wanted);
  return {
    grant: [...next].filter((k) => !now.has(k)).sort(),
    revoke: [...now].filter((k) => !next.has(k)).sort(),
  };
}
