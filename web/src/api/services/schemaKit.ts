/**
 * Small Yup building blocks for runtime response validation. Schemas built from these are annotated
 * with generated contract types, so contract drift fails `npm run typecheck`.
 */
import { array, boolean, mixed, number, string } from 'yup';

export const text = () => string().defined();
export const nullableText = () => string().nullable().defined();
export const id = () => string().required();
export const nullableId = () => string().nullable().defined();
export const int = () => number().integer().required();
export const nullableInt = () => number().integer().nullable().defined();
export const num = () => number().required();
export const nullableNum = () => number().nullable().defined();
export const bool = () => boolean().required();
export const nullableBool = () => boolean().nullable().defined();
export const oneOf = <T extends string>(values: readonly T[]) =>
  mixed<T>().oneOf(values).required();
export const nullableOneOf = <T extends string>(values: readonly T[]) =>
  mixed<T>()
    .nullable()
    .defined()
    .oneOf([...values, null]);
export const idList = () => array(string().required()).required();

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Free-form JSON object (evidence, policy values, GeoJSON). */
export const record = () => mixed<Record<string, unknown>>(isPlainRecord).required();

function isLngLat(value: unknown): value is [number, number] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    typeof value[0] === 'number' &&
    typeof value[1] === 'number'
  );
}

/** GeoJSON position `[lon, lat]`. */
export const lngLat = () => mixed<[number, number]>(isLngLat).required();

/** Free-form JSON object or null (e.g. a tracker comparison that may be absent). */
export const nullableRecord = () =>
  mixed<Record<string, unknown>>(isPlainRecord).nullable().defined();
