import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderHook, act } from '@testing-library/react';
import { OSSelector } from '@/components/os-selection/OSSelector';
import { ThemePicker } from '@/components/theme-picker/ThemePicker';
import { OrderSummary } from '@/components/order-summary/OrderSummary';
import { useOSStore } from '@/lib/os-store';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch as jest.Mock;

// Mock next/router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    back: jest.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Image from next/image
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line jsx-a11y/alt-text
    return <img {...props} />;
  },
}));

describe('OS Selector Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render OS selector with options', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, name: 'Windows 11', price: 150 },
          { id: 2, name: 'Ubuntu Linux', price: 0 },
        ],
      }),
    });

    render(<OSSelector />);

    await waitFor(() => {
      expect(screen.getByText('Windows 11')).toBeInTheDocument();
      expect(screen.getByText('Ubuntu Linux')).toBeInTheDocument();
    });
  });

  it('should handle OS selection', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, name: 'Windows 11', price: 150 },
          { id: 2, name: 'Ubuntu Linux', price: 0 },
        ],
      }),
    });

    render(<OSSelector />);

    const windowsRadio = await screen.findByLabelText(/Select Windows 11/);
    fireEvent.click(windowsRadio);

    expect(windowsRadio).toBeChecked();
  });

  it('should show license key dropdown when Windows is selected', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, name: 'Windows 11', price: 150 },
            { id: 2, name: 'Ubuntu Linux', price: 0 },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, key: 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX', available: true },
            { id: 2, key: 'YYYYY-YYYYY-YYYYY-YYYYY-YYYYY', available: false },
          ],
        }),
      });

    render(<OSSelector />);

    const windowsRadio = await screen.findByLabelText(/Select Windows 11/);
    fireEvent.click(windowsRadio);

    await waitFor(() => {
      expect(screen.getByLabelText(/Select Windows license/)).toBeInTheDocument();
    });
  });

  it('should display license availability status', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, name: 'Windows 11', price: 150 },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, key: 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX', available: true },
          ],
        }),
      });

    render(<OSSelector />);

    const windowsRadio = await screen.findByLabelText(/Select Windows 11/);
    fireEvent.click(windowsRadio);

    await waitFor(() => {
      expect(screen.getByText(/✓ Available/)).toBeInTheDocument();
    });
  });

  it('should not show license dropdown for Linux', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, name: 'Windows 11', price: 150 },
          { id: 2, name: 'Ubuntu Linux', price: 0 },
        ],
      }),
    });

    render(<OSSelector />);

    const linuxRadio = await screen.findByLabelText(/Select Ubuntu Linux/);
    fireEvent.click(linuxRadio);

    expect(screen.queryByLabelText(/Select Windows license/)).not.toBeInTheDocument();
  });

  it('should display OS prices', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, name: 'Windows 11', price: 150 },
          { id: 2, name: 'Ubuntu Linux', price: 0 },
        ],
      }),
    });

    render(<OSSelector />);

    await waitFor(() => {
      expect(screen.getByText('+£150.00')).toBeInTheDocument();
      expect(screen.getByText('+£0.00')).toBeInTheDocument();
    });
  });

  it('should handle API errors gracefully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });

    render(<OSSelector />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch/)).toBeInTheDocument();
    });
  });
});

describe('Theme Picker Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset store
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.reset();
    });
  });

  it('should not render when non-Windows OS is selected', () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 2, name: 'Ubuntu Linux', price: 0 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    });

    const { container } = render(<ThemePicker />);
    expect(container.firstChild).toBeNull();
  });

  it('should render themes when Windows is selected', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 1,
            name: 'Cyberpunk Blue',
            category: 'Gaming',
            preview_image_url: '/images/theme1.png',
            widgets_included: 'Clock, Weather, System Monitor',
          },
          {
            id: 2,
            name: 'Forest Green',
            category: 'Minimal',
            preview_image_url: '/images/theme2.png',
            widgets_included: 'Clock, Calendar',
          },
        ],
      }),
    });

    render(<ThemePicker />);

    await waitFor(() => {
      expect(screen.getByText('Cyberpunk Blue')).toBeInTheDocument();
      expect(screen.getByText('Forest Green')).toBeInTheDocument();
    });
  });

  it('should handle theme selection', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 1,
            name: 'Cyberpunk Blue',
            category: 'Gaming',
            preview_image_url: '/images/theme1.png',
            widgets_included: 'Clock, Weather, System Monitor',
          },
        ],
      }),
    });

    render(<ThemePicker />);

    const themeCard = await screen.findByRole('button', {
      name: /Select Cyberpunk Blue theme/,
    });
    fireEvent.click(themeCard);

    expect(screen.getByText('✓ Selected')).toBeInTheDocument();
  });

  it('should display theme categories', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 1,
            name: 'Cyberpunk Blue',
            category: 'Gaming',
            preview_image_url: '/images/theme1.png',
            widgets_included: 'Clock, Weather, System Monitor',
          },
          {
            id: 2,
            name: 'Minimal White',
            category: 'Minimal',
            preview_image_url: '/images/theme2.png',
            widgets_included: 'Clock, Calendar',
          },
        ],
      }),
    });

    render(<ThemePicker />);

    await waitFor(() => {
      expect(screen.getByText('Gaming')).toBeInTheDocument();
      expect(screen.getByText('Minimal')).toBeInTheDocument();
    });
  });

  it('should display theme descriptions', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 1,
            name: 'Cyberpunk Blue',
            category: 'Gaming',
            preview_image_url: '/images/theme1.png',
            widgets_included: 'Clock, Weather, System Monitor',
          },
        ],
      }),
    });

    render(<ThemePicker />);

    await waitFor(() => {
      expect(screen.getByText('Clock, Weather, System Monitor')).toBeInTheDocument();
    });
  });

  it('should handle theme loading errors', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });

    render(<ThemePicker />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch/)).toBeInTheDocument();
    });
  });
});

describe('Order Summary Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should display all order components', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: 'Intel Core i9-13900KS',
        gpu_name: 'NVIDIA RTX 4080 Super',
        ram_name: '32GB DDR5',
        ssd_name: '2TB NVMe SSD',
        psu_name: '1200W Platinum',
        case_name: 'NZXT H510 Flow',
        cooler_name: 'Corsair H150i',
        parts_cost_total: 2500,
        labor_cost: 75,
        overhead_cost: 250,
        total_price: 2825,
      }),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText(/Intel Core i9-13900KS/)).toBeInTheDocument();
      expect(screen.getByText(/NVIDIA RTX 4080 Super/)).toBeInTheDocument();
      expect(screen.getByText(/32GB DDR5/)).toBeInTheDocument();
    });
  });

  it('should display OS selection in summary', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
      result.current.setLicense({
        id: 1,
        key: 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX',
        available: true,
      });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: 'Intel Core i5',
        gpu_name: 'NVIDIA RTX 4060',
        ram_name: '16GB DDR4',
        ssd_name: '512GB SSD',
        psu_name: '650W',
        case_name: 'NZXT H510',
        cooler_name: 'Stock Cooler',
        parts_cost_total: 800,
        labor_cost: 75,
        overhead_cost: 100,
        total_price: 975,
      }),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText('Windows 11')).toBeInTheDocument();
    });
  });

  it('should display theme in summary when selected', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
      result.current.setTheme({
        id: 1,
        name: 'Cyberpunk Blue',
        category: 'Gaming',
        preview_image_url: '/images/theme1.png',
        widgets_included: 'Clock, Weather, System Monitor',
      });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: 'Intel Core i5',
        gpu_name: 'NVIDIA RTX 4060',
        ram_name: '16GB DDR4',
        ssd_name: '512GB SSD',
        psu_name: '650W',
        case_name: 'NZXT H510',
        cooler_name: 'Stock Cooler',
        parts_cost_total: 800,
        labor_cost: 75,
        overhead_cost: 100,
        total_price: 975,
      }),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText('Cyberpunk Blue (Gaming)')).toBeInTheDocument();
    });
  });

  it('should calculate total price including OS cost', async () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: 'Intel Core i5',
        gpu_name: 'NVIDIA RTX 4060',
        ram_name: '16GB DDR4',
        ssd_name: '512GB SSD',
        psu_name: '650W',
        case_name: 'NZXT H510',
        cooler_name: 'Stock Cooler',
        parts_cost_total: 800,
        labor_cost: 75,
        overhead_cost: 100,
        total_price: 975,
      }),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText(/£1,125.00/)).toBeInTheDocument();
    });
  });

  it('should display price breakdown', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: 'Intel Core i5',
        gpu_name: 'NVIDIA RTX 4060',
        ram_name: '16GB DDR4',
        ssd_name: '512GB SSD',
        psu_name: '650W',
        case_name: 'NZXT H510',
        cooler_name: 'Stock Cooler',
        parts_cost_total: 800,
        labor_cost: 75,
        overhead_cost: 100,
        total_price: 975,
      }),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText('Parts')).toBeInTheDocument();
      expect(screen.getByText('Labor')).toBeInTheDocument();
      expect(screen.getByText('Overhead')).toBeInTheDocument();
    });
  });

  it('should handle missing components gracefully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        cpu_name: null,
        gpu_name: null,
        ram_name: null,
        ssd_name: null,
        psu_name: null,
        case_name: null,
        cooler_name: null,
        parts_cost_total: 0,
        labor_cost: 0,
        overhead_cost: 0,
        total_price: 0,
      }),
    });

    const { container } = render(<OrderSummary />);
    expect(container).toBeInTheDocument();
  });

  it('should handle API errors gracefully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });

    render(<OrderSummary />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to generate quote/)).toBeInTheDocument();
    });
  });
});

describe('OS Store (Zustand)', () => {
  it('should initialize with null values', () => {
    const { result } = renderHook(() => useOSStore());
    expect(result.current.selectedOS).toBeNull();
    expect(result.current.selectedLicense).toBeNull();
    expect(result.current.selectedTheme).toBeNull();
  });

  it('should set OS and clear license', () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setLicense({
        id: 1,
        key: 'XXXXX',
        available: true,
      });
    });

    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
    });

    expect(result.current.selectedOS).toEqual({
      id: 1,
      name: 'Windows 11',
      price: 150,
    });
    expect(result.current.selectedLicense).toBeNull();
  });

  it('should set theme independently', () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setTheme({
        id: 1,
        name: 'Cyberpunk Blue',
        category: 'Gaming',
        preview_image_url: '/images/theme1.png',
        widgets_included: 'Clock, Weather',
      });
    });

    expect(result.current.selectedTheme).toEqual({
      id: 1,
      name: 'Cyberpunk Blue',
      category: 'Gaming',
      preview_image_url: '/images/theme1.png',
      widgets_included: 'Clock, Weather',
    });
  });

  it('should reset all selections', () => {
    const { result } = renderHook(() => useOSStore());
    act(() => {
      result.current.setOS({ id: 1, name: 'Windows 11', price: 150 });
      result.current.setLicense({
        id: 1,
        key: 'XXXXX',
        available: true,
      });
      result.current.setTheme({
        id: 1,
        name: 'Cyberpunk Blue',
        category: 'Gaming',
        preview_image_url: '/images/theme1.png',
        widgets_included: 'Clock, Weather',
      });
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.selectedOS).toBeNull();
    expect(result.current.selectedLicense).toBeNull();
    expect(result.current.selectedTheme).toBeNull();
  });
});
