import { create } from 'zustand';

export interface ConfiguratorState {
  budget: number;
  cpu_id: number | null;
  gpu_id: number | null;
  ram_id: number | null;
  ssd_id: number | null;
  psu_id: number | null;
  case_id: number | null;
  cooler_id: number | null;

  setComponent: (type: string, id: number) => void;
  setBudget: (budget: number) => void;
  reset: () => void;
  getComponentIds: () => Record<string, number | null>;
}

export const useConfiguratorStore = create<ConfiguratorState>((set, get) => ({
  budget: 1200,
  cpu_id: null,
  gpu_id: null,
  ram_id: null,
  ssd_id: null,
  psu_id: null,
  case_id: null,
  cooler_id: null,

  setComponent: (type, id) => {
    set((state) => {
      const componentKey = `${type}_id` as keyof Omit<ConfiguratorState, 'setComponent' | 'setBudget' | 'reset' | 'getComponentIds'>;
      return {
        ...state,
        [componentKey]: id,
      };
    });
  },

  setBudget: (budget) => set({ budget }),

  reset: () =>
    set({
      cpu_id: null,
      gpu_id: null,
      ram_id: null,
      ssd_id: null,
      psu_id: null,
      case_id: null,
      cooler_id: null,
    }),

  getComponentIds: () => {
    const state = get();
    return {
      cpu_id: state.cpu_id,
      gpu_id: state.gpu_id,
      ram_id: state.ram_id,
      ssd_id: state.ssd_id,
      psu_id: state.psu_id,
      case_id: state.case_id,
      cooler_id: state.cooler_id,
    };
  },
}));
