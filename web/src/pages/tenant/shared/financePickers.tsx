import type {
  CustomerDto,
  ExpenseCategoryDto,
  ExpenseDto,
  JobDto,
  MachineDto,
  StaffDto,
} from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import {
  customerOptionLabel,
  expenseCategoryOptionLabel,
  expenseOptionLabel,
  jobOptionLabel,
  machineOptionLabel,
  resolveCustomer,
  resolveExpense,
  resolveExpenseCategory,
  resolveJob,
  resolveMachine,
  resolveStaff,
  searchCustomers,
  searchExpenseCategories,
  searchExpenses,
  searchJobs,
  searchMachines,
  searchStaff,
  searchSupervisors,
  staffOptionLabel,
} from './financeLookups';
import { optionId } from './lookups';

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: T | null) => void;
}

/** Customer search (code / name) bound to a Formik id field. */
export function FormikCustomerIdPicker(props: IdPickerProps<CustomerDto>) {
  return (
    <FormikAsyncIdAutocomplete<CustomerDto>
      {...props}
      fetchOptions={searchCustomers}
      resolveOption={resolveCustomer}
      getOptionId={optionId}
      getOptionLabel={customerOptionLabel}
    />
  );
}

/** Staff search bound to a Formik id field (supervisors only with `supervisorsOnly`). */
export function FormikStaffIdPicker({
  supervisorsOnly = false,
  ...props
}: IdPickerProps<StaffDto> & { supervisorsOnly?: boolean }) {
  return (
    <FormikAsyncIdAutocomplete<StaffDto>
      {...props}
      fetchOptions={supervisorsOnly ? searchSupervisors : searchStaff}
      resolveOption={resolveStaff}
      getOptionId={optionId}
      getOptionLabel={staffOptionLabel}
    />
  );
}

/** Machine search (asset code / name) bound to a Formik id field. */
export function FormikMachineIdPicker(props: IdPickerProps<MachineDto>) {
  return (
    <FormikAsyncIdAutocomplete<MachineDto>
      {...props}
      fetchOptions={searchMachines}
      resolveOption={resolveMachine}
      getOptionId={optionId}
      getOptionLabel={machineOptionLabel}
    />
  );
}

/** Job search (job number) bound to a Formik id field. */
export function FormikJobIdPicker(props: IdPickerProps<JobDto>) {
  return (
    <FormikAsyncIdAutocomplete<JobDto>
      {...props}
      fetchOptions={searchJobs}
      resolveOption={resolveJob}
      getOptionId={optionId}
      getOptionLabel={jobOptionLabel}
    />
  );
}

/** Active expense category search (code / name) bound to a Formik id field. */
export function FormikExpenseCategoryIdPicker(props: IdPickerProps<ExpenseCategoryDto>) {
  return (
    <FormikAsyncIdAutocomplete<ExpenseCategoryDto>
      {...props}
      fetchOptions={searchExpenseCategories}
      resolveOption={resolveExpenseCategory}
      getOptionId={optionId}
      getOptionLabel={expenseCategoryOptionLabel}
    />
  );
}

/** Expense search bound to a Formik id field (the expense that paid for a fuel purchase). */
export function FormikExpenseIdPicker(props: IdPickerProps<ExpenseDto>) {
  return (
    <FormikAsyncIdAutocomplete<ExpenseDto>
      {...props}
      fetchOptions={searchExpenses}
      resolveOption={resolveExpense}
      getOptionId={optionId}
      getOptionLabel={expenseOptionLabel}
    />
  );
}

interface FilterProps<T> {
  label: string;
  value: T | null;
  onChange: (value: T | null) => void;
}

const sameId = (a: { id: string }, b: { id: string }) => a.id === b.id;

/** List filter: customer (server search). */
export function CustomerFilter({ label, value, onChange }: FilterProps<CustomerDto>) {
  return (
    <AsyncAutocomplete<CustomerDto>
      label={label}
      size="small"
      placeholder="All customers"
      value={value}
      onChange={onChange}
      fetchOptions={searchCustomers}
      getOptionLabel={customerOptionLabel}
      isOptionEqualToValue={sameId}
    />
  );
}

/** List filter / selector: staff member (server search; supervisors only with `supervisorsOnly`). */
export function StaffFilter({
  label,
  value,
  onChange,
  supervisorsOnly = false,
  placeholder = 'All staff',
}: FilterProps<StaffDto> & { supervisorsOnly?: boolean; placeholder?: string }) {
  return (
    <AsyncAutocomplete<StaffDto>
      label={label}
      size="small"
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      fetchOptions={supervisorsOnly ? searchSupervisors : searchStaff}
      getOptionLabel={staffOptionLabel}
      isOptionEqualToValue={sameId}
    />
  );
}

/** List filter: machine (server search). */
export function MachineFilter({ label, value, onChange }: FilterProps<MachineDto>) {
  return (
    <AsyncAutocomplete<MachineDto>
      label={label}
      size="small"
      placeholder="All machines"
      value={value}
      onChange={onChange}
      fetchOptions={searchMachines}
      getOptionLabel={machineOptionLabel}
      isOptionEqualToValue={sameId}
    />
  );
}
