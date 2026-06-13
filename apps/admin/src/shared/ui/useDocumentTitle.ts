import { useEffect } from 'react';

/** Ставит <title> на роут (как в дизайн-контракте: «DiffDuel Admin — …»). */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    const prev = document.title;
    document.title = `DiffDuel Admin — ${title}`;
    return () => {
      document.title = prev;
    };
  }, [title]);
}
