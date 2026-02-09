'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function Home() {
  const [url, setUrl] = useState('');
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSummarize = async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    setSummary(null);
    setCopied(false);

    try {
      const res = await fetch('/api/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!res.ok) {
        const contentType = res.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to fetch summary');
        } else {
          const errText = await res.text();
          throw new Error(`Server Error (${res.status}): ${errText.slice(0, 200)}`);
        }
      }

      const data = await res.json();
      setSummary(data.summary);
    } catch (err: any) {
      setError(err.message || 'An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (summary) {
      navigator.clipboard.writeText(summary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8 font-sans">
      <main className="w-full max-w-2xl flex flex-col items-center gap-8 animate-fade-in">
        <h1 className="text-4xl font-bold tracking-tight text-gray-800">Vibe Digest</h1>

        <div className="w-full glass-card p-6 rounded-2xl">
          <div className="flex flex-col gap-4">
            <input
              type="url"
              placeholder="Paste news URL here..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full p-4 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-black transition"
            />
            <button
              onClick={handleSummarize}
              disabled={loading || !url}
              className="w-full py-3 bg-black text-white rounded-xl font-medium hover:opacity-90 transition disabled:opacity-50 flex justify-center items-center cursor-pointer shadow-lg shadow-black/10"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Summarizing...
                </span>
              ) : (
                'Generate Digest'
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="text-red-500 bg-red-50 p-4 rounded-xl w-full border border-red-100 text-sm">
            <b>Error:</b> {error}
          </div>
        )}

        {summary && (
          <div className="w-full glass-card p-8 rounded-2xl animate-fade-in relative group">
            <button
              onClick={copyToClipboard}
              className="absolute top-4 right-4 p-2 rounded-lg bg-gray-50 text-gray-400 hover:text-black hover:bg-gray-100 transition opacity-0 group-hover:opacity-100 text-xs font-medium"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {summary}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </main>

      <style jsx global>{`
        .markdown-content strong {
          display: block;
          font-size: 1.25rem;
          margin-bottom: 1.5rem;
          color: #1a1a1b;
        }
        .markdown-content ul {
          list-style-type: disc;
          padding-left: 1.5rem;
          margin-bottom: 1.5rem;
          color: #374151;
        }
        .markdown-content li {
          margin-bottom: 0.5rem;
        }
        .markdown-content em {
          display: block;
          margin-top: 2rem;
          padding: 1rem;
          background: #fdfdfd;
          border-left: 3px solid #000;
          color: #6b7280;
          font-style: italic;
        }
      `}</style>
    </div>
  );
}
