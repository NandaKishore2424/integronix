-- ============================================================
-- Migration 021: Atomic claim adjudication
--
-- WHY: the API previously adjudicated in three separate requests:
--   fetch claim → check status in Python → update → (best-effort) audit insert.
-- Two concurrent APPROVEs both passed the Python status check (TOCTOU) and
-- both "won"; the HIPAA audit write happened AFTER the money moved and was
-- swallowed on failure; adjudicated_at was never set at all.
--
-- PostgREST cannot span a transaction across requests, so the invariant moves
-- into the database: one function, one transaction. The status check is part
-- of the UPDATE's WHERE clause (optimistic lock — a concurrent writer makes
-- FOUND false instead of double-paying), and the audit row commits atomically
-- with the status change or not at all.
-- ============================================================

CREATE OR REPLACE FUNCTION public.adjudicate_claim(
    p_claim_id               uuid,
    p_expected_status        text,
    p_new_status             text,
    p_total_allowed          numeric,
    p_total_paid             numeric,
    p_patient_responsibility numeric,
    p_denial_reason          text,
    p_action_notes           text,
    p_changed_by_user_id     uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_prev_status text;
    v_current     text;
BEGIN
    UPDATE public.claims
       SET status                 = p_new_status,
           total_allowed_amount   = p_total_allowed,
           total_paid_amount      = p_total_paid,
           patient_responsibility = p_patient_responsibility,
           denial_reason          = p_denial_reason,
           adjudicated_at         = now(),
           updated_at             = now()
     WHERE id     = p_claim_id
       AND status = p_expected_status          -- optimistic lock
    RETURNING p_expected_status INTO v_prev_status;

    IF NOT FOUND THEN
        SELECT status INTO v_current FROM public.claims WHERE id = p_claim_id;
        RETURN jsonb_build_object(
            'ok', false,
            'reason', CASE WHEN v_current IS NULL THEN 'not_found' ELSE 'status_conflict' END,
            'current_status', v_current
        );
    END IF;

    -- Audit is part of the SAME transaction: if this insert fails, the status
    -- change above rolls back with it. A paid claim without an audit row can
    -- no longer exist.
    INSERT INTO public.claim_audit_logs
        (claim_id, previous_status, new_status, action_notes, changed_by_user_id)
    VALUES
        (p_claim_id, v_prev_status, p_new_status, p_action_notes, p_changed_by_user_id);

    RETURN jsonb_build_object('ok', true, 'previous_status', v_prev_status,
                              'new_status', p_new_status);
END;
$$;

-- Only the backend (service role) may call this; the browser must go through
-- the API, which enforces payer-org access checks first.
REVOKE ALL ON FUNCTION public.adjudicate_claim(uuid,text,text,numeric,numeric,numeric,text,text,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.adjudicate_claim(uuid,text,text,numeric,numeric,numeric,text,text,uuid) TO service_role;

-- Same contract for plain status transitions (appeal, etc.): optimistic lock
-- against a set of expected statuses + atomic audit row.
CREATE OR REPLACE FUNCTION public.change_claim_status(
    p_claim_id           uuid,
    p_expected_statuses  text[],
    p_new_status         text,
    p_action_notes       text,
    p_changed_by_user_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_prev    text;
    v_current text;
BEGIN
    -- The old row must be captured BEFORE the update: a subquery inside
    -- RETURNING sees the post-update row. The self-join locks the row and
    -- hands us its pre-update status in one statement.
    UPDATE public.claims c
       SET status = p_new_status, updated_at = now()
      FROM (SELECT id, status FROM public.claims WHERE id = p_claim_id FOR UPDATE) old
     WHERE c.id = old.id
       AND old.status = ANY (p_expected_statuses)
    RETURNING old.status INTO v_prev;

    IF NOT FOUND THEN
        SELECT status INTO v_current FROM public.claims WHERE id = p_claim_id;
        RETURN jsonb_build_object(
            'ok', false,
            'reason', CASE WHEN v_current IS NULL THEN 'not_found' ELSE 'status_conflict' END,
            'current_status', v_current
        );
    END IF;

    INSERT INTO public.claim_audit_logs
        (claim_id, previous_status, new_status, action_notes, changed_by_user_id)
    VALUES
        (p_claim_id, v_prev, p_new_status, p_action_notes, p_changed_by_user_id);

    RETURN jsonb_build_object('ok', true, 'new_status', p_new_status);
END;
$$;

REVOKE ALL ON FUNCTION public.change_claim_status(uuid,text[],text,text,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.change_claim_status(uuid,text[],text,text,uuid) TO service_role;
