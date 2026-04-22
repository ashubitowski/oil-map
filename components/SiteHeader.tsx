import ShareButton from "./ShareButton";
import LastUpdated from "./LastUpdated";

export default function SiteHeader() {
  return (
    <header className="flex items-center gap-3 px-4 py-2.5 border-b border-amber-500/20 bg-gray-950/95 backdrop-blur-sm flex-shrink-0">
      {/* Logo + title */}
      <a
        href="/"
        className="flex items-center gap-2.5 group flex-shrink-0"
        aria-label="US Oil Map home"
      >
        {/* Derrick mark */}
        <svg
          width="22"
          height="22"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
          className="flex-shrink-0 opacity-90 group-hover:opacity-100 transition-opacity"
        >
          <line x1="16" y1="4" x2="6" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="16" y1="4" x2="26" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="9" y1="19" x2="23" y2="19" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
          <line x1="5" y1="28" x2="27" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="16" cy="4" r="2.5" fill="#f59e0b" />
        </svg>
        <h1 className="text-white font-semibold text-sm tracking-wide leading-none">US Oil Map</h1>
      </a>

      <LastUpdated />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right-side nav */}
      <div className="flex items-center gap-1">
        {/* Share */}
        <ShareButton />

        {/* Buy Me a Coffee */}
        <a
          href="https://buymeacoffee.com/shuby"
          target="_blank"
          rel="noopener noreferrer"
          title="Buy me a coffee"
          aria-label="Support on Buy Me a Coffee"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-amber-400/80 hover:text-amber-300 hover:bg-amber-500/10 border border-transparent hover:border-amber-500/20 transition-colors"
        >
          <span aria-hidden="true">☕</span>
          <span className="hidden sm:inline">Support</span>
        </a>

        {/* GitHub */}
        <a
          href="https://github.com/ashubitowski/oil-map"
          target="_blank"
          rel="noopener noreferrer"
          title="View source on GitHub"
          aria-label="GitHub repository"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-gray-400 hover:text-gray-200 hover:bg-gray-800 border border-transparent transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
          <span className="hidden sm:inline text-xs">GitHub</span>
        </a>

        {/* Built by */}
        <a
          href="https://github.com/ashubitowski"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden md:flex items-center gap-1 px-2.5 py-1.5 rounded-md text-gray-600 hover:text-gray-400 border border-transparent transition-colors text-xs"
        >
          Built by Shuby
        </a>
      </div>
    </header>
  );
}
