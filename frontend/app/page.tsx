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
    <div className="flex min-h-screen flex-col items-center justify-center p-8 font-sans bg-[#fcfcfc]">
      <main className="w-full max-w-2xl flex flex-col items-center gap-10 animate-fade-in">
        <div className="text-center flex flex-col gap-2">
          <h1 className="text-5xl font-black tracking-tighter text-gray-900">AI 기사 요약</h1>
          <p className="text-gray-400 font-medium uppercase tracking-[0.2em] text-xs">Summarize Articles</p>
        </div>

        <div className="w-full glass-card p-8 rounded-[2.5rem] shadow-2xl shadow-gray-200/50">
          <div className="flex flex-col gap-5">
            <div className="relative">
              <input
                type="url"
                placeholder="뉴스 기사 URL을 붙여넣으세요..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full p-5 rounded-2xl border-2 border-gray-100 focus:border-black focus:outline-none transition-all bg-gray-50/50 text-lg placeholder:text-gray-300"
              />
            </div>
            <button
              onClick={handleSummarize}
              disabled={loading || !url}
              className="w-full py-5 bg-black text-white rounded-2xl font-bold text-xl hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-30 flex justify-center items-center cursor-pointer shadow-xl shadow-black/20 overflow-hidden relative"
            >
              {loading ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="cat-run-container">
                    <span className="cat-emoji">🐈‍⬛</span>
                  </div>
                  <span className="text-sm font-medium animate-pulse">기사를 읽고 있어요...</span>
                </div>
              ) : (
                '요약하기'
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="text-red-600 bg-red-50/50 backdrop-blur-sm p-5 rounded-2xl w-full border border-red-100/50 text-sm font-medium flex gap-3 items-center">
            <span className="bg-red-100 p-1 rounded-full text-xs">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {summary && (
          <div className="w-full glass-card p-10 rounded-[2.5rem] animate-fade-in relative group border-2 border-white/50">
            <button
              onClick={copyToClipboard}
              className="absolute top-6 right-6 px-4 py-2 rounded-xl bg-gray-900 text-white hover:bg-black transition-all opacity-0 group-hover:opacity-100 text-xs font-bold shadow-lg"
            >
              {copied ? '복사 완료!' : '결과 복사'}
            </button>
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {summary}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </main>

      <footer className="mt-20 text-gray-300 text-xs font-medium tracking-widest uppercase pb-10">
        &copy; 2026 Summarize Articles
      </footer>

      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Noto+Sans+KR:wght@400;700;900&display=swap');
        
        body {
          font-family: 'Inter', 'Noto Sans KR', sans-serif;
        }

        .cat-run-container {
          position: relative;
          width: 60px;
          height: 30px;
          overflow: hidden;
        }

        .cat-emoji {
          position: absolute;
          font-size: 24px;
          animation: catRun 1.5s infinite linear;
        }

        @keyframes catRun {
          0% { left: -30px; transform: scaleX(1); }
          45% { transform: scaleX(1); }
          50% { left: 60px; transform: scaleX(-1); }
          95% { transform: scaleX(-1); }
          100% { left: -30px; transform: scaleX(1); }
        }

        .markdown-content strong {
          display: block;
          font-size: 1.5rem;
          font-weight: 900;
          margin-bottom: 2rem;
          color: #111;
          letter-spacing: -0.03em;
          line-height: 1.2;
        }
        .markdown-content ul {
          list-style: none;
          padding: 0;
          margin-bottom: 2rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .markdown-content li {
          padding: 1.25rem;
          background: rgba(255,255,255,0.4);
          border-radius: 1rem;
          border: 1px solid rgba(0,0,0,0.03);
          color: #444;
          line-height: 1.6;
          position: relative;
          padding-left: 3rem;
        }
        .markdown-content li::before {
          content: '✓';
          position: absolute;
          left: 1.25rem;
          top: 1.3rem;
          color: #000;
          font-weight: bold;
        }
        .markdown-content em {
          display: block;
          margin-top: 3rem;
          padding: 1.5rem;
          background: #111;
          border-radius: 1.25rem;
          color: #eee;
          font-style: italic;
          font-size: 0.95rem;
          line-height: 1.6;
          box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .markdown-content em::before {
          content: 'Insight';
          display: block;
          font-size: 0.5rem;
          text-transform: uppercase;
          letter-spacing: 0.3em;
          margin-bottom: 0.5rem;
          color: #666;
          font-style: normal;
        }
      `}</style>
    </div>
  );
}
