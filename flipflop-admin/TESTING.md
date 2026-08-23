# Testing Guide for FlipFlop Admin Dashboard

## Overview

This document describes the testing infrastructure for the flipflop-admin Next.js application.

### Test Types

| Type | Tool | Coverage | Location |
|------|------|----------|----------|
| Unit | Vitest | 80%+ | `**/*.test.ts`, `**/*.test.tsx` |
| Integration | Vitest | With mocking | Same as unit |
| E2E | Playwright | Critical flows | `playwright/` |

---

## Unit & Integration Tests (Vitest)

### Setup

Tests use Vitest + React Testing Library + jsdom.

**Install dependencies:**
```bash
npm install
```

**Vitest configuration:**
- `vitest.config.ts` — Main config
- `vitest.setup.ts` — Global setup (mocks, environment)

### Running Tests

```bash
# Run all tests (watch mode)
npm test

# Run tests once
npm test -- run

# Run specific test file
npm test lib/formatting.test.ts

# Run with UI
npm test:ui

# Run with coverage
npm test:coverage
```

### Coverage Requirements

| Metric | Target |
|--------|--------|
| Lines | 80% |
| Functions | 80% |
| Branches | 75% |
| Statements | 80% |

**Current coverage** is tracked in `coverage/` directory.

### Writing Tests

**Test file location:**
```
lib/formatting.ts        → lib/formatting.test.ts
components/Build.tsx    → components/Build.test.tsx
app/api/prices.ts       → app/api/prices.test.ts
```

**Test structure (AAA pattern):**
```typescript
import { describe, it, expect } from 'vitest'
import { formatCurrency } from './formatting'

describe('formatCurrency', () => {
  it('formats positive amounts as GBP', () => {
    // Arrange
    const amount = 79.99

    // Act
    const result = formatCurrency(amount)

    // Assert
    expect(result).toBe('£79.99')
  })
})
```

**Best practices:**
1. Test behavior, not implementation
2. Use descriptive test names
3. One assertion per test (or tightly related)
4. Mock external dependencies
5. Test edge cases (null, empty, negative)

### Mocking

**Mock Next.js router:**
```typescript
import { useRouter } from 'next/navigation'
import { vi } from 'vitest'

vi.mock('next/navigation')

// In test
const mockPush = vi.fn()
vi.mocked(useRouter).mockReturnValue({
  push: mockPush,
  // ...
})
```

**Mock API calls:**
```typescript
import { vi } from 'vitest'

const mockFetch = vi.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ data: [] }),
  })
)
global.fetch = mockFetch
```

**Mock React Query:**
```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
})

render(
  <QueryClientProvider client={queryClient}>
    <MyComponent />
  </QueryClientProvider>
)
```

### Testing Components

**Example component test:**
```typescript
import { render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { BuildCard } from './BuildCard'

describe('BuildCard', () => {
  it('renders build information', () => {
    const build = { id: 1, name: 'RTX 4070', price: 999 }
    render(<BuildCard build={build} />)
    expect(screen.getByText('RTX 4070')).toBeInTheDocument()
  })

  it('calls onEdit when edit button clicked', async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()
    render(<BuildCard build={build} onEdit={onEdit} />)
    await user.click(screen.getByRole('button', { name: /edit/i }))
    expect(onEdit).toHaveBeenCalled()
  })
})
```

### Testing Hooks

**Example hook test:**
```typescript
import { renderHook, act } from '@testing-library/react'
import { useBuilds } from './useBuilds'

describe('useBuilds', () => {
  it('fetches builds on mount', async () => {
    const { result } = renderHook(() => useBuilds())
    await waitFor(() => {
      expect(result.current.builds).toHaveLength(3)
    })
  })
})
```

---

## E2E Tests (Playwright)

### Setup

Playwright is configured for E2E testing of critical user flows.

**Configuration:**
- `playwright.config.ts`
- Tests: `playwright/**/*.spec.ts`

### Running E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI
npm run test:e2e:ui

# Run in headed mode (see browser)
npm run test:e2e:headed

# Run specific test
npm run test:e2e -- tests/builds.spec.ts
```

### Writing E2E Tests

**Example E2E test:**
```typescript
import { test, expect } from '@playwright/test'

test('User can create and list builds', async ({ page }) => {
  // Navigate
  await page.goto('http://localhost:3000/builds')

  // Create build
  await page.click('button:has-text("New Build")')
  await page.fill('input[name="name"]', 'RTX 4070 Build')
  await page.click('button:has-text("Create")')

  // Verify
  await expect(page.locator('text=RTX 4070 Build')).toBeVisible()
})
```

---

## CI/CD Integration

### Pre-commit

Run tests before committing:
```bash
# Run unit tests
npm test -- run

# Run coverage check
npm test:coverage
```

### Pre-push

Run full test suite:
```bash
# All tests
npm test -- run
npm run test:e2e
```

### GitHub Actions

Example workflow:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 20
      - run: npm install
      - run: npm test -- run --coverage
      - run: npm run test:e2e
```

---

## Debugging Tests

### Debug in VS Code

Add to `.vscode/launch.json`:
```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug Vitest",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["test", "--", "--inspect-brk"],
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen"
}
```

### Debug with UI

```bash
npm run test:ui
```

Opens browser-based test explorer with live debugging.

### Debug E2E

```bash
npm run test:e2e:headed
```

Runs tests in headed mode so you see the browser.

---

## Test Coverage Goals

### Phase 1 (Initial)
- **Target**: 60% overall
- **Priority**: Core business logic (formatting, calculations, API calls)

### Phase 2 (Consolidation)
- **Target**: 75% overall
- **Priority**: Components, hooks, edge cases

### Phase 3 (Comprehensive)
- **Target**: 80%+ overall
- **Priority**: All user flows, error cases, integration

---

## Common Patterns

### Testing API calls
```typescript
it('fetches builds from API', async () => {
  const mockData = [{ id: 1, name: 'Build 1' }]
  global.fetch = vi.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve(mockData),
    })
  )

  const result = await getBuilds()
  expect(result).toEqual(mockData)
})
```

### Testing with data-testid
```tsx
// Component
<button data-testid="submit-btn">Submit</button>

// Test
await user.click(screen.getByTestId('submit-btn'))
```

### Testing async operations
```typescript
it('loads builds asynchronously', async () => {
  const { result } = renderHook(() => useBuilds())

  await waitFor(() => {
    expect(result.current.isLoading).toBe(false)
  })

  expect(result.current.builds).toHaveLength(3)
})
```

---

## Troubleshooting

### Issue: "Cannot find module"
- Check import paths
- Ensure vitest.config.ts has correct `alias`
- Rebuild TypeScript cache: `rm -rf node_modules/.vite`

### Issue: "window is not defined"
- Ensure `environment: 'jsdom'` in vitest.config.ts
- Check vitest.setup.ts is loading

### Issue: "Timeout"
- Increase timeout: `it('slow test', async () => {...}, { timeout: 5000 })`
- Check for missing `await` in async tests

### Issue: Tests pass locally but fail in CI
- Check Node version matches
- Ensure all env vars are set
- Run: `npm install` (clean install)
- Check for timezone/locale differences

---

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Documentation](https://playwright.dev/)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

---

## Next Steps

1. Install dependencies: `npm install`
2. Run formatting tests: `npm test lib/formatting.test.ts`
3. Add tests for existing components
4. Set up CI/CD test workflows
5. Aim for 80%+ coverage by Phase 3
