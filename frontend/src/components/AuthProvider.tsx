'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { supabase, OrgUser, Organization } from '@/lib/supabase';
import type { User } from '@supabase/supabase-js';

interface AuthContextValue {
    authUser: User | null;
    orgUser: OrgUser | null;
    org: Organization | null;
    loading: boolean;
    profileError: string | null;
    signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
    authUser: null,
    orgUser: null,
    org: null,
    loading: true,
    profileError: null,
    signOut: async () => { },
});

export function AuthProvider({ children }: { children: ReactNode }) {
    const [authUser, setAuthUser] = useState<User | null>(null);
    const [orgUser, setOrgUser] = useState<OrgUser | null>(null);
    const [org, setOrg] = useState<Organization | null>(null);
    const [loading, setLoading] = useState(true);
    // FIX FE-BUG-003: Surface profile load errors to consumers instead of swallowing them
    const [profileError, setProfileError] = useState<string | null>(null);

    // FIX FE-BUG-003: loadProfile now has try/catch — errors don't cause infinite loading
    async function loadProfile(user: User): Promise<void> {
        setProfileError(null);
        try {
            const { data: userRow, error: userErr } = await supabase
                .from('users')
                .select('*')
                .eq('auth_id', user.id)
                .single();

            if (userErr) throw userErr;

            if (userRow) {
                setOrgUser(userRow as OrgUser);
                const { data: orgRow, error: orgErr } = await supabase
                    .from('organizations')
                    .select('*')
                    .eq('id', userRow.organization_id)
                    .single();

                if (orgErr) throw orgErr;
                if (orgRow) setOrg(orgRow as Organization);
            }
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to load user profile.';
            console.error('[AuthProvider] loadProfile error:', message);
            setProfileError(message);
        }
    }

    useEffect(() => {
        // Initial session check
        supabase.auth.getSession().then(({ data: { session } }) => {
            const user = session?.user ?? null;
            setAuthUser(user);
            if (user) {
                // FIX FE-BUG-003: .finally() ensures loading is always cleared, even on error
                loadProfile(user).finally(() => setLoading(false));
            } else {
                setLoading(false);
            }
        });

        // Listen for auth changes (login, logout, token refresh)
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            const user = session?.user ?? null;
            setAuthUser(user);
            if (user) {
                // FIX FE-BUG-003: now awaited properly via .finally() to always reset loading
                loadProfile(user).finally(() => setLoading(false));
            } else {
                setOrgUser(null);
                setOrg(null);
                setProfileError(null);
                setLoading(false);
            }
        });

        return () => subscription.unsubscribe();
    }, []);

    const signOut = async () => {
        await supabase.auth.signOut();
        setAuthUser(null);
        setOrgUser(null);
        setOrg(null);
        setProfileError(null);
        window.location.href = '/auth/login';
    };

    return (
        <AuthContext.Provider value={{ authUser, orgUser, org, loading, profileError, signOut }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
