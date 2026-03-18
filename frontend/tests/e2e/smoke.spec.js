import { test, expect } from '@playwright/test';

const shows = [
  {
    show_id: 'show_1',
    title: 'Signal City',
    poster_url: 'https://static.tvmaze.com/uploads/images/medium_portrait/81/202627.jpg',
    synopsis: 'A gritty urban thriller.',
    genres: ['Drama'],
    year: 2020,
    rating: 8.1,
    network: 'HBO',
    runtime: 52,
    language: 'English',
    status: 'Running',
    premiered_date: '2020-03-15',
    tags: ['drama', 'trending'],
    creator_names: ['Ava Writer'],
    director_names: [],
    cast_names: ['Actor A', 'Actor B'],
  },
  {
    show_id: 'show_2',
    title: 'Neon Void',
    poster_url: 'https://static.tvmaze.com/uploads/images/medium_portrait/200/501942.jpg',
    synopsis: 'Sci-fi mystery in deep space.',
    genres: ['Science-Fiction'],
    year: 2022,
    rating: 8.4,
    network: 'Netflix',
    runtime: 48,
    language: 'English',
    status: 'Ended',
    premiered_date: '2022-09-01',
    tags: ['sci_fi', 'thriller'],
    creator_names: ['Noah Future'],
    director_names: ['Mina Lens'],
    cast_names: ['Actor X', 'Actor Y', 'Actor Z'],
  },
  {
    show_id: 'show_3',
    title: 'Silent Echo',
    poster_url: 'https://static.tvmaze.com/uploads/images/medium_portrait/1/4388.jpg',
    synopsis: 'A quiet anthology of unresolved mysteries.',
    genres: ['Mystery'],
    year: 2018,
    rating: null,
    network: null,
    runtime: null,
    language: null,
    status: null,
    premiered_date: null,
    tags: [],
    creator_names: [],
    director_names: [],
    cast_names: [],
  },
];

test('renders rails and semantic search', async ({ page }) => {
  await page.route('**/api/home**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        profile_id: 'profile_alex',
        rails: [{ rail_id: 'trending', title: 'Trending Now', items: shows }],
      }),
    });
  });

  await page.route('**/api/recommendations**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ profile_id: 'profile_alex', basis: 'demo', items: [shows[1]] }),
    });
  });

  await page.route('**/api/search**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ query: 'space', total: 3, results: [shows[0], shows[1], shows[2]] }),
    });
  });

  await page.route('**/api/session/events', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', continue_watching_updated: true }),
    });
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'StreamFlix' })).toBeVisible();
  await expect(page.getByText('Trending Now')).toBeVisible();
  await expect(page.getByRole('button', { name: /Signal City poster/i })).toBeVisible();

  await page.getByLabel('Semantic Search').fill('space prison');
  await expect(page.getByTestId('search-featured-title')).toHaveText('Signal City');
  await page.getByTestId('search-strip-card-show_2').click();
  await expect(page.getByTestId('search-featured-title')).toHaveText('Neon Void');
  await expect(page.getByText('Noah Future')).toBeVisible();
  await page.getByTestId('search-strip-card-show_3').click();
  await expect(page.getByTestId('search-featured-title')).toHaveText('Silent Echo');
  await expect(page.getByText('Network:')).toHaveCount(0);
  await expect(page.getByText('Creators')).toHaveCount(0);
});
