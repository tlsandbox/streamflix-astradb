import React from 'react';

function hasValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function joinList(values) {
  if (!values?.length) return '';
  return values.join(', ');
}

export default function SearchPanel({ query, onChange, results, selected, onSelect, loading, onWatch }) {
  const featured = selected || results?.[0] || null;
  const featuredTags = Array.from(new Set([...(featured?.genres || []), ...(featured?.tags || [])])).slice(0, 10);
  const topMeta = [
    hasValue(featured?.year) ? String(featured.year) : null,
    hasValue(featured?.rating) ? `${featured.rating.toFixed(1)} / 10` : null,
    hasValue(featured?.status) ? featured.status : null,
    hasValue(featured?.runtime) ? `${featured.runtime} min` : null,
  ].filter(Boolean);
  const secondaryMeta = [
    hasValue(featured?.network) ? `Network: ${featured.network}` : null,
    hasValue(featured?.language) ? `Language: ${featured.language}` : null,
    hasValue(featured?.premiered_date) ? `Premiered: ${featured.premiered_date}` : null,
  ].filter(Boolean);

  return (
    <section className="search-panel">
      <label htmlFor="semantic-search">Semantic Search</label>
      <input
        id="semantic-search"
        value={query}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Try: gritty prison drama with political twists"
      />
      {loading ? <p>Searching vectors...</p> : null}
      {query && !loading ? <p className="subtle">{results.length} result(s)</p> : null}

      {query && featured ? (
        <article className="search-featured">
          <div className="search-featured-media">
            <img src={featured.poster_url} alt={`${featured.title} poster`} />
          </div>
          <div className="search-featured-content">
            <h3 data-testid="search-featured-title">{featured.title}</h3>
            <p className="search-featured-synopsis">{featured.synopsis}</p>

            {topMeta.length ? (
              <div className="search-meta-row">
                {topMeta.map((item) => <span key={item}>{item}</span>)}
              </div>
            ) : null}

            {featuredTags.length ? (
              <div className="search-chip-row">
                {featuredTags.map((tag) => (
                  <span className="chip" key={tag}>{tag}</span>
                ))}
              </div>
            ) : null}

            <div className="search-meta-block">
              {secondaryMeta.length ? (
                <p className="search-meta-inline">{secondaryMeta.join(' • ')}</p>
              ) : null}
              {featured.creator_names?.length ? <p><strong>Creators</strong> {joinList(featured.creator_names)}</p> : null}
              {featured.director_names?.length ? <p><strong>Directors</strong> {joinList(featured.director_names)}</p> : null}
              {featured.cast_names?.length ? <p><strong>Cast</strong> {joinList((featured.cast_names || []).slice(0, 6))}</p> : null}
            </div>

            <div className="search-featured-actions">
              <button onClick={() => onWatch(featured)} type="button">Watch Now</button>
              {featured.similarity ? (
                <p className="subtle">Semantic match score: {featured.similarity.toFixed(3)}</p>
              ) : null}
            </div>
          </div>
        </article>
      ) : null}

      {query && results.length ? (
        <div className="search-result-strip">
          {results.map((item) => (
            <button
              className={`search-strip-card${featured?.show_id === item.show_id ? ' is-active' : ''}`}
              key={item.show_id}
              type="button"
              data-testid={`search-strip-card-${item.show_id}`}
              onClick={() => onSelect(item)}
              aria-pressed={featured?.show_id === item.show_id}
            >
              <img src={item.poster_url} alt={`${item.title} poster`} />
              <div>
                <strong>{item.title}</strong>
                <small>
                  {[item.year, (item.genres || []).slice(0, 2).join(' / ') || 'Series'].filter(Boolean).join(' · ')}
                </small>
              </div>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
