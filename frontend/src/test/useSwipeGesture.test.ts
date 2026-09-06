import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSwipeGesture } from '../hooks/useSwipeGesture';

describe('useSwipeGesture hook', () => {
  it('triggers onSwipeLeft when horizontal swipe distance exceeds minDistance', () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();

    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
        minDistance: 50,
      })
    );

    // Simulate swipe left (touchStart at 200, touchEnd at 100)
    act(() => {
      result.current.onTouchStart({
        touches: [{ clientX: 200, clientY: 100 }],
      } as any);
    });

    act(() => {
      result.current.onTouchEnd({
        changedTouches: [{ clientX: 100, clientY: 105 }],
      } as any);
    });

    expect(onSwipeLeft).toHaveBeenCalledTimes(1);
    expect(onSwipeRight).not.toHaveBeenCalled();
  });

  it('triggers onSwipeRight when horizontal swipe distance exceeds minDistance', () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();

    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
        minDistance: 50,
      })
    );

    // Simulate swipe right (touchStart at 100, touchEnd at 200)
    act(() => {
      result.current.onTouchStart({
        touches: [{ clientX: 100, clientY: 100 }],
      } as any);
    });

    act(() => {
      result.current.onTouchEnd({
        changedTouches: [{ clientX: 200, clientY: 105 }],
      } as any);
    });

    expect(onSwipeRight).toHaveBeenCalledTimes(1);
    expect(onSwipeLeft).not.toHaveBeenCalled();
  });

  it('ignores swipe if vertical movement is dominant (scroll behavior)', () => {
    const onSwipeLeft = vi.fn();
    const onSwipeRight = vi.fn();

    const { result } = renderHook(() =>
      useSwipeGesture({
        onSwipeLeft,
        onSwipeRight,
        minDistance: 50,
        maxPerpendicularDistance: 60,
      })
    );

    // DeltaX = -80, but DeltaY = 120 (user is scrolling vertically)
    act(() => {
      result.current.onTouchStart({
        touches: [{ clientX: 200, clientY: 100 }],
      } as any);
    });

    act(() => {
      result.current.onTouchEnd({
        changedTouches: [{ clientX: 120, clientY: 220 }],
      } as any);
    });

    expect(onSwipeLeft).not.toHaveBeenCalled();
    expect(onSwipeRight).not.toHaveBeenCalled();
  });
});
