'use client';

import React, { useState, useMemo, useEffect } from 'react';

interface PCCase {
  id: number;
  name: string;
  brand: string;
  model: string;
  rating: number;
  review_count: number;
  price: number;
  form_factors?: string[];
  keywords?: string[];
  status: 'has-model' | 'reference-only' | 'pending';
  image_url?: string;
  model_3d_url?: string;
  has_3d_model: boolean;
}

export function PCCasesGallery() {
  const [cases, setCases] = useState<PCCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  { id: 2, name: 'CORSAIR FRAME 4000D', brand: 'CORSAIR', model: 'frame-4000d', rating: 4.7, reviewCount: 1803, price: 70.79, tags: 'mid-tower, atx, tempered-glass, airflow', formFactor: 'mid-tower', status: 'has-model' },
  { id: 3, name: 'NZXT H5 Flow', brand: 'NZXT', model: 'h5-flow', rating: 4.6, reviewCount: 1160, price: 49.99, tags: 'micro-atx, compact, airflow', formFactor: 'micro-atx', status: 'has-model' },
  { id: 4, name: 'Phanteks XT Silent', brand: 'Phanteks', model: 'xt-pro', rating: 4.7, reviewCount: 914, price: 119.99, tags: 'mid-tower, atx, silent-design, tempered-glass', formFactor: 'mid-tower', status: 'has-model' },
  { id: 5, name: 'Lian Li LANCOOL 216 RGB', brand: 'Lian Li', model: 'lancool-216', rating: 4.7, reviewCount: 910, price: 89.99, tags: 'mid-tower, atx, airflow, rgb-lighting', formFactor: 'mid-tower', status: 'has-model' },
  { id: 6, name: 'HYTE Y60', brand: 'HYTE', model: 'y60', rating: 4.8, reviewCount: 904, price: 132.56, tags: 'mid-tower, atx, dual-chamber, panoramic-glass', formFactor: 'mid-tower', status: 'has-model' },
  { id: 7, name: 'CORSAIR 3000D RGB', brand: 'CORSAIR', model: '3000d-rgb', rating: 4.5, reviewCount: 806, price: 60.26, tags: 'mid-tower, atx, rgb-lighting, airflow', formFactor: 'mid-tower', status: 'has-model' },
  { id: 8, name: 'MSI MAG FORGE 120A', brand: 'MSI', model: 'mag-forge-120a', rating: 4.6, reviewCount: 786, price: 52.70, tags: 'mid-tower, atx, airflow, tempered-glass', formFactor: 'mid-tower', status: 'has-model' },
  { id: 9, name: 'CORSAIR 3500X', brand: 'CORSAIR', model: '3500x', rating: 4.7, reviewCount: 767, price: 69.99, tags: 'mid-tower, atx, panoramic-glass, airflow', formFactor: 'mid-tower', status: 'has-model' },
  { id: 10, name: 'CiT Flash Gaming', brand: 'CiT', model: 'flash', rating: 4.2, reviewCount: 725, price: 38.60, tags: 'micro-atx, gaming, compact', formFactor: 'micro-atx', status: 'has-model' },
  { id: 11, name: 'Fractal Design Pop Silent', brand: 'Fractal Design', model: 'pop-silent', rating: 4.6, reviewCount: 720, price: 79.99, tags: 'mid-tower, atx, quiet-design, airflow', formFactor: 'mid-tower', status: 'has-model' },
  { id: 12, name: 'NZXT H3 Flow', brand: 'NZXT', model: 'h3-flow', rating: 4.6, reviewCount: 669, price: 49.98, tags: 'micro-atx, compact, airflow', formFactor: 'micro-atx', status: 'has-model' },
  { id: 13, name: 'Mars Gaming MCV4', brand: 'Mars Gaming', model: 'mcv4', rating: 4.5, reviewCount: 582, price: 74.39, tags: 'e-atx, gaming, dual-chamber, frameless', formFactor: 'e-atx', status: 'has-model' },
  { id: 14, name: 'MSI MAG FORGE 112R', brand: 'MSI', model: 'mag-forge-112r', rating: 4.4, reviewCount: 563, price: 49.99, tags: 'mid-tower, multi-form, tempered-glass', formFactor: 'mid-tower', status: 'has-model' },
  { id: 15, name: 'Lian Li A3', brand: 'Lian Li', model: 'a3', rating: 4.7, reviewCount: 513, price: 65.99, tags: 'micro-atx, compact, wood-panel', formFactor: 'micro-atx', status: 'has-model' },
  { id: 16, name: 'Antec C8', brand: 'Antec', model: 'c8', rating: 4.7, reviewCount: 488, price: 103.77, tags: 'e-atx, full-tower, dual-chamber, radiator-support', formFactor: 'e-atx', status: 'has-model' },
  { id: 17, name: 'Lian Li O11D EVO', brand: 'Lian Li', model: 'o11d-evo', rating: 4.7, reviewCount: 469, price: 139.99, tags: 'mid-tower, e-atx, tempered-glass, modular', formFactor: 'mid-tower', status: 'has-model' },
  { id: 18, name: 'NZXT H9 Flow', brand: 'NZXT', model: 'h9-flow', rating: 4.8, reviewCount: 465, price: 99.98, tags: 'mid-tower, atx, dual-chamber, airflow', formFactor: 'mid-tower', status: 'has-model' },
  { id: 19, name: 'Lian Li O11 VISION-M', brand: 'Lian Li', model: 'o11-vision-m', rating: 4.6, reviewCount: 460, price: 99.99, tags: 'micro-atx, dual-chamber, modular', formFactor: 'micro-atx', status: 'reference-only' },
  { id: 20, name: 'ASUS TUF Gaming GT301', brand: 'ASUS', model: 'tuf-gt301', rating: 4.5, reviewCount: 428, price: 87.98, tags: 'mid-tower, atx, gaming, tempered-glass', formFactor: 'mid-tower', status: 'pending' },
  { id: 21, name: 'GAMDIAS ZEUS', brand: 'GAMDIAS', model: 'zeus', rating: 4.3, reviewCount: 412, price: 49.95, tags: 'mid-tower, atx, gaming, tempered-glass', formFactor: 'mid-tower', status: 'pending' },
  { id: 22, name: 'MSI MAG PANO 100R', brand: 'MSI', model: 'mag-pano-100r', rating: 4.8, reviewCount: 390, price: 89.99, tags: 'mid-tower, atx, panoramic-glass, vertical-gpu', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 23, name: 'NZXT H7 Flow RGB', brand: 'NZXT', model: 'h7-flow', rating: 4.7, reviewCount: 380, price: 89.99, tags: 'mid-tower, atx, rgb-lighting, airflow', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 24, name: 'Fractal Design Define 7', brand: 'Fractal Design', model: 'define-7', rating: 4.6, reviewCount: 350, price: 149.99, tags: 'mid-tower, e-atx, quiet-design, modular', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 25, name: 'GAMDIAS TALOS E3', brand: 'GAMDIAS', model: 'talos-e3', rating: 4.4, reviewCount: 340, price: 69.99, tags: 'mid-tower, atx, gaming, mesh-front', formFactor: 'mid-tower', status: 'pending' },
  { id: 26, name: 'Antec C8 White', brand: 'Antec', model: 'c8-white', rating: 4.7, reviewCount: 320, price: 109.99, tags: 'e-atx, full-tower, dual-chamber, no-fans', formFactor: 'e-atx', status: 'reference-only' },
  { id: 27, name: 'Lian Li V100', brand: 'Lian Li', model: 'v100', rating: 4.6, reviewCount: 310, price: 79.99, tags: 'mid-tower, atx, tempered-glass, airflow', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 28, name: 'CiT Jet Stream', brand: 'CiT', model: 'jet-stream', rating: 4.5, reviewCount: 290, price: 45.99, tags: 'mid-tower, atx, office, compact', formFactor: 'mid-tower', status: 'pending' },
  { id: 29, name: 'CORSAIR AIR 5400 RS-R', brand: 'CORSAIR', model: 'air-5400', rating: 4.6, reviewCount: 280, price: 189.99, tags: 'mid-tower, atx, triple-chamber, panoramic-glass', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 30, name: 'be quiet! Pure Base 600', brand: 'be quiet!', model: 'pure-base-600', rating: 4.7, reviewCount: 270, price: 59.99, tags: 'mid-tower, atx, quiet-design, mesh-front', formFactor: 'mid-tower', status: 'has-model' },
  { id: 31, name: 'Lian Li LANCOOL 217', brand: 'Lian Li', model: 'lancool-217', rating: 4.7, reviewCount: 260, price: 85.99, tags: 'mid-tower, atx, tempered-glass, airflow', formFactor: 'mid-tower', status: 'reference-only' },
  { id: 32, name: 'Corsair iCUE 5000D RGB', brand: 'CORSAIR', model: '5000d-rgb', rating: 4.8, reviewCount: 250, price: 129.99, tags: 'mid-tower, atx, rgb-lighting, panoramic-glass', formFactor: 'mid-tower', status: 'has-model' },
];

export function PCCasesGallery() {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedStatus, setSelectedStatus] = useState<'all' | 'has-model' | 'reference-only' | 'pending'>('all');
  const [selectedFormFactor, setSelectedFormFactor] = useState<'all' | string>('all');
  const [sortBy, setSortBy] = useState<'rating' | 'reviews' | 'price' | 'name'>('reviews');
  const [selectedCase, setSelectedCase] = useState<PCCase | null>(null);

  const filteredAndSorted = useMemo(() => {
    let filtered = MOCK_CASES;

    if (selectedStatus !== 'all') {
      filtered = filtered.filter((c) => c.status === selectedStatus);
    }

    if (selectedFormFactor !== 'all') {
      filtered = filtered.filter((c) => c.formFactor === selectedFormFactor);
    }

    const sorted = [...filtered];

    // Always sort: 3D models first, then by selected sort criteria
    sorted.sort((a, b) => {
      // First: prioritize cases with 3D models
      if (a.status === 'has-model' && b.status !== 'has-model') return -1;
      if (a.status !== 'has-model' && b.status === 'has-model') return 1;

      // Then: apply sort preference within each group
      if (sortBy === 'rating') return b.rating - a.rating;
      if (sortBy === 'reviews') return b.reviewCount - a.reviewCount;
      if (sortBy === 'price') return (a.price || 999999) - (b.price || 999999);
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      return 0;
    });

    return sorted;
  }, [selectedStatus, selectedFormFactor, sortBy]);

  const statusCounts = {
    'has-model': MOCK_CASES.filter((c) => c.status === 'has-model').length,
    'reference-only': MOCK_CASES.filter((c) => c.status === 'reference-only').length,
    'pending': MOCK_CASES.filter((c) => c.status === 'pending').length,
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'has-model':
        return <span className="px-3 py-1 bg-green-900/50 text-green-400 rounded-full text-xs">✓ 3D Model</span>;
      case 'reference-only':
        return <span className="px-3 py-1 bg-blue-900/50 text-blue-400 rounded-full text-xs">📋 Reference</span>;
      case 'pending':
        return <span className="px-3 py-1 bg-yellow-900/50 text-yellow-400 rounded-full text-xs">⏳ Pending</span>;
      default:
        return null;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">PC Cases 3D Review Gallery</h1>
          <p className="text-gray-400">Explore 3D models and reference materials for gaming PC cases</p>
        </div>
        <a href="/cases" className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition">
          → View Cases
        </a>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white/5 backdrop-blur border border-white/10 rounded-lg p-4">
          <div className="text-3xl font-bold text-white">{MOCK_CASES.length}</div>
          <div className="text-sm text-gray-400">Total Cases</div>
        </div>
        <div className="bg-green-900/20 backdrop-blur border border-green-500/30 rounded-lg p-4">
          <div className="text-3xl font-bold text-green-400">{statusCounts['has-model']}</div>
          <div className="text-sm text-gray-400">3D Models Ready</div>
        </div>
        <div className="bg-blue-900/20 backdrop-blur border border-blue-500/30 rounded-lg p-4">
          <div className="text-3xl font-bold text-blue-400">{statusCounts['reference-only']}</div>
          <div className="text-sm text-gray-400">Reference Materials</div>
        </div>
        <div className="bg-yellow-900/20 backdrop-blur border border-yellow-500/30 rounded-lg p-4">
          <div className="text-3xl font-bold text-yellow-400">{statusCounts['pending']}</div>
          <div className="text-sm text-gray-400">Pending</div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white/5 backdrop-blur border border-white/10 rounded-lg p-4 mb-8">
        <div className="grid grid-cols-5 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-2">View</label>
            <select value={viewMode} onChange={(e) => setViewMode(e.target.value as 'grid' | 'list')} className="w-full bg-black/50 border border-white/20 text-white px-3 py-2 rounded text-sm">
              <option value="grid">Grid</option>
              <option value="list">List</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-2">Status</label>
            <select value={selectedStatus} onChange={(e) => setSelectedStatus(e.target.value as any)} className="w-full bg-black/50 border border-white/20 text-white px-3 py-2 rounded text-sm">
              <option value="all">All</option>
              <option value="has-model">3D Models</option>
              <option value="reference-only">Reference</option>
              <option value="pending">Pending</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-2">Form Factor</label>
            <select value={selectedFormFactor} onChange={(e) => setSelectedFormFactor(e.target.value)} className="w-full bg-black/50 border border-white/20 text-white px-3 py-2 rounded text-sm">
              <option value="all">All</option>
              <option value="micro-atx">Micro ATX</option>
              <option value="mid-tower">Mid Tower</option>
              <option value="e-atx">E-ATX</option>
              <option value="full-tower">Full Tower</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-2">Sort By</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} className="w-full bg-black/50 border border-white/20 text-white px-3 py-2 rounded text-sm">
              <option value="reviews">Reviews</option>
              <option value="rating">Rating</option>
              <option value="price">Price</option>
              <option value="name">Name</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-2">Results</label>
            <div className="text-2xl font-bold text-white">{filteredAndSorted.length}</div>
          </div>
        </div>
      </div>

      {/* Cases Grid/List */}
      <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4' : 'space-y-3'}>
        {filteredAndSorted.map((pcCase) => (
          <div key={pcCase.id} onClick={() => setSelectedCase(pcCase)} className="relative bg-white/5 backdrop-blur border border-white/10 rounded-lg p-4 hover:bg-white/10 hover:border-white/20 cursor-pointer transition">
            {/* Sparkling 3D badge for models with animation */}
            {pcCase.status === 'has-model' && (
              <div className="absolute top-2 right-2 animate-pulse">
                <div className="relative">
                  <div className="absolute inset-0 bg-blue-400 rounded-full blur-md opacity-50"></div>
                  <span className="relative inline-block px-2 py-1 bg-gradient-to-r from-blue-500 to-cyan-400 text-white text-xs font-bold rounded-full shadow-lg shadow-blue-500/50">✨ 3D</span>
                </div>
              </div>
            )}
            <div className="flex justify-between items-start mb-2">
              <div>
                <h3 className="font-semibold text-white text-sm">{pcCase.name}</h3>
                <p className="text-xs text-gray-400">{pcCase.brand}</p>
              </div>
              {getStatusBadge(pcCase.status)}
            </div>
            <div className="flex items-center justify-between text-xs text-gray-300 mb-2">
              <div>★ {pcCase.rating}</div>
              <div>{pcCase.reviewCount.toLocaleString()} reviews</div>
            </div>
            {pcCase.price > 0 && <div className="text-sm font-semibold text-white">£{pcCase.price.toFixed(2)}</div>}
            <div className="flex flex-wrap gap-1 mt-2">
              {pcCase.tags.split(', ').slice(0, 2).map((tag) => (
                <span key={tag} className="text-xs bg-white/10 text-gray-300 px-2 py-1 rounded">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Detail Modal */}
      {selectedCase && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur flex items-center justify-center z-50 p-4" onClick={() => setSelectedCase(null)}>
          <div className="bg-black/90 border border-white/20 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-black/95 border-b border-white/10 p-6 flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-white">{selectedCase.name}</h2>
                <p className="text-gray-400">{selectedCase.brand} • {selectedCase.model}</p>
              </div>
              <button onClick={() => setSelectedCase(null)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <div className="p-6 space-y-6">
              {/* 3D Viewer or Reference */}
              {selectedCase.status === 'has-model' ? (
                <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 border border-blue-500/30 rounded-lg p-8 h-96 flex flex-col items-center justify-center">
                  <div className="text-center">
                    <div className="text-3xl mb-4">📦</div>
                    <div className="text-blue-300 font-semibold mb-2">3D Model Ready</div>
                    <p className="text-sm text-gray-400 mb-4">{selectedCase.name}</p>
                    <div className="flex gap-2 justify-center text-xs">
                      <span className="px-3 py-1 bg-blue-600/50 text-blue-200 rounded-full">↻ Rotate</span>
                      <span className="px-3 py-1 bg-blue-600/50 text-blue-200 rounded-full">🔍 Zoom</span>
                      <span className="px-3 py-1 bg-blue-600/50 text-blue-200 rounded-full">⬆ Pan</span>
                    </div>
                    <div className="mt-4 text-xs text-gray-500">GLB Model • Sketchfab</div>
                  </div>
                </div>
              ) : (
                <div className="bg-white/5 border border-white/10 rounded-lg p-4">
                  <div className="text-gray-400 mb-2">📸 Reference Materials</div>
                  <p className="text-sm text-gray-500">Product photos and YouTube videos available</p>
                </div>
              )}

              {/* Specs */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Form Factor</div>
                  <div className="font-semibold text-white capitalize">{selectedCase.formFactor}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Rating</div>
                  <div className="font-semibold text-white">★ {selectedCase.rating}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Reviews</div>
                  <div className="font-semibold text-white">{selectedCase.reviewCount.toLocaleString()}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Price</div>
                  <div className="font-semibold text-white">{selectedCase.price > 0 ? `£${selectedCase.price.toFixed(2)}` : 'N/A'}</div>
                </div>
              </div>

              {/* Tags */}
              <div>
                <div className="text-xs text-gray-400 mb-2">Tags</div>
                <div className="flex flex-wrap gap-2">
                  {selectedCase.tags.split(', ').map((tag) => (
                    <span key={tag} className="bg-white/10 text-gray-300 px-3 py-1 rounded-full text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Admin Actions */}
              <div className="border-t border-white/10 pt-4 space-y-2">
                <button className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm">Upload 3D Model</button>
                <button className="w-full bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded text-sm">Manage References</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
