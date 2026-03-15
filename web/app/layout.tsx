import type { Metadata, Viewport } from 'next'
import { JetBrains_Mono } from 'next/font/google'
import { GeistPixelGrid } from 'geist/font/pixel'
import { ThemeProvider } from '@/components/theme-provider'

import './globals.css'

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'Crowd Signal | Market Crowd Simulation',
  description:
    'See how the market crowd will react before it happens. Crowd Signal simulates how retail bulls, bears, whales, and algos respond to a market catalyst and returns a probability map, not a prediction.',
  keywords: [
    'brutalist landing page template',
    'AI SaaS template',
    'engineering UI kit',
    'Next.js landing page',
    'Tailwind CSS template',
    'dark UI template',
    'Geist Pixel font',
    'bento grid layout',
    'SaaS pricing page',
    'Framer Motion animations',
    'monospace design system',
    'developer landing page',
    'AI infrastructure template',
    'industrial web design',
    'dot matrix typography',
    'terminal UI components',
    'startup landing page',
    'tech landing page template',
  ],
  authors: [{ name: 'Crowd Signal Team' }],
  creator: 'Crowd Signal Team',
  publisher: 'Crowd Signal Team',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    title: 'Crowd Signal | Market Crowd Simulation',
    description:
      'Crowd Signal simulates how trader archetypes react to a catalyst over the next 1 to 4 hours and returns a probability map for intraday crowd behavior.',
    siteName: 'Crowd Signal',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Crowd Signal | Market Crowd Simulation',
    description:
      'See how the market crowd will react before it happens. Probabilistic simulation for intraday stock sentiment.',
    creator: '@crowdsignal',
  },
  category: 'technology',
}

export const viewport: Viewport = {
  themeColor: '#F2F1EA',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${jetbrainsMono.variable} ${GeistPixelGrid.variable}`} suppressHydrationWarning>
      <body className="font-mono antialiased">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
