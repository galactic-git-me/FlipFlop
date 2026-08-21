'use client';

import React, { useState } from 'react';
import { TwinklingStars } from './components/TwinklingStars';
import { PCCasesGallery } from './components/PCCasesGallery';

export default function PCCasesReviewPage() {
  return (
    <div className="relative w-full min-h-screen bg-black overflow-hidden">
      {/* Twinkling stars background */}
      <TwinklingStars />

      {/* Main content - positioned above stars */}
      <div className="relative z-10">
        <PCCasesGallery />
      </div>
    </div>
  );
}
