'use client';

import React from 'react';
import { TwinklingStars } from './components/TwinklingStars';
import { PCCasesGallery } from './components/PCCasesGallery';

export default function PCCasesReviewPage() {
  return (
    <div className="relative w-full h-full">
      {/* Twinkling stars background */}
      <TwinklingStars />

      {/* Main content with higher z-index */}
      <div className="relative z-20 w-full h-full">
        <PCCasesGallery />
      </div>
    </div>
  );
}
