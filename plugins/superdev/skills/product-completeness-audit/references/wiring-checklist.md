# Wiring checklist — what counts as "wired"

The `wiring-auditor` uses this to grade each interactive element.

## WIRED ✓ (production-ready)

A handler is WIRED if ALL of the following hold:
- ✅ It calls a function from `api.ts` (which uses `apiRequest` / fetch) OR a TanStack `useMutation.mutate()`
- ✅ It awaits the response (or uses the mutation's `onSuccess` callback)
- ✅ Successful mutations trigger UI feedback (toast / inline confirmation / navigation)
- ✅ Errors are caught and surfaced to the user (toast / inline error / error boundary)
- ✅ The destination of any persistence is verifiable in the DB

## STUB ✗ (block ship)

A handler is a STUB if any of:
- ❌ Calls only `console.log`, `console.error`, `alert`, or `window.confirm` with no follow-up
- ❌ Has a `// TODO` / `// FIXME` comment in the body
- ❌ Calls a placeholder function whose body is `throw new Error('not implemented')`
- ❌ Updates only local state for an operation that should persist to the backend (e.g. "delete" that just filters from `useState` and doesn't call the API)

## NO-OP ✗ (block ship)

- ❌ Form `onSubmit` that calls only `e.preventDefault()`
- ❌ Button `onClick={() => {}}`
- ❌ Handler that's bound but missing from props (silent JS error in dev tools)

## NAVIGATION-ONLY ✓

- ✓ `onClick` that calls `router.push('/some-route')` is OK — navigation IS the work
- But: verify the destination route exists and renders (cross-check with `route-completeness-checker`)

## OPEN-IN-MODAL ✓ (conditional)

- ✓ `onClick` that opens a dialog/sheet is OK IF the dialog itself has wired actions
- ✗ NOT OK if the dialog is also a stub ("Coming soon" content)

## DOWNLOAD / EXPORT ✓ (conditional)

- ✓ Generates and downloads a file with real data → WIRED
- ✗ Triggers a "download started" toast but no file appears → STUB
