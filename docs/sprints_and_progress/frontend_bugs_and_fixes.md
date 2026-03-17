# Frontend Code Review — Integronix
**Reviewer:** Senior Developer (AI Code Review)  
**Scope:** All frontend source files  
**Date:** 2026-03-10  
**Files Reviewed:** 18 files across `src/app`, `src/components`, `src/lib`, `src/types`, `src/middleware.ts`  
**Total Issues Found:** 9 (2 High · 5 Medium · 2 Minor) + 1 Optimization

---

## Table of Contents

1. [FE-BUG-001 — `AuditCard` Missing `CODE_DIVERGENCE` Display Config (HIGH)](#fe-bug-001)
2. [FE-BUG-002 — `RESOLUTION_LABELS` Incomplete — 3 of 6 `MappingPath` Values Missing (HIGH)](#fe-bug-002)
3. [FE-BUG-003 — `AuthProvider.loadProfile` Fires Unguarded Async — Infinite Loading on DB Fail (MEDIUM)](#fe-bug-003)
4. [FE-BUG-004 — Hardcoded Demo Credentials in Source Code (MEDIUM)](#fe-bug-004)
5. [FE-BUG-005 — `FhirPanel.copyJson` No Error Handling (MEDIUM)](#fe-bug-005)
6. [FE-BUG-006 — `analyze/page.tsx` Interval Leaks on Component Unmount (MEDIUM)](#fe-bug-006)
7. [FE-BUG-007 — `login/page.tsx` Loading State Never Resets on Successful Redirect (MEDIUM)](#fe-bug-007)
8. [FE-BUG-008 — `CandidateChart` Unused `maxScore` Variable (Dead Code) (MINOR)](#fe-bug-008)
9. [FE-BUG-009 — `MultiCodeList` Combined Reimbursement Sums Duplicate Codes Across All Roles (MINOR)](#fe-bug-009)
10. [FE-OPT-001 — `AuthProvider` Supabase Client Not Memoized Between Re-renders (OPTIMIZATION)](#fe-opt-001)

---

## FE-BUG-001 — `AuditCard` Missing `CODE_DIVERGENCE` Display Config {#fe-bug-001}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `src/components/AuditCard.tsx` |
| **Line** | 14–19 |

### Description

The backend backend fix BUG-005 introduced a new discrepancy type: `CODE_DIVERGENCE` (two valid codes from different ICD-10 categories). The `AuditCard` component has a `DISCREPANCY_CFG` lookup map for rendering the correct badge/icon/color per discrepancy type — but `CODE_DIVERGENCE` is not in this map.

When the backend returns `type: "CODE_DIVERGENCE"`, the component falls to:
```typescript
const cfg = DISCREPANCY_CFG[d.type] ?? DISCREPANCY_CFG['UNSUPPORTED_CODE'];
```
— which renders the orange **"Invalid Code Detected"** badge and `AlertOctagon` icon. This is factually wrong — neither code is invalid. A `CODE_DIVERGENCE` means both codes exist, they just represent different clinical categories.

**Visual Impact:** Every code divergence case in the UI will show as "Invalid Code" — a misleading and alarming label for clinicians.

### Before (Broken)

```tsx
const DISCREPANCY_CFG: Record<string, ...> = {
    EXACT_MATCH:             { label: 'Codes Match', ... icon: CheckCircle2 },
    SPECIFICITY_IMPROVEMENT: { label: 'Higher Specificity Available', ... icon: TrendingUp },
    OVERCODING:              { label: 'Overcoding Risk', ... icon: AlertOctagon },
    UNSUPPORTED_CODE:        { label: 'Invalid Code Detected', ... icon: AlertOctagon },
    // CODE_DIVERGENCE missing ← falls to UNSUPPORTED_CODE default
};
```

### After (Fixed)

```tsx
const DISCREPANCY_CFG: Record<string, ...> = {
    EXACT_MATCH:             { label: 'Codes Match', color: 'text-success', bg: 'bg-success/10', border: 'border-success/25', icon: CheckCircle2 },
    SPECIFICITY_IMPROVEMENT: { label: 'Higher Specificity Available', color: 'text-accent-light', bg: 'bg-accent/10', border: 'border-accent/25', icon: TrendingUp },
    OVERCODING:              { label: 'Overcoding Risk', color: 'text-danger', bg: 'bg-danger/10', border: 'border-danger/25', icon: AlertOctagon },
    UNSUPPORTED_CODE:        { label: 'Invalid Code Detected', color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/25', icon: AlertOctagon },
    CODE_DIVERGENCE:         { label: 'Category Mismatch — Review Required', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/25', icon: ArrowLeftRight },
};
```

---

## FE-BUG-002 — `RESOLUTION_LABELS` Incomplete — 3 of 6 `MappingPath` Values Missing {#fe-bug-002}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **Files** | `src/components/ResultsPanel.tsx` (line 18–22) · `src/components/IcdCodeCard.tsx` (lines 9–19) |

### Description

`MappingPath` is a TypeScript union type defined in `types/coding.ts`:
```typescript
export type MappingPath = 'direct' | 'embedding' | 'no_mapping' | 'embedding_failed' | 'no_snomed' | 'unknown';
```
Six possible values. Both `ResultsPanel` and `IcdCodeCard` have lookup dictionaries for these values — but both only map 3 of the 6. The other 3 (`embedding_failed`, `no_snomed`, `unknown`) fall through to `?? RESOLUTION_LABELS['no_mapping']` — showing "Low Confidence" and a misleading badge.

`no_snomed` means SNOMED resolution completely failed — it should be shown differently than `no_mapping` (which means there was a SNOMED match but no ICD crosswalk found). `embedding_failed` means the vector fallback itself crashed — the highest-severity failure state, it should be flagged as an error, not just "Low Confidence."

### Before (Broken)

```tsx
// ResultsPanel.tsx — only 3 of 6 paths covered
const RESOLUTION_LABELS = {
    direct:     { label: 'High Confidence', color: 'text-success' },
    embedding:  { label: 'Semantic Match',  color: 'text-warning' },
    no_mapping: { label: 'Low Confidence',  color: 'text-slate-400' },
    // embedding_failed, no_snomed, unknown → ?? no_mapping (WRONG fallback)
};
```

### After (Fixed)

```tsx
// ResultsPanel.tsx — all 6 paths covered
const RESOLUTION_LABELS: Record<MappingPath, { label: string; color: string }> = {
    direct:           { label: 'High Confidence',   color: 'text-success' },
    embedding:        { label: 'Semantic Match',     color: 'text-warning' },
    no_mapping:       { label: 'Low Confidence',     color: 'text-slate-400' },
    no_snomed:        { label: 'Ontology Gap',       color: 'text-orange-400' },
    embedding_failed: { label: 'Pipeline Error',     color: 'text-danger' },
    unknown:          { label: 'Unresolved',         color: 'text-slate-500' },
};
```

> **Note:** Using `Record<MappingPath, ...>` instead of `Record<string, ...>` also gives TypeScript exhaustiveness checking — the compiler will error if a new mapping path is ever added to the type without being added here.

---

## FE-BUG-003 — `AuthProvider.loadProfile` Fires Unguarded Async — Infinite Loading on DB Fail {#fe-bug-003}

| Field | Detail |
|---|---|
| **Severity** | 🟠 MEDIUM |
| **File** | `src/components/AuthProvider.tsx` |
| **Lines** | 47–63 |

### Description

Two problems in the `useEffect`:

**Problem 1** — In the `onAuthStateChange` handler (line 58):
```typescript
if (user) { loadProfile(user); }   // ← no await, no catch
```
`loadProfile` is async. Calling it without `await` means errors are silently swallowed — the profile state might stay as `null` even after a successful login, leaving components that depend on `orgUser` in a permanently empty state.

**Problem 2** — If `loadProfile` throws (Supabase DB call fails), the initial session loading path (line 51):
```typescript
if (user) loadProfile(user).finally(() => setLoading(false));
```
— the `.finally` does set `loading = false`, so the initial load resolves. But in `onAuthStateChange` (line 58), there is **no `.finally`** — so if `loadProfile` throws during a re-auth event, `loading` never returns to `false`, leaving the UI in a permanent loading state.

**Problem 3** — `loadProfile` has no `try/catch` inside it. A Supabase error on the `users` table query will propagate to the promise without any user-facing error state being set.

### Before (Broken)

```typescript
// No catch, no loading reset in onAuthStateChange handler
const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
    const user = session?.user ?? null;
    setAuthUser(user);
    if (user) { loadProfile(user); }   // ← fire and forget, no error handling
    else { setOrgUser(null); setOrg(null); }
});
```

### After (Fixed)

```typescript
// loadProfile — add try/catch
async function loadProfile(user: User) {
    try {
        const { data: userRow, error } = await supabase
            .from('users').select('*').eq('auth_id', user.id).single();
        if (error) throw error;
        if (userRow) {
            setOrgUser(userRow as OrgUser);
            const { data: orgRow } = await supabase
                .from('organizations').select('*').eq('id', userRow.organization_id).single();
            if (orgRow) setOrg(orgRow as Organization);
        }
    } catch (err) {
        console.error('[AuthProvider] Failed to load user profile:', err);
        // Don't leave UI in broken state — sign out or show error
    }
}

// onAuthStateChange — await with finally
if (user) {
    loadProfile(user).finally(() => setLoading(false));
}
```

---

## FE-BUG-004 — Hardcoded Demo Credentials in Source Code {#fe-bug-004}

| Field | Detail |
|---|---|
| **Severity** | 🟠 MEDIUM |
| **File** | `src/app/auth/login/page.tsx` |
| **Lines** | 28–31 |

### Description

Demo email and password are hardcoded directly in the source file:
```typescript
const { error: err } = await supabase.auth.signInWithPassword({
    email: 'demo@integronix.ai',
    password: 'IntegronixDemo2025!',   // ← hardcoded in plaintext
});
```

This is a security issue regardless of whether it's a demo account:
- Credentials are exposed to anyone who can view the source (build output, browser devtools, GitHub)
- A team member could accidentally commit a production override with real credentials
- When the demo password is rotated, the code must be redeployed

### Fix

Move to environment variables:

```typescript
// .env.local
NEXT_PUBLIC_DEMO_EMAIL=demo@integronix.ai
NEXT_PUBLIC_DEMO_PASSWORD=IntegronixDemo2025!

// login/page.tsx
const { error: err } = await supabase.auth.signInWithPassword({
    email: process.env.NEXT_PUBLIC_DEMO_EMAIL ?? '',
    password: process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? '',
});
```

> **Note:** `NEXT_PUBLIC_*` env vars are still client-visible in Next.js — for a production system these credentials should be rotated frequently or the demo flow replaced with Supabase magic links.

---

## FE-BUG-005 — `FhirPanel.copyJson` No Error Handling {#fe-bug-005}

| Field | Detail |
|---|---|
| **Severity** | 🟠 MEDIUM |
| **File** | `src/components/FhirPanel.tsx` |
| **Line** | 13–17 |

### Description

The clipboard copy function uses `navigator.clipboard.writeText()` which is an async promise — but it's called without `await` and without a `.catch()`:

```typescript
function copyJson() {
    navigator.clipboard.writeText(JSON.stringify(fhir, null, 2));  // ← no await, no catch
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
}
```

`navigator.clipboard` requires the page to be in focus and HTTPS context. If it fails (user denies clipboard permission, HTTP origin, or mobile browser restriction), the promise rejects silently. The user sees the "Copied!" badge briefly — but nothing was actually copied. This is especially common in embedded iframes, mobile browsers, and the Safari clipboard API.

### Fix

```typescript
async function copyJson() {
    try {
        await navigator.clipboard.writeText(JSON.stringify(fhir, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    } catch {
        // Fallback — execCommand is deprecated but widely supported
        const el = document.createElement('textarea');
        el.value = JSON.stringify(fhir, null, 2);
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }
}
```

---

## FE-BUG-006 — `analyze/page.tsx` Interval Leaks on Component Unmount {#fe-bug-006}

| Field | Detail |
|---|---|
| **Severity** | 🟠 MEDIUM |
| **File** | `src/app/dashboard/analyze/page.tsx` |
| **Lines** | 32, 40 |

### Description

The pipeline progress stage animation uses `setInterval` but clears it only in the `finally` block of `handleSubmit`. If the user **navigates away** while a pipeline run is in progress, the component unmounts — but the interval keeps running. React will then warn:

> *Warning: Can't perform a React state update on an unmounted component.*

In strict mode or rapid navigation (e.g., user clicks away then back), this can cause stale state updates and memory leaks.

```typescript
// Created inside the handler — no cleanup on unmount
const interval = setInterval(() => { i++; setStageIdx(i); }, 1200);
```

### Fix

Store the ref at component scope and clear in a `useEffect` cleanup:

```typescript
const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

// In handleSubmit
intervalRef.current = setInterval(() => { i++; setStageIdx(i); }, 1200);

// Cleanup on unmount
useEffect(() => {
    return () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
    };
}, []);
```

---

## FE-BUG-007 — Login Loading State Never Resets on Successful Redirect {#fe-bug-007}

| Field | Detail |
|---|---|
| **Severity** | 🟠 MEDIUM |
| **File** | `src/app/auth/login/page.tsx` |
| **Lines** | 17–23 |

### Description

In `handleLogin`, `setLoading(false)` is only called when there is an **error**:
```typescript
async function handleLogin(e: React.FormEvent) {
    setLoading(true); setError('');
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    if (err) { setError(err.message); setLoading(false); }  // ← loading reset ONLY on error
    else router.push('/dashboard/analyze');                   // ← loading stays true, button disabled
}
```

On successful login, loading stays `true` and the button stays disabled. While Next.js navigation begins, there's a brief window where the button is frozen. If the middleware redirect is slow, the user sees a spinner with no explanation. The same issue exists in `handleDemoAccess`.

### Fix

Use a `try/finally` pattern like the pipeline page does:

```typescript
async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError('');
    try {
        const { error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) { setError(err.message); return; }
        router.push('/dashboard/analyze');
    } finally {
        setLoading(false);
    }
}
```

---

## FE-BUG-008 — `CandidateChart` Unused `maxScore` Variable (Dead Code) {#fe-bug-008}

| Field | Detail |
|---|---|
| **Severity** | 🟡 MINOR |
| **File** | `src/components/CandidateChart.tsx` |
| **Line** | 41 |

### Description

`maxScore` is computed but never used anywhere in the component:

```typescript
const maxScore = data[0]?.final_score ?? 1;   // ← computed, never referenced
```

This is dead code — likely intended for a normalized bar chart where bars are scaled relative to the top score, but the Recharts `<XAxis domain={[0, 1]}>` already handles this by fixing the axis from 0 to 1. The variable should be removed to avoid confusion.

### Fix

```typescript
// Remove this line entirely
// const maxScore = data[0]?.final_score ?? 1;
```

---

## FE-BUG-009 — `MultiCodeList` Combined Reimbursement Includes Secondary Codes Misleadingly {#fe-bug-009}

| Field | Detail |
|---|---|
| **Severity** | 🟡 MINOR |
| **File** | `src/components/MultiCodeList.tsx` |
| **Lines** | 100–104 |

### Description

The "Combined Estimated Reimbursement" footer sums `base_reimbursement` across ALL codes — primary, secondary, and additional:

```tsx
${codes.reduce((s, c) => s + c.base_reimbursement, 0).toLocaleString()}
```

In ICD-10 billing, reimbursement is determined by the **principal (primary) diagnosis DRG grouping** — not by adding up each code's individual base rate. Secondary and additional codes affect DRG weight but don't have separate additive reimbursements. Displaying a sum of all codes as "Combined Estimated Reimbursement" could overstate expected revenue, misleading the clinical reviewer.

### Fix

Either:
1. Only show primary code reimbursement with a note explaining DRG grouping
2. Or display the sum with a disclaimer: "Combined base rates — actual reimbursement determined by DRG grouper"

```tsx
{/* Option 1 — only primary */}
<span className="text-sm font-bold text-success">
    ${codes.find(c => c.role === 'primary')?.base_reimbursement.toLocaleString() ?? '—'}
</span>
<span className="text-xs text-slate-600 ml-1">(primary DRG rate)</span>
```

---

## FE-OPT-001 — AuthProvider Supabase Client Not Memoized {#fe-opt-001}

| Field | Detail |
|---|---|
| **Severity** | 🔵 OPTIMIZATION |
| **File** | `src/components/AuthProvider.tsx` + `src/lib/supabase.ts` |

### Description

The `supabase` singleton in `lib/supabase.ts` is created at module load time with `createBrowserClient()`. While `createBrowserClient` internally handles singleton behaviour, it is technically invoked every time the module is imported. For SSR/hydration safety, the recommended pattern per Supabase SSR docs is to use `useMemo` inside the provider:

```typescript
// AuthProvider.tsx — more defensive pattern
const supabase = useMemo(() => createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
), []);
```

This is low priority for the current POC but matters once SSR pages are added.

---

## What's Done Well ✅

| Area | Verdict |
|---|---|
| **TypeScript types (`coding.ts`)** | ✅ Comprehensive — covers FHIR, DRG flags, risk labels, all backend response fields |
| **`ApiError` class (`api.ts`)** | ✅ Proper error subclass with status code, correct `instanceof` usage in catch blocks |
| **`RiskMeter` SVG gauge** | ✅ Correct math, handles all 4 `RiskLabel` values including `UNKNOWN` |
| **`DrgBadge`** | ✅ Correctly guards against null flag with `if (!flag)` before rendering |
| **`MultiCodeList` empty state** | ✅ Handles `codes.length === 0` gracefully |
| **`CandidateChart` empty state** | ✅ Handles `candidates.length === 0` gracefully |
| **`CodeInputPanel` char counter** | ✅ Real-time feedback, correct disable logic, `maxLength` on ICD input |
| **Middleware (`middleware.ts`)** | ✅ Correctly uses `@supabase/ssr` `createServerClient`, proper cookie handling |
| **FHIR JSON copy UX** | ✅ Good fallback visual with "Copied!" state badge |
| **Pipeline interval cycling** | ✅ `stageIdx % PROCESSING_STAGES.length` correctly prevents array out of bounds |

---

## Summary Table

| ID | Severity | File | Issue |
|---|---|---|---|
| FE-BUG-001 | 🟠 High | `AuditCard.tsx` | `CODE_DIVERGENCE` not in `DISCREPANCY_CFG` — shows wrong badge |
| FE-BUG-002 | 🟠 High | `ResultsPanel.tsx` + `IcdCodeCard.tsx` | 3 of 6 `MappingPath` values not mapped → wrong label shown |
| FE-BUG-003 | 🟠 Medium | `AuthProvider.tsx` | `loadProfile` fires unguarded — infinite loading on DB error |
| FE-BUG-004 | 🟠 Medium | `login/page.tsx` | Demo password hardcoded in source |
| FE-BUG-005 | 🟠 Medium | `FhirPanel.tsx` | `clipboard.writeText` unhandled rejection |
| FE-BUG-006 | 🟠 Medium | `analyze/page.tsx` | `setInterval` not cleared on component unmount |
| FE-BUG-007 | 🟠 Medium | `login/page.tsx` | Loading never resets on successful login redirect |
| FE-BUG-008 | 🟡 Minor | `CandidateChart.tsx` | Dead code: `maxScore` computed but never used |
| FE-BUG-009 | 🟡 Minor | `MultiCodeList.tsx` | Combined reimbursement sum is clinically misleading |
| FE-OPT-001 | 🔵 Opt | `AuthProvider.tsx` | Supabase client not memoized — relevant when SSR added |

**Total: 9 issues found across 7 files. None prevent the app from running — all affect correctness, UX, or security.**
