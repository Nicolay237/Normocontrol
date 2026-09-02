import { ShieldCheck, TriangleAlert } from 'lucide-react';
import { Spinner } from '@/components/spinner';
import { describeWsError } from '../../materials.utils';
import { useNormocontrolRunUpdates, useNormocontrolView } from '../../use-normocontrol';
import { NormocontrolRunList } from './normocontrol-run-list.component';
import { NormocontrolSettingsForm } from './normocontrol-settings-form.component';
import { NormocontrolUploader } from './normocontrol-uploader.component';
import styles from './normocontrol-panel.style.module.css';

export interface NormocontrolPanelProps {
  pageId: string;
  canEdit: boolean;
}

/**
 * Материал нормоконтроля.
 *
 * Проверка советующая: она ничего не запрещает и ни на что не влияет — ни на
 * сдачи, ни на оценки. Это инструмент, которым студент пользуется до того, как
 * понесёт работу преподавателю, и говорить об этом надо прямо: иначе красный
 * список замечаний читается как отказ принять работу.
 */
export function NormocontrolPanel({ pageId, canEdit }: NormocontrolPanelProps) {
  const query = useNormocontrolView(pageId, true);
  const runs = query.data?.runs ?? [];
  useNormocontrolRunUpdates(pageId, runs);

  if (query.isPending) return <Spinner label="Загружаем проверки…" />;
  if (query.isError) return <p className={styles.error}>{describeWsError(query.error)}</p>;
  if (!query.data) return null;

  const { settings, service_available: available, pending } = query.data;
  const closed = !settings.accepting;

  return (
    <section className={styles.panel}>
      <header className={styles.head}>
        <h2 className={styles.title}>
          <ShieldCheck size={16} /> Нормоконтроль
        </h2>
        {canEdit && <NormocontrolSettingsForm pageId={pageId} settings={settings} />}
      </header>

      <p className={styles.intro}>
        Проверка оформления по ГОСТ 7.32-2017. Она <strong>советующая</strong>: на сдачу работы и
        оценку не влияет и ничего не запрещает.
      </p>

      {settings.instructions && <p className={styles.instructions}>{settings.instructions}</p>}

      {!available && (
        <div className={styles.notice}>
          <TriangleAlert size={14} />
          <span>
            <strong>Сервис проверки не подключён</strong>
            <small>Отправить документ сейчас нельзя. Готовые отчёты по-прежнему доступны.</small>
          </span>
        </div>
      )}

      {available && closed && (
        <div className={styles.notice}>
          <TriangleAlert size={14} />
          <span>
            <strong>Приём документов закрыт</strong>
            <small>Преподаватель временно отключил проверку в этом материале.</small>
          </span>
        </div>
      )}

      {available && !closed && (
        <NormocontrolUploader
          pageId={pageId}
          settings={settings}
          pending={pending}
          disabled={false}
        />
      )}

      <NormocontrolRunList
        pageId={pageId}
        runs={runs}
        showAuthors={query.data.reviewing_all ?? false}
      />
    </section>
  );
}
