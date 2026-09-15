/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      // Public self-signup was removed: accounts are provisioned directly in
      // Supabase. Any old link lands on sign-in instead of a 404.
      { source: '/auth/signup', destination: '/auth/login', permanent: false },
    ];
  },
};

export default nextConfig;
