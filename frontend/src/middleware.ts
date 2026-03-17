import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;
    const response = NextResponse.next({ request });

    // Create a Supabase server client that reads/writes cookies correctly
    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                getAll() {
                    return request.cookies.getAll();
                },
                setAll(cookiesToSet) {
                    cookiesToSet.forEach(({ name, value, options }) => {
                        request.cookies.set(name, value);
                        response.cookies.set(name, value, options);
                    });
                },
            },
        }
    );

    // Refresh session — keeps tokens alive
    const { data: { session } } = await supabase.auth.getSession();
    const isLoggedIn = !!session;

    // ── 1. Auth guard: redirect unauthenticated users to /auth/login ──────────
    const isProtectedPath = pathname.startsWith('/hospital') || pathname.startsWith('/payer');
    if (isProtectedPath && !isLoggedIn) {
        return NextResponse.redirect(new URL('/auth/login', request.url));
    }

    // ── 2. Already logged in + visiting /auth/* → redirect to home ───────────
    if (pathname.startsWith('/auth') && isLoggedIn) {
        // Will be redirected correctly by role below after profile load on the client
        return NextResponse.redirect(new URL('/hospital/coder/analyze', request.url));
    }

    // ── 3. RBAC: fetch user role from DB and enforce route access ────────────
    if (isProtectedPath && isLoggedIn && session?.user?.id) {
        const { data: userRow } = await supabase
            .from('users')
            .select('role')
            .eq('auth_id', session.user.id)
            .single();

        const role = userRow?.role as string | null;

        // If no DB user found yet (e.g. in signup flow), let it through
        if (!role) return response;

        // /hospital/coder/* → only coder or admin
        if (pathname.startsWith('/hospital/coder') && !['coder', 'admin'].includes(role)) {
            return NextResponse.redirect(new URL('/403', request.url));
        }

        // /hospital/rcm/* → only rcm or admin
        if (pathname.startsWith('/hospital/rcm') && !['rcm', 'admin'].includes(role)) {
            return NextResponse.redirect(new URL('/403', request.url));
        }

        // /hospital/admin/* → only admin
        if (pathname.startsWith('/hospital/admin') && role !== 'admin') {
            return NextResponse.redirect(new URL('/403', request.url));
        }

        // /payer/* → only payer (or admin for ops support)
        if (pathname.startsWith('/payer') && !['payer', 'admin'].includes(role)) {
            return NextResponse.redirect(new URL('/403', request.url));
        }
    }

    return response;
}

export const config = {
    // Match all routes except static assets
    matcher: [
        '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
    ],
};

