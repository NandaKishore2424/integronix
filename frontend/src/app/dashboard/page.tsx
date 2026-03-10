import { redirect } from 'next/navigation';

// Redirect /dashboard → /dashboard/analyze
export default function DashboardIndex() {
    redirect('/dashboard/analyze');
}
