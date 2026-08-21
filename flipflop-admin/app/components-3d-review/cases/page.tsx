'use client';

import React from 'react';
import { TwinklingStars } from './components/TwinklingStars';
import { PCCasesGallery } from './components/PCCasesGallery';

export default function PCCasesReviewPage() {
  return (
    <div className="relative min-h-screen bg-black">
      {/* Twinkling stars background - fixed positioned so sidebar shows on top */}
      <TwinklingStars />

      {/* Main content - positioned above stars with sidebar visible */}
      <div className="relative z-20">
        <PCCasesGallery />
      </div>
    </div>
  );
}
