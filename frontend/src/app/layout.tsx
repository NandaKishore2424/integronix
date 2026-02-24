import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Integronix — AI Clinical Coding Engine',
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
      <body className="min-h-screen overflow-x-hidden">{children}</body>
    </html>
  );
}
