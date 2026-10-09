import { CuratedBuildsResponse, CaseItem } from './types'

const API_BASE = typeof window !== 'undefined' 
  ? '' 
  : (process.env.FLIPFLOP_API_BASE || 'http://localhost:18000')

export async function getCuratedBuilds(): Promise<CuratedBuildsResponse> {
  const res = await fetch(`${API_BASE}/api/public/curated-builds`, {
    cache: 'no-store',
  })
  
  if (!res.ok) {
    throw new Error(`Failed to fetch curated builds: ${res.status}`)
  }
  
  const data = await res.json()
  return { builds: data }
}

export async function getCases(): Promise<CaseItem[]> {
  const res = await fetch(`${API_BASE}/api/public/cases`, {
    cache: 'no-store',
  })
  
  if (!res.ok) {
    throw new Error(`Failed to fetch cases: ${res.status}`)
  }
  
  return res.json()
}

export async function getCuratedBuildById(id: string): Promise<any> {
  const { builds } = await getCuratedBuilds()
  return builds.find(b => b.id === id)
}
