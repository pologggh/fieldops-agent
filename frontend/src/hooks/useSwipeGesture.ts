import { useRef, TouchEvent } from 'react';

interface SwipeGestureOptions {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  minDistance?: number;
  maxPerpendicularDistance?: number;
}

export const useSwipeGesture = ({
  onSwipeLeft,
  onSwipeRight,
  minDistance = 50,
  maxPerpendicularDistance = 60,
}: SwipeGestureOptions) => {
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  const onTouchStart = (e: TouchEvent) => {
    if (e.touches.length === 1) {
      touchStartX.current = e.touches[0].clientX;
      touchStartY.current = e.touches[0].clientY;
    }
  };

  const onTouchEnd = (e: TouchEvent) => {
    if (touchStartX.current === null || touchStartY.current === null) return;

    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;

    const deltaX = touchEndX - touchStartX.current;
    const deltaY = touchEndY - touchStartY.current;

    // Reset touch coordinates
    touchStartX.current = null;
    touchStartY.current = null;

    // Verify that horizontal swipe is dominant over vertical scroll
    if (Math.abs(deltaY) > maxPerpendicularDistance) {
      return;
    }

    if (deltaX < -minDistance && onSwipeLeft) {
      onSwipeLeft();
    } else if (deltaX > minDistance && onSwipeRight) {
      onSwipeRight();
    }
  };

  return {
    onTouchStart,
    onTouchEnd,
  };
};
