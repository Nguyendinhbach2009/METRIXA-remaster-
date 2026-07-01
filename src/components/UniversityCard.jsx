import React from "react";
import PropTypes from "prop-types";
import { Trophy, Award, Medal } from "lucide-react";
import { formatNumber } from "../lib/utils";

function getMedalIcon(rank) {
  if (rank === 1) return <Trophy size={18} className="text-yellow-500" />;
  if (rank === 2) return <Award size={18} className="text-gray-400" />;
  if (rank === 3) return <Medal size={18} className="text-amber-600" />;
  return null;
}

export default function UniversityCard({ 
  university, 
  rank, 
  contribution, 
  authorCount,
  percentage,
  onClick,
  animationWidth,
  universityUrls
}) {
  return (
    <div
      className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-5 hover:shadow-lg hover:border-purple-500/50 transition-all duration-300 cursor-pointer backdrop-blur-sm"
      onClick={() => onClick(university)}
    >
      <div className="flex items-center gap-4">
        <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center shadow-lg">
          <span className="text-white font-bold text-lg">{rank}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-0.5 line-clamp-1">
                {universityUrls?.[university] ? (
                  <a
                    href={universityUrls[university]}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-purple-400 hover:underline transition-colors cursor-pointer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {university}
                  </a>
                ) : (
                  university
                )}
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                {authorCount || 0} authors
              </p>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {getMedalIcon(rank)}
              <div className="text-right">
                <div className="text-xl font-bold text-[var(--primary)]">
                  {formatNumber(contribution, 4)}
                </div>
                <div className="text-xs text-[var(--text-muted)]">Score</div>
              </div>
            </div>
          </div>

          <div className="relative h-7 bg-[var(--bg-primary)] rounded-full overflow-hidden border border-[var(--border)]">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-600 to-pink-600 rounded-full flex items-center justify-end pr-3 shadow-lg"
              style={{ 
                width: `${animationWidth ?? 0}%`,
                transition: 'width 1.2s cubic-bezier(0.4, 0, 0.2, 1)'
              }}
            >
              {percentage >= 15 && (
                <span className="text-white text-xs font-semibold">
                  {percentage.toFixed(1)}%
                </span>
              )}
            </div>
            {percentage < 15 && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-[var(--text-secondary)]">
                {percentage.toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

UniversityCard.propTypes = {
  university: PropTypes.string.isRequired,
  rank: PropTypes.number.isRequired,
  contribution: PropTypes.number.isRequired,
  authorCount: PropTypes.number,
  percentage: PropTypes.number,
  onClick: PropTypes.func.isRequired,
  animationWidth: PropTypes.number,
  universityUrls: PropTypes.object
};