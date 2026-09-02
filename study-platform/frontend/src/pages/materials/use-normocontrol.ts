import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useWsClient, useWsMutation, useWsQuery } from '@/app/ws';
import { uploadFile } from '@/api/workspace.utils';
import type { WsApiClient } from '@/api/ws/ws-client';

type GeneratedView = Awaited<ReturnType<WsApiClient['actions']['normocontrol']['open']>>;

export type NormocontrolSettings = GeneratedView['settings'];
export type NormocontrolRun = GeneratedView['runs'][number];
export type NormocontrolReport = NonNullable<NormocontrolRun['report']>;
export type NormocontrolCategory = NormocontrolReport['categories'][number];

export type NormocontrolRunStatus =
  'draft' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled';

/** Работа ещё движется сама — за такой стоит следить. */
export function isRunPending(run: NormocontrolRun): boolean {
  return run.status === 'queued' || run.status === 'running';
}

export function normocontrolViewKey(pageId: string) {
  return ['normocontrol', 'open', pageId];
}

/** Условие материала и собственные проверки вызывающего. */
export function useNormocontrolView(pageId: string | undefined, enabled: boolean) {
  return useWsQuery<GeneratedView>(
    normocontrolViewKey(pageId ?? ''),
    async (client) =>
      (await client.actions.normocontrol.open({
        page_id: pageId as string,
      })) as GeneratedView,
    {
      enabled: enabled && Boolean(pageId),
      // Sync is the fast path. A small fallback poll covers a completion event
      // lost during reconnect (and stops as soon as no checks are moving).
      refetchInterval: (query) => (query.state.data?.runs.some(isRunPending) ? 5_000 : false),
    },
  );
}

/**
 * Отправка документа: открыть проверку, загрузить файл, поставить в очередь.
 *
 * Проверка создаётся раньше самого файла не для красоты: `POST /files/upload`
 * привязывает файл в момент загрузки, и цель привязки должна существовать
 * заранее. К странице материала документ привязать нельзя — его прочитал бы
 * любой, у кого есть доступ (см. docs/normocontrol.md).
 */
export function useSubmitNormocontrol(pageId: string) {
  const queryClient = useQueryClient();
  return useWsMutation(
    async (client, file: File) => {
      const run = await client.actions.normocontrol.run.create({ page_id: pageId });
      const uploaded = await uploadFile({
        file,
        // Приведение намеренное: приёмник шире, чем folder/page/test, а тип в
        // сгенерированном клиенте описывает только их.
        resourceType: 'normocontrol_run' as 'page',
        resourceId: run.id,
        behavior: 'download',
      });
      if (!uploaded) throw new Error(`Не удалось загрузить «${file.name}».`);
      return client.actions.normocontrol.run.submit({
        run_id: run.id,
        file_id: uploaded.fileId,
      });
    },
    {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: normocontrolViewKey(pageId) }),
    },
  );
}

export function useCancelNormocontrolRun(pageId: string) {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, runId: string) => client.actions.normocontrol.run.cancel({ run_id: runId }),
    {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: normocontrolViewKey(pageId) }),
    },
  );
}

export function useNormocontrolSettingsMutation(pageId: string) {
  const queryClient = useQueryClient();
  return useWsMutation(
    (client, vars: { instructions: string | null; accepting: boolean }) =>
      client.actions.normocontrol.settings.set({
        page_id: pageId,
        instructions: vars.instructions,
        accepting: vars.accepting,
      }),
    {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: normocontrolViewKey(pageId) }),
    },
  );
}

/**
 * Держит открытыми подписки на незавершённые проверки.
 *
 * Отчёт приезжает событием, а не опросом: проверка идёт секунды и десятки
 * секунд, и дёргать сервер всё это время незачем. Подписка идёт по области
 * конкретной проверки — на странице материала сидят и другие студенты.
 */
export function useNormocontrolRunUpdates(
  pageId: string | undefined,
  runs: readonly NormocontrolRun[],
) {
  const client = useWsClient();
  const queryClient = useQueryClient();
  // Строкой, а не массивом: иначе effect перезаписывался бы на каждый рендер.
  const watched = runs
    .filter(isRunPending)
    .map((run) => run.id)
    .join(',');

  useEffect(() => {
    if (!client || !pageId || !watched) return;
    const unsubscribes = watched.split(',').map((runId) =>
      client.sync.normocontrol.run.changed(runId, () => {
        void queryClient.invalidateQueries({ queryKey: normocontrolViewKey(pageId) });
      }),
    );
    return () => unsubscribes.forEach((stop) => stop());
  }, [client, pageId, watched, queryClient]);
}
