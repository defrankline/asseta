import { object, string, type ObjectSchema } from 'yup';

export interface CategoryValues {
  name: string;
  description: string;
}
export const categorySchema: ObjectSchema<CategoryValues> = object({
  name: string().trim().required('Name is required').max(100, 'At most 100 characters'),
  description: string().trim().max(300, 'At most 300 characters').ensure(),
});

export interface AreaValues {
  code: string;
  name: string;
}
export const areaSchema: ObjectSchema<AreaValues> = object({
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
});

/** Stable error codes for categories and operating areas. */
export const LOOKUP_ERROR_HINTS: Readonly<Record<string, string>> = {
  CATEGORY_INACTIVE: 'This category is inactive; reactivate it or pick another one.',
  AREA_INACTIVE: 'This operating area is inactive; reactivate it or pick another one.',
};
