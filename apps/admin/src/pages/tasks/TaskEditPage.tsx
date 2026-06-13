import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AdminTask, QuizBody, TaskCreate, TaskUpdate } from '@diffduel/contracts';
import { adminTasksApi } from '@/shared/api/endpoints';
import { useTopics } from '@/shared/api/queries';
import { useToast } from '@/shared/ui/ToastContext';
import { useDocumentTitle } from '@/shared/ui/useDocumentTitle';

interface OptionDraft {
  text: string;
}

interface FormState {
  topicId: string;
  difficulty: number;
  question: string;
  code: string;
  options: OptionDraft[];
  correct: number;
  explanation: string;
}

const EMPTY_FORM: FormState = {
  topicId: '',
  difficulty: 1,
  question: '',
  code: '',
  options: [{ text: '' }, { text: '' }],
  correct: 0,
  explanation: '',
};

function formFromTask(task: AdminTask): FormState {
  const body = task.body as Partial<QuizBody>;
  const answer = task.answer as { correct?: unknown };
  const options = Array.isArray(body.options) ? body.options : [];
  return {
    topicId: task.topic_id,
    difficulty: task.difficulty,
    question: typeof body.question === 'string' ? body.question : '',
    code: typeof body.code === 'string' ? body.code : '',
    options: options.length >= 2 ? options.map((t) => ({ text: t })) : EMPTY_FORM.options,
    correct: typeof answer.correct === 'number' ? answer.correct : 0,
    explanation: task.explanation ?? '',
  };
}

function validate(form: FormState): string | null {
  if (!form.topicId) return 'Выберите тему.';
  if (form.question.trim().length === 0) return 'Заполните вопрос.';
  const filled = form.options.filter((o) => o.text.trim().length > 0);
  if (filled.length < 2) return 'Нужно минимум два непустых варианта.';
  if (form.correct < 0 || form.correct >= form.options.length) return 'Выберите верный вариант.';
  if (form.options[form.correct].text.trim().length === 0) {
    return 'Верный вариант не может быть пустым.';
  }
  return null;
}

export function TaskEditPage(): React.JSX.Element {
  const { taskId } = useParams<{ taskId: string }>();
  const isNew = taskId === undefined;
  useDocumentTitle(isNew ? 'новая задача' : 'редактор задачи');

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { notify, notifyError } = useToast();
  const topics = useTopics();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  // Детального GET нет — для редактирования ищем задачу в кэше уже загруженных
  // списков; если её там нет (прямой заход по ссылке), тянем первую страницу
  // и фильтруем на клиенте.
  const cachedTask = useMemo(() => {
    if (isNew) return undefined;
    const lists = queryClient.getQueriesData<{ items: AdminTask[] }>({
      queryKey: ['admin', 'tasks'],
    });
    for (const [, data] of lists) {
      const found = data?.items.find((t) => t.id === taskId);
      if (found) return found;
    }
    return undefined;
  }, [isNew, queryClient, taskId]);

  const taskQuery = useQuery({
    queryKey: ['admin', 'task-lookup', taskId],
    queryFn: async (): Promise<AdminTask | undefined> => {
      const list = await adminTasksApi.list({ page: 1, pageSize: 100 });
      return list.items.find((t) => t.id === taskId);
    },
    enabled: !isNew && cachedTask === undefined,
  });

  const task = cachedTask ?? taskQuery.data;

  useEffect(() => {
    if (task) setForm(formFromTask(task));
  }, [task]);

  // Тема по умолчанию для новой задачи.
  useEffect(() => {
    if (isNew && !form.topicId && topics.data && topics.data.length > 0) {
      setForm((f) => ({ ...f, topicId: topics.data[0].id }));
    }
  }, [isNew, topics.data, form.topicId]);

  function buildBody(): QuizBody {
    return {
      question: form.question.trim(),
      options: form.options.map((o) => o.text.trim()),
      code: form.code.trim() ? form.code : null,
      tags: [],
    };
  }

  const saveMutation = useMutation({
    mutationFn: async (): Promise<AdminTask> => {
      const body: Record<string, unknown> = { ...buildBody() };
      const answer: Record<string, unknown> = { correct: form.correct };
      if (isNew) {
        const payload: TaskCreate = {
          topic_id: form.topicId,
          difficulty: form.difficulty,
          type: 'quiz',
          body,
          answer,
          explanation: form.explanation.trim() || null,
        };
        return adminTasksApi.create(payload);
      }
      const payload: TaskUpdate = {
        difficulty: form.difficulty,
        body,
        answer,
        explanation: form.explanation.trim() || null,
      };
      return adminTasksApi.update(taskId as string, payload);
    },
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] });
      notify(isNew ? 'Задача создана (draft).' : 'Изменения сохранены.');
      if (isNew) navigate(`/tasks/${task.id}`);
    },
    onError: notifyError,
  });

  const statusMutation = useMutation({
    mutationFn: (action: 'publish' | 'reject') =>
      action === 'publish'
        ? adminTasksApi.publish(taskId as string)
        : adminTasksApi.reject(taskId as string),
    onSuccess: (_task, action) => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] });
      notify(action === 'publish' ? 'Задача опубликована.' : 'Задача отклонена.');
    },
    onError: notifyError,
  });

  function onSave(): void {
    const error = validate(form);
    if (error) {
      notify(error, 'error');
      return;
    }
    saveMutation.mutate();
  }

  function updateOption(index: number, text: string): void {
    setForm((f) => ({
      ...f,
      options: f.options.map((o, i) => (i === index ? { text } : o)),
    }));
  }
  function addOption(): void {
    setForm((f) => ({ ...f, options: [...f.options, { text: '' }] }));
  }
  function removeOption(index: number): void {
    setForm((f) => {
      if (f.options.length <= 2) return f;
      const options = f.options.filter((_, i) => i !== index);
      const correct = f.correct >= options.length ? options.length - 1 : f.correct;
      return { ...f, options, correct };
    });
  }

  useEffect(() => {
    if (taskQuery.isError) notifyError(taskQuery.error);
  }, [taskQuery.isError, taskQuery.error, notifyError]);

  return (
    <>
      <header className="adm__top">
        <div className="crumbs">
          <Link to="/tasks">Задачи</Link>
          <span className="crumbs__sep">/</span>
          <b>{isNew ? 'новая' : `#${(taskId ?? '').slice(0, 8)}`}</b>
        </div>
        <span style={{ flex: 1 }} />
        {!isNew && (
          <>
            <button
              type="button"
              className="btn btn--ghost t-minus"
              style={{ padding: '8px 14px' }}
              disabled={statusMutation.isPending}
              onClick={() => statusMutation.mutate('reject')}
            >
              Отклонить
            </button>
            <button
              type="button"
              className="btn btn--duel"
              style={{ padding: '8px 14px' }}
              disabled={statusMutation.isPending}
              onClick={() => statusMutation.mutate('publish')}
            >
              Опубликовать
            </button>
          </>
        )}
        <button
          type="button"
          className="btn btn--duel"
          style={{ padding: '8px 14px' }}
          disabled={saveMutation.isPending}
          onClick={onSave}
        >
          {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
        </button>
      </header>
      <main className="adm__content">
        <h1 style={{ font: '800 22px var(--font-display)', fontStretch: '110%', marginBottom: 14 }}>
          {isNew ? 'Новая задача' : `Редактор задачи #${(taskId ?? '').slice(0, 8)}`}
        </h1>

        <div className="edit-grid">
          <form className="edit-form" onSubmit={(e) => e.preventDefault()}>
            <div className="row-2">
              <label className="field">
                <span className="field__label">Тема</span>
                <select
                  value={form.topicId}
                  onChange={(e) => setForm((f) => ({ ...f, topicId: e.target.value }))}
                >
                  <option value="" disabled>
                    — выбрать —
                  </option>
                  {(topics.data ?? []).map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Сложность</span>
                <select
                  value={form.difficulty}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, difficulty: Number(e.target.value) }))
                  }
                >
                  {[1, 2, 3, 4, 5].map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span className="field__label">Вопрос</span>
              <input
                type="text"
                value={form.question}
                onChange={(e) => setForm((f) => ({ ...f, question: e.target.value }))}
              />
            </label>

            <label className="field">
              <span className="field__label">Код задачи (необязательно)</span>
              <textarea
                className="mono"
                style={{ minHeight: 120 }}
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              />
            </label>

            <div className="field">
              <span className="field__label">Варианты ответа (выберите верный)</span>
              <div style={{ display: 'grid', gap: 8 }}>
                {form.options.map((opt, index) => (
                  <div key={index} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="radio"
                      name="correct"
                      aria-label={`Верный вариант ${index + 1}`}
                      checked={form.correct === index}
                      onChange={() => setForm((f) => ({ ...f, correct: index }))}
                    />
                    <input
                      type="text"
                      style={{ flex: 1 }}
                      value={opt.text}
                      placeholder={`Вариант ${index + 1}`}
                      onChange={(e) => updateOption(index, e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn--ghost"
                      style={{ padding: '4px 10px' }}
                      disabled={form.options.length <= 2}
                      onClick={() => removeOption(index)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="btn btn--ghost"
                style={{ padding: '6px 12px', marginTop: 8 }}
                onClick={addOption}
              >
                + Вариант
              </button>
            </div>

            <label className="field">
              <span className="field__label">Объяснение</span>
              <textarea
                style={{ minHeight: 80 }}
                value={form.explanation}
                onChange={(e) => setForm((f) => ({ ...f, explanation: e.target.value }))}
              />
            </label>
          </form>

          <div className="preview">
            <div className="preview__label">// превью · как в дуэли</div>
            {form.code.trim() && <pre className="code">{form.code}</pre>}
            <div style={{ marginTop: 12, fontWeight: 600 }}>{form.question || 'Вопрос…'}</div>
            <div className="opts opts--stack" style={{ marginTop: 12 }}>
              {form.options.map((opt, index) => (
                <button
                  key={index}
                  type="button"
                  className={index === form.correct ? 'opt is-correct' : 'opt'}
                >
                  {opt.text || `Вариант ${index + 1}`}
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
