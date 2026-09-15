import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/components/AuthProvider';

export const metadata: Metadata = {
  title: 'Integronix — Clinical Coding & Revenue Integrity Engine',
  description:
    'A portfolio project by Nanda Kishore R: an agentic LangGraph pipeline that derives ICD-10-CM and CPT codes from clinical notes, with deterministic, evidence-backed code selection and a transactional claims workflow.',
  keywords: ['ICD-10-CM', 'clinical coding', 'LangGraph', 'FastAPI', 'pgvector', 'FHIR', 'EDI 837', 'revenue cycle'],
  openGraph: {
    title: 'Integronix — Clinical Coding & Revenue Integrity Engine',
    description:
      'Agentic clinical coding with deterministic, evidence-backed code selection. A portfolio project by Nanda Kishore R.',
    type: 'website',
  },
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
