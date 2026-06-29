import { create } from 'zustand';

export interface OSOption {
  id: number;
  name: string;
  price: number;
}

export interface LicenseKey {
  id: number;
  key: string;
  available: boolean;
}

export interface Theme {
  id: number;
  name: string;
  category: string;
  preview_image_url: string;
  widgets_included: string;
  description?: string;
}

interface OSStore {
  selectedOS: OSOption | null;
  selectedLicense: LicenseKey | null;
  selectedTheme: Theme | null;

  setOS: (os: OSOption) => void;
  setLicense: (license: LicenseKey | null) => void;
  setTheme: (theme: Theme) => void;
  reset: () => void;
}

export const useOSStore = create<OSStore>((set) => ({
  selectedOS: null,
  selectedLicense: null,
  selectedTheme: null,

  setOS: (os) => set({ selectedOS: os, selectedLicense: null }),
  setLicense: (license) => set({ selectedLicense: license }),
  setTheme: (theme) => set({ selectedTheme: theme }),

  reset: () =>
    set({
      selectedOS: null,
      selectedLicense: null,
      selectedTheme: null,
    }),
}));
