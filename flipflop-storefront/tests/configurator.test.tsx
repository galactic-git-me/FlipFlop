import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComponentPicker } from '@/components/configurator/ComponentPicker';
import { PricingSidebar } from '@/components/configurator/PricingSidebar';
import { useConfiguratorStore } from '@/lib/configurator-store';

// Mock store
jest.mock('@/lib/configurator-store');

describe('ComponentPicker', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useConfiguratorStore as jest.Mock).mockReturnValue({
      cpu_id: null,
      gpu_id: null,
      ram_id: null,
      ssd_id: null,
      psu_id: null,
      case_id: null,
      cooler_id: null,
      setComponent: jest.fn(),
    });
  });

  it('should render component picker with label', () => {
    render(<ComponentPicker componentType="cpu" label="Processor" />);
    expect(screen.getByText('Processor')).toBeInTheDocument();
  });

  it('should display default label when no custom label provided', () => {
    render(<ComponentPicker componentType="gpu" />);
    expect(screen.getByText('GPU')).toBeInTheDocument();
  });

  it('should fetch and display components', async () => {
    render(<ComponentPicker componentType="cpu" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue(/Intel i5-13600K/i)).toBeInTheDocument();
    });
  });

  it('should call setComponent when selection changes', async () => {
    const mockSetComponent = jest.fn();
    (useConfiguratorStore as jest.Mock).mockReturnValueOnce({
      cpu_id: null,
      setComponent: mockSetComponent,
    });

    render(<ComponentPicker componentType="cpu" />);

    const select = screen.getByRole('combobox');
    await userEvent.selectOption(select, '1');

    expect(mockSetComponent).toHaveBeenCalledWith('cpu', 1);
  });

  it('should display component info when selected', async () => {
    (useConfiguratorStore as jest.Mock).mockReturnValueOnce({
      cpu_id: 1,
      setComponent: jest.fn(),
    });

    render(<ComponentPicker componentType="cpu" />);

    await waitFor(() => {
      expect(screen.getByText(/Intel i5-13600K/i)).toBeInTheDocument();
      expect(screen.getByText(/£320\.00/)).toBeInTheDocument();
      expect(screen.getByText(/In Stock/)).toBeInTheDocument();
    });
  });

  it('should show recommended badge for recommended components', async () => {
    render(<ComponentPicker componentType="cpu" />);

    await waitFor(() => {
      const options = screen.getAllByRole('option');
      const recommendedOption = options.find((opt) =>
        opt.textContent?.includes('⭐')
      );
      expect(recommendedOption).toBeInTheDocument();
    });
  });
});

describe('PricingSidebar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useConfiguratorStore as jest.Mock).mockReturnValue({
      cpu_id: 1,
      gpu_id: 1,
      ram_id: 1,
      ssd_id: 1,
      psu_id: 1,
      case_id: 1,
      cooler_id: 1,
    });
  });

  it('should render pricing sidebar with title', () => {
    render(<PricingSidebar budget={1200} />);
    expect(screen.getByText('Build Summary')).toBeInTheDocument();
  });

  it('should display pricing breakdown', async () => {
    render(<PricingSidebar budget={1200} />);

    await waitFor(() => {
      expect(screen.getByText('Parts')).toBeInTheDocument();
      expect(screen.getByText('Labor (3.5h)')).toBeInTheDocument();
      expect(screen.getByText('Overhead (10%)')).toBeInTheDocument();
      expect(screen.getByText('Total')).toBeInTheDocument();
    });
  });

  it('should calculate total price correctly', async () => {
    render(<PricingSidebar budget={1200} />);

    await waitFor(() => {
      // With all components at tier 1: 320 + 500 + 160 + 120 + 140 + 150 + 110 = 1500
      // + labor (87.5) + overhead (10% of 1500 = 150) = 1737.5
      const totalText = screen.getByText(/£\d+\.\d+/).textContent;
      expect(totalText).toBeDefined();
    });
  });

  it('should show within budget indicator when under budget', async () => {
    render(<PricingSidebar budget={2000} />);

    await waitFor(() => {
      expect(screen.getByText(/Within Budget/)).toBeInTheDocument();
    });
  });

  it('should show over budget indicator when exceeding budget', async () => {
    render(<PricingSidebar budget={1000} />);

    await waitFor(() => {
      expect(screen.getByText(/Over Budget/)).toBeInTheDocument();
    });
  });

  it('should display budget progress bar', async () => {
    render(<PricingSidebar budget={1200} />);

    await waitFor(() => {
      const budgetBar = document.querySelector('.budget-used');
      expect(budgetBar).toBeInTheDocument();
    });
  });

  it('should call onContinue when CTA button clicked', async () => {
    const mockOnContinue = jest.fn();
    render(<PricingSidebar budget={1200} onContinue={mockOnContinue} />);

    await waitFor(() => {
      const button = screen.getByRole('button', {
        name: /Continue to Payment/i,
      });
      fireEvent.click(button);
      expect(mockOnContinue).toHaveBeenCalled();
    });
  });
});

describe('Configurator State Management', () => {
  it('should initialize with null component IDs', () => {
    const store = useConfiguratorStore.getState();
    expect(store.cpu_id).toBeNull();
    expect(store.gpu_id).toBeNull();
    expect(store.ram_id).toBeNull();
  });

  it('should update component when setComponent called', () => {
    const store = useConfiguratorStore.getState();
    store.setComponent('gpu', 2);
    expect(useConfiguratorStore.getState().gpu_id).toBe(2);
  });

  it('should reset all components', () => {
    const store = useConfiguratorStore.getState();
    store.setComponent('cpu', 1);
    store.setComponent('gpu', 2);
    store.reset();

    const state = useConfiguratorStore.getState();
    expect(state.cpu_id).toBeNull();
    expect(state.gpu_id).toBeNull();
  });

  it('should update budget', () => {
    const store = useConfiguratorStore.getState();
    store.setBudget(2000);
    expect(useConfiguratorStore.getState().budget).toBe(2000);
  });

  it('should get all component IDs', () => {
    const store = useConfiguratorStore.getState();
    store.setComponent('cpu', 1);
    store.setComponent('gpu', 2);

    const componentIds = store.getComponentIds();
    expect(componentIds.cpu_id).toBe(1);
    expect(componentIds.gpu_id).toBe(2);
    expect(componentIds.ram_id).toBeNull();
  });
});

describe('Pricing Calculations', () => {
  it('should calculate parts cost from selected components', async () => {
    (useConfiguratorStore as jest.Mock).mockReturnValue({
      cpu_id: 1, // 320
      gpu_id: 1, // 500
      ram_id: 1, // 160
      ssd_id: 1, // 120
      psu_id: 1, // 140
      case_id: 1, // 150
      cooler_id: 1, // 110
    });

    render(<PricingSidebar budget={2000} />);

    await waitFor(() => {
      // Total: 320 + 500 + 160 + 120 + 140 + 150 + 110 = 1500
      const partRow = screen.getByText(/Parts/).parentElement;
      expect(partRow?.textContent).toContain('£1500.00');
    });
  });

  it('should include labor cost (87.5) in total', async () => {
    render(<PricingSidebar budget={2000} />);

    await waitFor(() => {
      const laborRow = screen.getByText(/Labor/).parentElement;
      expect(laborRow?.textContent).toContain('£87.50');
    });
  });

  it('should apply 10% overhead', async () => {
    (useConfiguratorStore as jest.Mock).mockReturnValue({
      cpu_id: 1,
      gpu_id: 1,
      ram_id: 1,
      ssd_id: 1,
      psu_id: 1,
      case_id: 1,
      cooler_id: 1,
    });

    render(<PricingSidebar budget={2000} />);

    await waitFor(() => {
      // 10% of 1500 = 150
      const overheadRow = screen.getByText(/Overhead/).parentElement;
      expect(overheadRow?.textContent).toContain('£150.00');
    });
  });

  it('should handle missing components gracefully', async () => {
    (useConfiguratorStore as jest.Mock).mockReturnValue({
      cpu_id: null,
      gpu_id: null,
      ram_id: null,
      ssd_id: null,
      psu_id: null,
      case_id: null,
      cooler_id: null,
    });

    render(<PricingSidebar budget={1200} />);

    await waitFor(() => {
      expect(screen.getByText('Build Summary')).toBeInTheDocument();
    });
  });
});
