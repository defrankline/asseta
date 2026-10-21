import { object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import type { ExpenseCategoryDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { EXPENSE_CATEGORY_HINTS } from './expenseCategoryHints';

interface CategoryValues {
  code: string;
  name: string;
}

const schema: ObjectSchema<CategoryValues> = object({
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
});

interface ExpenseCategoryDialogProps {
  /** Category to edit; omit to create. */
  category?: ExpenseCategoryDto;
  onClose: () => void;
  onSaved: (category: ExpenseCategoryDto) => void;
  onReload: () => void;
}

/** Create or edit an expense category (edit sends the `version` read). Mount only while open. */
export function ExpenseCategoryDialog({
  category,
  onClose,
  onSaved,
  onReload,
}: ExpenseCategoryDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<CategoryValues>
      open
      title={category === undefined ? 'New expense category' : `Edit ${category.name}`}
      initialValues={{ code: category?.code ?? '', name: category?.name ?? '' }}
      validationSchema={schema}
      submitLabel={category === undefined ? 'Create category' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const fields = { code: v.code.trim(), name: v.name.trim() };
        try {
          if (category === undefined) {
            onSaved(await expenseCategoryService.create(fields, keyFor(fields)));
          } else {
            const body = { ...fields, version: category.version };
            onSaved(
              await guard(() => expenseCategoryService.update(category.id, body, keyFor(body))),
            );
          }
        } catch (err) {
          throw withErrorCode(err, EXPENSE_CATEGORY_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <FormikTextField name="code" label="Code" required />
      <FormikTextField name="name" label="Name" required />
    </FormDialog>
  );
}
