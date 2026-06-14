import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import type { TopicPublic, TournamentSummary } from '@diffduel/contracts';
import TournamentsPage from './TournamentsPage.vue';
import { tournamentsApi, topicsApi } from '@/shared/api/endpoints';

vi.mock('vue-router', () => ({
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}));

vi.mock('@/components/AppNav.vue', () => ({ default: { template: '<nav />' } }));
vi.mock('@/components/TabBar.vue', () => ({ default: { template: '<nav />' } }));

const TOPIC: TopicPublic = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'sql',
  title: 'SQL',
};

function makeTournament(over: Partial<TournamentSummary> = {}): TournamentSummary {
  return {
    id: '22222222-2222-2222-2222-222222222222',
    title: 'Пятничный блиц',
    topic_id: TOPIC.id,
    starts_at: '2026-06-20T19:00:00Z',
    ends_at: null,
    entry_fee: '0',
    prize_pool: '10000',
    status: 'active',
    entries_count: 128,
    ...over,
  };
}

describe('TournamentsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('рендерит список турниров из мок-API с темой и фондом', async () => {
    vi.spyOn(tournamentsApi, 'list').mockResolvedValue([makeTournament()]);
    vi.spyOn(topicsApi, 'list').mockResolvedValue([TOPIC]);

    const wrapper = mount(TournamentsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('Пятничный блиц');
    expect(wrapper.text()).toContain('SQL');
    expect(wrapper.text()).toContain('live');
    expect(wrapper.text()).toContain('128');
    // CTA для active -> «Смотреть сетку» и ссылка на детали.
    expect(wrapper.text()).toContain('Смотреть сетку');
    expect(wrapper.find('a[href="/tournaments/22222222-2222-2222-2222-222222222222"]').exists()).toBe(
      true,
    );
  });

  it('показывает пустое состояние, когда турниров нет', async () => {
    vi.spyOn(tournamentsApi, 'list').mockResolvedValue([]);
    vi.spyOn(topicsApi, 'list').mockResolvedValue([TOPIC]);

    const wrapper = mount(TournamentsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('Пока без турниров');
  });

  it('показывает ошибку при сбое загрузки', async () => {
    vi.spyOn(tournamentsApi, 'list').mockRejectedValue(new Error('boom'));
    vi.spyOn(topicsApi, 'list').mockResolvedValue([TOPIC]);

    const wrapper = mount(TournamentsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('Не удалось загрузить турниры');
  });
});
