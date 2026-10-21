/**
 * Platform rule: backend-sourced options must never be rendered as a TextField select + MenuItem
 * list. Static option lists are module-level ALL_CAPS constants (e.g. `STATUS_OPTIONS`, or a lookup
 * such as `TARGETS[state]`); anything else is treated as data and must use the debounced,
 * server-searched AsyncAutocomplete / FormikAsyncIdAutocomplete / FormikAsyncAutocomplete.
 */
const ALL_CAPS = '/^[A-Z][A-Z0-9_]*$/';
const STATIC_RECEIVER = `:matches(Identifier[name=${ALL_CAPS}], MemberExpression[object.type='Identifier'][object.name=${ALL_CAPS}])`;
const ASYNC_HINT =
  'Backend data must use the debounced, server-searched AsyncAutocomplete (src/components/data/AsyncAutocomplete.tsx) or FormikAsyncIdAutocomplete; static enums must be an ALL_CAPS module constant. See web/README.md "Dropdowns".';
/** `no-restricted-syntax` entries; imported by eslint.config.js and its guard test. */
export const DROPDOWN_RULES = [
  {
    selector: `CallExpression[callee.type='MemberExpression'][callee.property.name='map']:not([callee.object.type='Identifier'][callee.object.name=${ALL_CAPS}]):not([callee.object.type='MemberExpression'][callee.object.object.type='Identifier'][callee.object.object.name=${ALL_CAPS}]) JSXOpeningElement[name.name='MenuItem']`,
    message: `<MenuItem> rendered from a non-constant list. ${ASYNC_HINT}`,
  },
  {
    selector: `JSXOpeningElement[name.name=/^(FormikSelectField|StaticSelectFilter)$/] > JSXAttribute[name.name='options'] > JSXExpressionContainer > :not(${STATIC_RECEIVER})`,
    message: `Select options must be an ALL_CAPS static constant. ${ASYNC_HINT}`,
  },
];
