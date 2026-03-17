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

    // Protect /hospital/* and /payer/* — redirect to login if not authenticated
    if ((pathname.startsWith('/hospital') || pathname.startsWith('/payer')) && !isLoggedIn) {
        return NextResponse.redirect(new URL('/auth/login', request.url));
    }

    // /auth/* — redirect already-logged-in users to dashboard
    if (pathname.startsWith('/auth') && isLoggedIn) {
        return NextResponse.redirect(new URL('/hospital/coder/analyze', request.url));
    }

    return response;
}

export const config = {
    // Match all routes except static assets
    matcher: [
        '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
    ],
};
