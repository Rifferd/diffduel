import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type {
  AdminTournament,
  TournamentCreate,
  TournamentStatus,
  TournamentSummary,
  TournamentUpdate,
} from '@diffduel/contracts';
import { adminTournamentsApi } from '@/shared/api/endpoints';

export function tournamentsQueryKey(status?: TournamentStatus): unknown[] {
  return ['admin', 'tournaments', status ?? 'all'];
}

export function useTournamentsQuery(
  status?: TournamentStatus,
): UseQueryResult<TournamentSummary[]> {
  return useQuery({
    queryKey: tournamentsQueryKey(status),
    queryFn: () => adminTournamentsApi.list(status),
    placeholderData: (prev) => prev,
  });
}

export function useCreateTournamentMutation(): UseMutationResult<
  AdminTournament,
  unknown,
  TournamentCreate
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TournamentCreate) => adminTournamentsApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tournaments'] });
    },
  });
}

export function useTournamentStatusMutation(): UseMutationResult<
  AdminTournament,
  unknown,
  { id: string; status: TournamentStatus }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) =>
      adminTournamentsApi.update(id, { status } satisfies TournamentUpdate),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tournaments'] });
    },
  });
}

export function useGrantEntryMutation(): UseMutationResult<
  unknown,
  unknown,
  { id: string; userId: string }
> {
  return useMutation({
    mutationFn: ({ id, userId }) => adminTournamentsApi.grantEntry(id, userId),
  });
}
