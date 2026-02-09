'use client';

import { useState } from 'react';

export default function Home() {
  const [url, setUrl] = useState('');
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSummarize = async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    setSummary(null);

    try {
      const res = await fetch('/api/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!res.ok) {
        throw new Error('Failed to fetch summary');
      }

      const data = await res.json();
      setSummary(data.summary);
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8 font-sans">
      <main className="w-full max-w-2xl flex flex-col items-center gap-8">
        <h1 className="text-4xl font-bold tracking-tight text-gray-800">Vibe Digest</h1>

        <div className="w-full bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div className="flex flex-col gap-4">
            <input
              type="url"
              placeholder="Paste URL here..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full p-4 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-300 transition"
            />
            <button
              onClick={handleSummarize}
              disabled={loading || !url}
              className="w-full py-3 bg-black text-white rounded-xl font-medium hover:bg-gray-800 transition disabled:opacity-50 flex justify-center items-center"
            >
              {loading ? (
                <span className="animate-pulse">Summarizing...</span>
              ) : (
                'Summarize'
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="text-red-500 bg-red-50 p-4 rounded-xl w-full text-center">
            {error}
          </div>
        )}

        {summary && (
          <div className="w-full bg-white p-8 rounded-2xl shadow-sm border border-gray-100 text-left">
            <div className="prose prose-gray max-w-none whitespace-pre-wrap">
              {summary}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
