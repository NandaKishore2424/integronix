import { redirect } from 'next/navigation';

/**
 * Payer "/Adjudications" nav link points to this base route.
 * The actual adjudication UI lives under "/payer/adjudicate/[id]".
 *
 * To avoid a 404 when the user clicks the sidebar item, redirect to the
 * claim queue where the "Review Case" buttons route to the correct page.
 */
export default function PayerAdjudicateIndexPage() {
    // This route is only here because the sidebar/links might point to it.
    // Redirect immediately to the queue so users never see a blank page.
    redirect('/payer/inbox');
}

