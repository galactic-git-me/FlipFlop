import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.FLIPFLOP_API_BASE || 'http://localhost:18000/api/:path*',
      },
    ]
  },
}

export default nextConfig
