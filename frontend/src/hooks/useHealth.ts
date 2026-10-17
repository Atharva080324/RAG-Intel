/**
 * useHealth – polls /ready every 2 s while warming up, then every 30 s once warm.
 * Tracks reachable status and model warm-up status.
 */
import { useEffect, useState } from 'react'
import { readyApi } from '@/api/client'

export interface HealthState {
  reachable: boolean
  warmedUp: boolean
  checking: boolean
}

export function useHealth(): HealthState {
  const [reachable, setReachable] = useState(false)
  const [warmedUp, setWarmedUp] = useState(false)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let mounted = true
    let timeout: ReturnType<typeof setTimeout>

    const check = async () => {
      try {
        const res = await readyApi.check()
        if (mounted) {
          const warm = !!res.warmed_up
          setReachable(true)
          setWarmedUp(warm)
          setChecking(false)

          // If reachable but still warming up, poll fast (2s). Once warm, poll relaxed (30s).
          timeout = setTimeout(check, warm ? 30_000 : 2_000)
        }
      } catch {
        if (mounted) {
          setReachable(false)
          setWarmedUp(false)
          setChecking(false)
          // Retry every 3 s when unreachable
          timeout = setTimeout(check, 3_000)
        }
      }
    }

    void check()
    return () => {
      mounted = false
      clearTimeout(timeout)
    }
  }, [])

  return { reachable, warmedUp, checking }
}

