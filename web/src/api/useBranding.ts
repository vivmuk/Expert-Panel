// Brand Studio assets: watercolor art the server generates via Venice image
// models. Kicks off generation for missing slots and polls while working.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

export interface BrandAsset {
  url: string | null
  generating: boolean
}

export type BrandAssets = Record<string, BrandAsset>

export function useBranding() {
  const queryClient = useQueryClient()
  const ensured = useRef(false)
  const { data } = useQuery<BrandAssets>({
    queryKey: ['branding'],
    queryFn: () => fetch('/api/branding/assets').then((r) => r.json()),
    refetchInterval: (query) => {
      const assets = query.state.data
      if (!assets) return false
      return Object.values(assets).some((a) => a.generating) ? 4000 : false
    },
  })

  useEffect(() => {
    if (!data || ensured.current) return
    const missing = Object.values(data).some((a) => !a.url && !a.generating)
    if (missing) {
      ensured.current = true
      fetch('/api/branding/ensure', { method: 'POST' })
        .then(() => queryClient.invalidateQueries({ queryKey: ['branding'] }))
        .catch(() => {})
    }
  }, [data, queryClient])

  return data ?? {}
}

export function regenerateBranding(slot?: string) {
  return fetch('/api/branding/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(slot ? { slot } : {}),
  })
}
