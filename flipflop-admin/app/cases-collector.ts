/**
 * Browser-side case collector for Overclockers search results.
 * Drop this in the browser console on Overclockers /search?sSearch=PC+case
 * to collect all visible cases and submit them in bulk.
 *
 * Usage:
 *   1. Open https://www.overclockers.co.uk/search?sSearch=PC+case (logged in)
 *   2. Paste this entire script into the browser console (F12)
 *   3. Call: collectAndSubmitCases()
 *   4. Script will collect all paginated results and submit to backend
 */

interface CaseData {
  name: string
  price: number
  source_site: string
  source_url: string
  image_url: string | null
  theme: string
  supplier: string
  rating: number | null
  in_stock: boolean
  specs: string | null
}

async function extractCasesFromPage(): Promise<CaseData[]> {
  const cases: CaseData[] = []
  const seen = new Set<string>()

  // Overclockers product listing structure (adjust selectors if needed)
  const products = document.querySelectorAll(
    '[data-component-type="product-card"], .product, .listing-product, [class*="product-item"]'
  )

  products.forEach((product) => {
    try {
      // Extract name/title
      const nameEl =
        product.querySelector('h2, h3, .product-name, [class*="title"]') ||
        product.querySelector('a')
      const name = nameEl?.textContent?.trim().slice(0, 300)
      if (!name || name.length < 5) return

      // Extract price
      const priceEl = product.querySelector(
        '.price, [class*="price"], .product-price'
      )
      const priceText =
        priceEl?.textContent?.match(/£?([\d,]+(?:\.\d{2})?)/)?.[1] || ''
      const price = parseFloat(priceText.replace(/,/g, ''))
      if (!price || price <= 0 || price > 2000) return

      // Extract URL
      const linkEl = product.querySelector('a[href]') as HTMLAnchorElement
      const source_url = linkEl?.href || ''
      if (!source_url || !source_url.startsWith('http')) return

      // Deduplicate
      if (seen.has(source_url)) return
      seen.add(source_url)

      // Extract image
      const imgEl = product.querySelector('img') as HTMLImageElement
      const image_url = imgEl?.src || imgEl?.getAttribute('data-src') || null

      // Extract stock status
      const stockEl = product.querySelector('[class*="stock"], [class*="availability"]')
      const in_stock = !stockEl?.textContent?.toLowerCase().includes('out of stock')

      // Extract specs (if visible)
      const specsEl = product.querySelector(
        '[class*="specs"], [class*="description"]'
      )
      const specs = specsEl?.textContent?.slice(0, 200) || null

      cases.push({
        name,
        price,
        source_site: 'Overclockers',
        source_url,
        image_url,
        theme: 'Overclockers Collection',
        supplier: 'Overclockers',
        rating: null,
        in_stock,
        specs,
      })
    } catch (e) {
      console.debug('Failed to extract case:', e)
    }
  })

  return cases
}

async function collectAllPages(): Promise<CaseData[]> {
  const allCases: CaseData[] = []

  // Extract current page
  const currentCases = await extractCasesFromPage()
  allCases.push(...currentCases)
  console.log(
    `Collected ${currentCases.length} cases from current page, total: ${allCases.length}`
  )

  // Check for pagination and collect next pages
  const nextButton = document.querySelector(
    'a[rel="next"], [class*="next"], button:contains("Next")'
  ) as HTMLElement
  if (nextButton && !nextButton.getAttribute('aria-disabled')) {
    console.log('Moving to next page...')
    nextButton.click()
    await new Promise((resolve) => setTimeout(resolve, 2000)) // Wait for page load
    const nextCases = await collectAllPages()
    allCases.push(...nextCases)
  } else {
    console.log('No more pages to collect')
  }

  return allCases
}

async function submitCasesToBackend(cases: CaseData[]): Promise<void> {
  if (!cases.length) {
    console.warn('No cases to submit')
    return
  }

  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')
  const apiUrl = `${apiBase}/api/cases/bulk-import`

  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ cases }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(`API error: ${response.status} ${JSON.stringify(error)}`)
    }

    const result = await response.json()
    console.log('✅ Cases submitted successfully:', result)
    console.log(`Inserted: ${result.inserted}, Updated: ${result.updated}, Skipped: ${result.skipped}, Errors: ${result.errors}`)
  } catch (error) {
    console.error('❌ Failed to submit cases:', error)
    throw error
  }
}

async function collectAndSubmitCases(): Promise<void> {
  console.log('🔄 Starting case collection from Overclockers...')
  try {
    const cases = await collectAllPages()
    console.log(`Collected ${cases.length} cases total`)

    if (cases.length === 0) {
      console.warn('No cases found. Check selectors for this Overclockers page.')
      return
    }

    console.log('📤 Submitting to backend...')
    await submitCasesToBackend(cases)
    console.log('✅ Collection and submission complete!')
  } catch (error) {
    console.error('❌ Collection failed:', error)
  }
}

// Export for browser console
export {};

declare global {
  interface Window {
    collectAndSubmitCases: typeof collectAndSubmitCases
  }
}

window.collectAndSubmitCases = collectAndSubmitCases

console.log(
  '✅ Case collector loaded. Run: collectAndSubmitCases() to start.'
)
