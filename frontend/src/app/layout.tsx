import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/components/AuthProvider';

export const metadata: Metadata = {
  title: 'Integronix — Revenue Integrity Platform',
  description: 'AI-powered ICD-10-CM coding engine with revenue integrity analysis, SNOMED mapping, and FHIR output.',
  keywords: ['ICD-10', 'clinical coding', 'RCM', 'SNOMED', 'FHIR', 'AI', 'healthcare'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-screen overflow-x-hidden">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
