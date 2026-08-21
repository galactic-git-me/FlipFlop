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
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedStatus, setSelectedStatus] = useState<'all' | 'has-model' | 'reference-only' | 'pending'>('all');
  const [selectedFormFactor, setSelectedFormFactor] = useState<'all' | string>('all');
  const [sortBy, setSortBy] = useState<'rating' | 'reviews' | 'price' | 'name'>('reviews');
  const [selectedCase, setSelectedCase] = useState<PCCase | null>(null);

  // Fetch cases from API on mount
  useEffect(() => {
    const fetchCases = async () => {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:18000/api/cases/gallery?limit=50&sort_by=${sortBy}`);
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const data = await response.json();
        setCases(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch cases:', err);
        setError(err instanceof Error ? err.message : 'Failed to load cases');
      } finally {
        setLoading(false);
      }
    };

    fetchCases();
  }, [sortBy]);

  const filteredAndSorted = useMemo(() => {
    let filtered = cases;

    if (selectedStatus !== 'all') {
      filtered = filtered.filter((c) => c.status === selectedStatus);
    }

    if (selectedFormFactor !== 'all') {
      filtered = filtered.filter((c) => c.form_factors?.includes(selectedFormFactor));
    }

    return filtered;
  }, [cases, selectedStatus, selectedFormFactor]);

  const statusCounts = {
    'has-model': cases.filter((c) => c.status === 'has-model').length,
    'reference-only': cases.filter((c) => c.status === 'reference-only').length,
    'pending': cases.filter((c) => c.status === 'pending').length,
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

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="text-center py-20">
          <div className="text-gray-400 mb-4">Loading cases...</div>
          <div className="inline-block animate-spin">⏳</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="text-center py-20">
          <div className="text-red-400 mb-4">Error loading cases</div>
          <div className="text-sm text-gray-400">{error}</div>
        </div>
      </div>
    );
  }

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
          <div className="text-3xl font-bold text-white">{cases.length}</div>
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
              <div>★ {pcCase.rating?.toFixed(1) || 'N/A'}</div>
              <div>{(pcCase.review_count || 0).toLocaleString()} reviews</div>
            </div>
            {pcCase.price > 0 && <div className="text-sm font-semibold text-white">£{pcCase.price.toFixed(2)}</div>}
            <div className="flex flex-wrap gap-1 mt-2">
              {(pcCase.keywords || []).slice(0, 2).map((tag) => (
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
                  <div className="text-xs text-gray-400 mb-1">Rating</div>
                  <div className="font-semibold text-white">★ {selectedCase.rating?.toFixed(1) || 'N/A'}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Reviews</div>
                  <div className="font-semibold text-white">{(selectedCase.review_count || 0).toLocaleString()}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Price</div>
                  <div className="font-semibold text-white">£{selectedCase.price?.toFixed(2) || 'N/A'}</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded p-3">
                  <div className="text-xs text-gray-400 mb-1">Source</div>
                  <div className="font-semibold text-white capitalize">{selectedCase.brand}</div>
                </div>
              </div>

              {/* Admin Controls */}
              <div className="border-t border-white/10 pt-4 mt-4">
                <div className="flex gap-2">
                  <button className="flex-1 bg-blue-600/20 border border-blue-500/50 text-blue-300 px-4 py-2 rounded text-sm hover:bg-blue-600/30 transition">
                    📤 Upload Model
                  </button>
                  <button className="flex-1 bg-purple-600/20 border border-purple-500/50 text-purple-300 px-4 py-2 rounded text-sm hover:bg-purple-600/30 transition">
                    📎 Manage References
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
