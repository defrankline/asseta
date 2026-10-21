import type { AreaDto, CategoryDto, JobSiteDto, TrackerModelDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import {
  areaLabel,
  categoryLabel,
  jobSiteLabel,
  optionId,
  resolveArea,
  resolveCategory,
  resolveJobSite,
  searchAreas,
  searchCategories,
  searchJobSites,
  searchTrackerModels,
  trackerModelLabel,
} from './lookups';

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  helperText?: string;
  /** The option behind the field (picked, cleared or resolved for an edit form). */
  onOptionChange?: (option: T | null) => void;
  /** Overrides the default id → option lookup (e.g. from a list the page already holds). */
  resolveOption?: (id: string, signal: AbortSignal) => Promise<T | null>;
}

/** Machine category search bound to a Formik id field. */
export function FormikCategoryPicker(props: IdPickerProps<CategoryDto>) {
  return (
    <FormikAsyncIdAutocomplete<CategoryDto>
      resolveOption={resolveCategory}
      {...props}
      fetchOptions={searchCategories}
      getOptionId={optionId}
      getOptionLabel={categoryLabel}
    />
  );
}

/** Operating area search (code / name) bound to a Formik id field. */
export function FormikAreaPicker(props: IdPickerProps<AreaDto>) {
  return (
    <FormikAsyncIdAutocomplete<AreaDto>
      resolveOption={resolveArea}
      {...props}
      fetchOptions={searchAreas}
      getOptionId={optionId}
      getOptionLabel={areaLabel}
    />
  );
}

/** Job site search (code / name) bound to a Formik id field. */
export function FormikJobSitePicker(props: IdPickerProps<JobSiteDto>) {
  return (
    <FormikAsyncIdAutocomplete<JobSiteDto>
      resolveOption={resolveJobSite}
      {...props}
      fetchOptions={searchJobSites}
      getOptionId={optionId}
      getOptionLabel={jobSiteLabel}
    />
  );
}

/** Approved tracker model search (manufacturer / model) bound to a Formik id field. */
export function FormikTrackerModelPicker(props: IdPickerProps<TrackerModelDto>) {
  return (
    <FormikAsyncIdAutocomplete<TrackerModelDto>
      {...props}
      fetchOptions={searchTrackerModels}
      getOptionId={optionId}
      getOptionLabel={trackerModelLabel}
      noOptionsText="No approved tracker model matches"
    />
  );
}

interface FilterProps<T> {
  label: string;
  value: T | null;
  onChange: (value: T | null) => void;
}

/** List-page filter: machine category (server search). */
export function CategoryFilter({ label, value, onChange }: FilterProps<CategoryDto>) {
  return (
    <AsyncAutocomplete<CategoryDto>
      label={label}
      size="small"
      placeholder="All categories"
      value={value}
      onChange={onChange}
      fetchOptions={searchCategories}
      getOptionLabel={categoryLabel}
      isOptionEqualToValue={(a, b) => a.id === b.id}
    />
  );
}

/** List-page filter: job site (server search). */
export function JobSiteFilter({ label, value, onChange }: FilterProps<JobSiteDto>) {
  return (
    <AsyncAutocomplete<JobSiteDto>
      label={label}
      size="small"
      value={value}
      onChange={onChange}
      fetchOptions={searchJobSites}
      getOptionLabel={jobSiteLabel}
      isOptionEqualToValue={(a, b) => a.id === b.id}
    />
  );
}
