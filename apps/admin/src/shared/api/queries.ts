import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import type { TopicPublic } from '@diffduel/contracts';
import { topicsApi } from './endpoints';

/** Темы редко меняются — кэшируем надолго; нужны для фильтров и редактора. */
export function useTopics(): UseQueryResult<TopicPublic[]> {
  return useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
    staleTime: 5 * 60_000,
  });
}
