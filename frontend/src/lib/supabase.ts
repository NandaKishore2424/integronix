import { createBrowserClient } from '@supabase/ssr';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// Single browser client instance — safe for 'use client' components only
export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);

// Types matching our public.users table
export type UserRole = 'admin' | 'auditor' | 'coder';

export interface OrgUser {
    id: string;
    auth_id: string;
    organization_id: string;
    branch_id: string | null;
    email: string;
    full_name: string;
    role: UserRole;
}

export interface Organization {
    id: string;
    name: string;
    slug: string;
    type: string;
}

export interface Branch {
    id: string;
    organization_id: string;
    name: string;
    code: string | null;
    city: string | null;
    state: string | null;
}
