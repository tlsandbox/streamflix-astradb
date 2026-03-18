import React from 'react';

function PosterCard({ item, onWatch }) {
  return (
    <button className="poster-card" onClick={() => onWatch(item)} type="button">
      <img src={item.poster_url} alt={`${item.title} poster`} loading="lazy" />
      <span className="poster-overlay" />
      <span className="poster-meta">
        <strong>{item.title}</strong>
        <small>{item.year || 'N/A'} · {item.genres?.slice(0, 2).join(' / ') || 'Series'}</small>
        <small>{item.network || 'Network N/A'} · {item.rating ? `${item.rating.toFixed(1)} / 10` : 'NR'}</small>
        {item.tags?.length ? <small>{item.tags.slice(0, 2).join(' • ')}</small> : null}
        {item.progress_seconds ? <em>Resume at {Math.round(item.progress_seconds / 60)} min</em> : null}
      </span>
    </button>
  );
}

export default function RailRow({ rail, onWatch }) {
  if (!rail?.items?.length) return null;

  return (
    <section className="rail-row" aria-label={rail.title}>
      <h2>{rail.title}</h2>
      <div className="rail-grid">
        {rail.items.map((item) => (
          <PosterCard key={item.show_id} item={item} onWatch={onWatch} />
        ))}
      </div>
    </section>
  );
}
