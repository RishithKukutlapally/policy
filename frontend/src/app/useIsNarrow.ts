import { useEffect, useState } from 'react';

/** Layout breakpoint shared with the stylesheet (frontend/CLAUDE.md: collapse below 768 px). */
export const NARROW_QUERY = '(max-width: 767.98px)';

function matches(query: string): boolean {
  const mm = globalThis.matchMedia;
  if (typeof mm !== 'function') return false;
  return mm.call(globalThis, query).matches;
}

/** True when the viewport is below the 768 px breakpoint. */
export function useIsNarrow(query: string = NARROW_QUERY): boolean {
  const [isNarrow, setIsNarrow] = useState<boolean>(() => matches(query));

  useEffect(() => {
    const mm = globalThis.matchMedia;
    if (typeof mm !== 'function') return;
    const list = mm.call(globalThis, query);
    const onChange = (): void => setIsNarrow(list.matches);
    onChange();
    if (typeof list.addEventListener === 'function') {
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    }
    globalThis.addEventListener('resize', onChange);
    return () => globalThis.removeEventListener('resize', onChange);
  }, [query]);

  return isNarrow;
}
