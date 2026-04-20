import './globals.css';
import type {Metadata} from 'next';
import type {ReactNode} from 'react';

export const metadata: Metadata = {
  title: 'BudgetWings',
  description: 'AI-powered low-cost travel intelligence.'
};

export default function RootLayout({children}: Readonly<{children: ReactNode}>) {
  return (
    <html lang="zh-CN">
      <body className="bg-paper text-ink antialiased dark:bg-zinc-950 dark:text-zinc-100">
        {children}
      </body>
    </html>
  );
}
