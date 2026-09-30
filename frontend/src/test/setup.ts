import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

export interface MediaQueryStub {
  matches: boolean;
}

/** jsdom has no matchMedia: default to the desktop (>= 768 px) case. */
export function setViewportMatches(isNarrow: boolean): void {
  const listeners = new Set<() => void>();
  const impl = (query: string): MediaQueryList =>
    ({
      matches: isNarrow,
      media: query,
      onchange: null,
      addEventListener: (_: string, cb: EventListener) => listeners.add(cb as () => void),
      removeEventListener: (_: string, cb: EventListener) => listeners.delete(cb as () => void),
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;

  Object.defineProperty(globalThis, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn(impl),
  });
}

setViewportMatches(false);

afterEach(() => {
  cleanup();
  globalThis.localStorage.clear();
  setViewportMatches(false);
});
