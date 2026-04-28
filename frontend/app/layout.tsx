import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Aegis',
  description: 'Multi-agent AI application builder',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[#0f172a] min-h-screen relative overflow-x-hidden`}>
        {/* Decorative glow blobs */}
        <div
          className="pointer-events-none fixed top-0 right-0 w-[700px] h-[700px] rounded-full"
          style={{
            background: 'radial-gradient(circle, #9333ea 0%, transparent 70%)',
            filter: 'blur(80px)',
            opacity: 0.10,
            transform: 'translate(30%, -30%)',
          }}
        />
        <div
          className="pointer-events-none fixed bottom-0 left-0 w-[700px] h-[700px] rounded-full"
          style={{
            background: 'radial-gradient(circle, #4f46e5 0%, transparent 70%)',
            filter: 'blur(80px)',
            opacity: 0.10,
            transform: 'translate(-30%, 30%)',
          }}
        />
        {children}
      </body>
    </html>
  )
}
