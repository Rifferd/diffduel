import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { AdminTask, AdminTaskList, TaskStatus } from '@diffduel/contracts';
import { adminTasksApi, type AdminTasksParams } from '@/shared/api/endpoints';

export const TASKS_PAGE_SIZE = 20;

export function tasksQueryKey(params: AdminTasksParams): unknown[] {
  return ['admin', 'tasks', params];
}

export function useTasksQuery(params: AdminTasksParams): UseQueryResult<AdminTaskList> {
  return useQuery({
    queryKey: tasksQueryKey(params),
    queryFn: () => adminTasksApi.list(params),
    placeholderData: (prev) => prev,
  });
}

type StatusAction = 'publish' | 'reject';

/**
 * Оптимистично меняет статус задачи в кэше текущего списка,
 * затем инвалидирует, чтобы подтянуть авторитетные данные сервера.
 */
export function useTaskStatusMutation(
  params: AdminTasksParams,
): UseMutationResult<AdminTask, unknown, { id: string; action: StatusAction }, { prev?: AdminTaskList }> {
  const queryClient = useQueryClient();
  const key = tasksQueryKey(params);

  return useMutation({
    mutationFn: ({ id, action }) =>
      action === 'publish' ? adminTasksApi.publish(id) : adminTasksApi.reject(id),
    onMutate: async ({ id, action }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const prev = queryClient.getQueryData<AdminTaskList>(key);
      if (prev) {
        const nextStatus: TaskStatus = action === 'publish' ? 'published' : 'draft';
        queryClient.setQueryData<AdminTaskList>(key, {
          ...prev,
          items: prev.items.map((t) => (t.id === id ? { ...t, status: nextStatus } : t)),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, context) => {
      if (context?.prev) queryClient.setQueryData(key, context.prev);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] });
    },
  });
}
