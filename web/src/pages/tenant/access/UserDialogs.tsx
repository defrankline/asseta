import {
  Checkbox,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  FormLabel,
  Stack,
  Typography,
} from '@mui/material';
import { useField } from 'formik';
import { useState } from 'react';
import { tenantAccessService } from '../../../api/services/tenantAccessService';
import type { InviteResultDto, MemberDto, TenantRoleDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  PERSON_FIELDS,
  addUserSchema,
  editUserSchema,
  editValuesOf,
  roleChanges,
  roleLabel,
  toInvite,
  type AddUserValues,
  type EditUserValues,
} from './accessForm';

/** Roles this user may give or take away: approval roles only with the approver-assignment right. */
function assignable(roles: readonly TenantRoleDto[], canAssignApprovers: boolean) {
  return roles.filter((r) => !r.carries_approvals || canAssignApprovers);
}

function NameFields() {
  return (
    <>
      <FormikTextField name="first_name" label="First name" required autoFocus />
      <FormikTextField name="last_name" label="Last name" required />
    </>
  );
}

interface AddUserDialogProps {
  roles: readonly TenantRoleDto[];
  canAssignApprovers: boolean;
  onClose: () => void;
  onAdded: (result: InviteResultDto, values: AddUserValues) => void;
}

/** Person → Role → Review. A new account gets a one-time password, shown after saving. */
export function AddUserDialog({ roles, canAssignApprovers, onClose, onAdded }: AddUserDialogProps) {
  const keyFor = useIdempotencyKey();
  const options = assignable(roles, canAssignApprovers);
  const searchRoles = (query: string) =>
    Promise.resolve(
      options.filter((r) =>
        roleLabel(r.role_key).toLowerCase().includes(query.trim().toLowerCase()),
      ),
    );
  const resolveRole = (key: string) =>
    Promise.resolve(options.find((r) => r.role_key === key) ?? null);
  const [initialValues] = useState<AddUserValues>({
    first_name: '',
    last_name: '',
    email: '',
    role_key: '',
  });
  const steps: FormStep<AddUserValues>[] = [
    {
      label: 'Person',
      fields: PERSON_FIELDS,
      render: () => (
        <>
          <NameFields />
          <FormikTextField
            name="email"
            label="Email"
            required
            type="email"
            helperText="They sign in with this email."
          />
        </>
      ),
    },
    {
      label: 'Role',
      fields: ['role_key'],
      render: () => (
        <FormikAsyncIdAutocomplete<TenantRoleDto>
          name="role_key"
          label="Role"
          required
          fetchOptions={searchRoles}
          resolveOption={resolveRole}
          getOptionId={(r) => r.role_key}
          getOptionLabel={(r) => roleLabel(r.role_key)}
          noOptionsText="No role matches"
        />
      ),
    },
  ];
  return (
    <StepperFormDialog<AddUserValues>
      open
      title="Add user"
      steps={steps}
      initialValues={initialValues}
      validationSchema={addUserSchema}
      submitLabel="Add user"
      renderReview={(v) => (
        <Stack spacing={0.5}>
          <Typography>
            <strong>
              {v.first_name} {v.last_name}
            </strong>
          </Typography>
          <Typography>{v.email}</Typography>
          <Typography>Role: {roleLabel(v.role_key)}</Typography>
        </Stack>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const body = toInvite(values);
        onAdded(await tenantAccessService.invite(body, keyFor(body)), values);
      }}
    />
  );
}

function RoleChecklist({
  roles,
  canAssignApprovers,
  locked,
}: {
  roles: readonly TenantRoleDto[];
  canAssignApprovers: boolean;
  /** Roles held under a managed-service mandate: they end with the mandate. */
  locked: ReadonlySet<string>;
}) {
  const [field, meta, helpers] = useField<string[]>('roles');
  const error = meta.touched && typeof meta.error === 'string' ? meta.error : null;
  const toggle = (key: string, on: boolean) => {
    void helpers.setTouched(true, false);
    void helpers.setValue(on ? [...field.value, key] : field.value.filter((k) => k !== key));
  };
  return (
    <FormControl error={error !== null} component="fieldset" variant="standard">
      <FormLabel component="legend">Roles</FormLabel>
      <FormGroup>
        {roles.map((r) => {
          const blocked = locked.has(r.role_key) || (r.carries_approvals && !canAssignApprovers);
          return (
            <FormControlLabel
              key={r.role_key}
              label={roleLabel(r.role_key)}
              control={
                <Checkbox
                  checked={field.value.includes(r.role_key)}
                  disabled={blocked}
                  onChange={(e) => {
                    toggle(r.role_key, e.target.checked);
                  }}
                />
              }
            />
          );
        })}
      </FormGroup>
      {error !== null && <FormHelperText>{error}</FormHelperText>}
    </FormControl>
  );
}

interface EditUserDialogProps {
  member: MemberDto;
  roles: readonly TenantRoleDto[];
  canAssignApprovers: boolean;
  onClose: () => void;
  onSaved: (members: MemberDto[] | null) => void;
}

/** Name and roles. Saves only what changed: the name, then roles given, then roles taken away. */
export function EditUserDialog({
  member,
  roles,
  canAssignApprovers,
  onClose,
  onSaved,
}: EditUserDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(() => editValuesOf(member));
  const locked = new Set(
    member.roles.filter((r) => (r.mandate_reference ?? null) !== null).map((r) => r.role_key),
  );
  return (
    <FormDialog<EditUserValues>
      open
      title={`Edit ${member.display_name}`}
      initialValues={initialValues}
      validationSchema={editUserSchema}
      submitLabel="Save changes"
      onClose={onClose}
      onSubmit={async (values) => {
        let latest: MemberDto[] | null = null;
        const first = values.first_name.trim();
        const last = values.last_name.trim();
        if (first !== initialValues.first_name || last !== initialValues.last_name) {
          const body = { first_name: first, last_name: last };
          latest = await tenantAccessService.rename(
            member.user_id,
            body,
            keyFor({ user: member.user_id, ...body }),
          );
        }
        const { grant, revoke } = roleChanges(member, values.roles);
        for (const role of grant) {
          latest = await tenantAccessService.grantRole(
            member.user_id,
            role,
            keyFor({ user: member.user_id, grant: role }),
          );
        }
        for (const role of revoke) {
          latest = await tenantAccessService.revokeRole(
            member.user_id,
            role,
            keyFor({ user: member.user_id, revoke: role }),
          );
        }
        onSaved(latest);
      }}
    >
      <Stack spacing={2}>
        <NameFields />
        <Typography variant="body2" color="text.secondary">
          {member.email} · the email is how they sign in, so it can&apos;t be changed.
        </Typography>
        <RoleChecklist roles={roles} canAssignApprovers={canAssignApprovers} locked={locked} />
      </Stack>
    </FormDialog>
  );
}
