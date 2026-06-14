import { useState } from 'react';
import { useMutation, type UseMutationResult } from '@tanstack/react-query';
import type { ProStatus } from '@diffduel/contracts';
import { adminUsersApi } from '@/shared/api/endpoints';

/**
 * Pro-статус по пользователям в рамках текущей сессии админки.
 *
 * Контракт `AdminUser` (GET /admin/users) не возвращает `is_pro`, а grant/revoke
 * возвращают `ProStatus`. Поэтому колонку «План» наполняем оптимистично:
 * сразу при действии и подтверждаем ответом сервера. Значение `undefined`
 * означает «неизвестно» (до первого действия в этой сессии).
 */
export type ProMap = Record<string, boolean | undefined>;

export interface UseUsersProResult {
  proMap: ProMap;
  grant: UseMutationResult<ProStatus, unknown, { id: string; days: number }, { prev?: boolean }>;
  revoke: UseMutationResult<ProStatus, unknown, { id: string }, { prev?: boolean }>;
}

export function useUsersPro(onError: (err: unknown) => void): UseUsersProResult {
  const [proMap, setProMap] = useState<ProMap>({});

  const setPro = (id: string, value: boolean | undefined): void => {
    setProMap((prev) => ({ ...prev, [id]: value }));
  };

  const grant = useMutation({
    mutationFn: ({ id, days }: { id: string; days: number }) =>
      adminUsersApi.grantPro(id, { days }),
    onMutate: ({ id }) => {
      const prev = proMap[id];
      setPro(id, true); // оптимистично — Pro выдан
      return { prev };
    },
    onSuccess: (status, { id }) => {
      setPro(id, status.is_pro);
    },
    onError: (err, { id }, context) => {
      setPro(id, context?.prev);
      onError(err);
    },
  });

  const revoke = useMutation({
    mutationFn: ({ id }: { id: string }) => adminUsersApi.revokePro(id),
    onMutate: ({ id }) => {
      const prev = proMap[id];
      setPro(id, false); // оптимистично — Pro снят
      return { prev };
    },
    onSuccess: (status, { id }) => {
      setPro(id, status.is_pro);
    },
    onError: (err, { id }, context) => {
      setPro(id, context?.prev);
      onError(err);
    },
  });

  return { proMap, grant, revoke };
}
