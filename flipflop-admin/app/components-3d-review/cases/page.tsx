'use client';

import React from 'react';
import { TwinklingStars } from './components/TwinklingStars';
import { PCCasesGallery } from './components/PCCasesGallery';

export default function PCCasesReviewPage() {
  return (
    <div className="relative w-full h-full flex flex-col">
      {/* Twinkling stars background - fixed positioning outside flex flow */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <TwinklingStars />
      </div>

      {/* Main content with higher z-index */}
      <div className="relative z-10 flex-1 w-full overflow-hidden">
        <PCCasesGallery />
      </div>
    </div>
  );
}
