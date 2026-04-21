import './globals.css';
import type {Metadata} from 'next';
import type {ReactNode} from 'react';

export const metadata: Metadata = {
  title: 'BudgetWings',
  description: 'Agent-first cheap travel discovery, guides, evaluation, and deployment dashboard.',
};

export default function RootLayout({children}: Readonly<{children: ReactNode}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
