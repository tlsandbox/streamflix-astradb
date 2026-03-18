import React, { useEffect, useMemo, useState } from 'react';
import RailRow from './components/RailRow';
import SearchPanel from './components/SearchPanel';
import { DEFAULT_PROFILE, getHome, getRecommendations, postSessionEvent, searchShows } from './lib/api';

export default function App() {
  const profileId = DEFAULT_PROFILE;
  const [home, setHome] = useState({ profile_id: profileId, rails: [] });
  const [recommendations, setRecommendations] = useState({ basis: '', items: [] });
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedSearchItem, setSelectedSearchItem] = useState(null);
  const [loadingHome, setLoadingHome] = useState(true);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [error, setError] = useState('');

  const heroShow = useMemo(() => {
    for (const rail of home.rails || []) {
      if (rail.items?.length) return rail.items[0];
    }
    return null;
  }, [home]);

  async function loadHome() {
    setLoadingHome(true);
    setError('');
    try {
      const payload = await getHome(profileId);
      setHome(payload);
    } catch (err) {
      setError(err.message || 'Failed to load homepage data.');
    } finally {
      setLoadingHome(false);
    }
  }

  async function loadRecommendations() {
    try {
      const payload = await getRecommendations(profileId);
      setRecommendations(payload);
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    loadHome();
    loadRecommendations();
  }, []);

  useEffect(() => {
    const timeout = setTimeout(async () => {
      if (!query.trim()) {
        setSearchResults([]);
        setSelectedSearchItem(null);
        return;
      }
      setLoadingSearch(true);
      try {
        const payload = await searchShows(query.trim());
        const nextResults = payload.results || [];
        setSearchResults(nextResults);
        setSelectedSearchItem(nextResults[0] || null);
      } catch (err) {
        setError(err.message || 'Search failed');
      } finally {
        setLoadingSearch(false);
      }
    }, 320);

    return () => clearTimeout(timeout);
  }, [query]);

  async function handleWatch(show) {
    try {
      await postSessionEvent({
        profile_id: profileId,
        show_id: show.show_id,
        event_type: 'progress',
        progress_seconds: show.progress_seconds ? show.progress_seconds + 180 : 180,
        device_type: 'web',
        locale: 'en-US',
      });
      await Promise.all([loadHome(), loadRecommendations()]);
    } catch (err) {
      setError(err.message || 'Could not write session event.');
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-backdrop" style={{ backgroundImage: `url(${heroShow?.poster_url || ''})` }} />
        <div className="hero-content">
          <p className="eyebrow">Astra DB Workshop</p>
          <h1>StreamFlix</h1>
          <p>
            Netflix-inspired homepage powered by Astra collections, Astra tables, and vector search.
          </p>
          {heroShow ? (
            <button className="hero-cta" onClick={() => handleWatch(heroShow)} type="button">
              Resume {heroShow.title}
            </button>
          ) : null}
        </div>
      </header>

      <main>
        <SearchPanel
          query={query}
          onChange={setQuery}
          results={searchResults}
          selected={selectedSearchItem}
          onSelect={setSelectedSearchItem}
          loading={loadingSearch}
          onWatch={handleWatch}
        />

        {recommendations.items?.length ? (
          <RailRow
            rail={{
              rail_id: 'because_you_watched',
              title: `Because You Watched (${recommendations.basis.slice(0, 48)}...)`,
              items: recommendations.items,
            }}
            onWatch={handleWatch}
          />
        ) : null}

        {loadingHome ? <p className="status">Loading homepage rails...</p> : null}
        {!loadingHome && !home.rails?.length ? <p className="status">No rails found for this profile yet.</p> : null}
        {(home.rails || []).map((rail) => (
          <RailRow key={rail.rail_id} rail={rail} onWatch={handleWatch} />
        ))}
      </main>

      {error ? <aside className="error-banner">{error}</aside> : null}
    </div>
  );
}
