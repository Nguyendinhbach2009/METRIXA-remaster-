import React from "react";
import { GraduationCap } from "lucide-react";

export default function Header() {
  return (
    <header className="bg-[var(--bg-secondary)] border-b border-[var(--border)] sticky top-0 z-50 shadow-md backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center flex-shrink-0 shadow-lg">
            <GraduationCap size={28} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 text-transparent bg-clip-text" style={{textShadow: '0 0 8px rgba(255, 255, 255, 0.3), 0 0 20px rgba(168, 85, 247, 0.6)'}}>
              Research Contribution Rankings
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Ranking Vietnamese universities by scientific research contribution
            </p>
          </div>
          <button
            onClick={() => window.location.href = import.meta.env.BASE_URL}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:from-purple-500 hover:to-pink-500 transition-all duration-300 flex-shrink-0 shadow-lg"
          >
            Papers Distribution Page →
          </button>
        </div>
      </div>
    </header>
  );
}