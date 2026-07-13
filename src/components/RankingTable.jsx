import React from "react";
import PropTypes from "prop-types";
import { Trophy, Award, Medal } from "lucide-react";
import { formatNumber } from "../lib/utils";

function getMedalIcon(rank) {
  if (rank === 1) return <Trophy size={20} className="text-yellow-500" />;
  if (rank === 2) return <Award size={20} className="text-gray-400" />;
  if (rank === 3) return <Medal size={20} className="text-amber-600" />;
  return null;
}

export default function RankingTable({ data = [], authorsByUniversity = {}, onUniversityClick = () => {} }) {
  const rows = Array.isArray(data) ? data : [];
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const [page, setPage] = React.useState(0);

  const pageRows = rows.slice(page * pageSize, page * pageSize + pageSize);

  const goTo = (p) => {
    if (p < 0) p = 0;
    if (p >= totalPages) p = totalPages - 1;
    setPage(p);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const globalMax = rows.length > 0 ? Math.max(...rows.map(r => r.totalContribution || 0)) : 1;

  return (
    <div className="space-y-4">
      {pageRows.length === 0 ? (
        <div className="bg-white rounded-xl border border-[var(--border)] p-12 text-center">
          <p className="text-[var(--text-secondary)]">No ranking data available.</p>
        </div>
      ) : (
        pageRows.map((row, idx) => {
          const rank = row.rank || row.originalRank || (page * pageSize + idx + 1);
          const uniqueAuthors = authorsByUniversity[row.university] ? authorsByUniversity[row.university].length : 0;
          const percentage = globalMax > 0 ? (row.totalContribution / globalMax) * 100 : 0;

          return (
            <div
              key={row.university ?? idx}
              className="bg-white rounded-xl border border-[var(--border)] p-6 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => onUniversityClick(row.university)}
            >
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-[var(--primary)] flex items-center justify-center">
                  <span className="text-white font-bold text-lg">{rank}</span>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1 line-clamp-2">
                        {row.university}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      {getMedalIcon(rank)}
                      <div className="text-right">
                        <div className="text-2xl font-bold text-[var(--primary)]">
                          {formatNumber(row.totalContribution, 4)}
                        </div>
                        <div className="text-xs text-[var(--text-muted)]"> </div>
                      </div>
                    </div>
                  </div>

                  <div className="relative h-8 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="absolute inset-y-0 left-0 bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] rounded-full transition-all duration-500 flex items-center justify-end pr-3"
                      style={{ width: `${Math.max(2, percentage)}%` }}
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
        })
      )}

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-3 pt-6 border-t border-[var(--border)]">
          <button
            onClick={() => goTo(page - 1)}
            disabled={page === 0}
            className="px-6 py-2 rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] text-sm font-medium text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all duration-200"
          >
            Previous
          </button>
          
          <div className="flex gap-2 items-center">
            {page > 3 && (
              <>
                <button
                  onClick={() => goTo(0)}
                  className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 transition-all duration-200"
                >
                  1
                </button>
                <span className="text-[var(--text-muted)] px-1">...</span>
              </>
            )}
            
            {Array.from({ length: totalPages }, (_, i) => i).filter(i => {
              if (page <= 3) return i < 7;
              if (page >= totalPages - 4) return i >= totalPages - 7;
              return i >= page - 3 && i <= page + 3;
            }).map(pageNum => (
              <button
                key={pageNum}
                onClick={() => goTo(pageNum)}
                style={pageNum === page ? { background: 'linear-gradient(to right bottom in oklab, var(--primary) 0%, var(--accent) 100%)' } : {}}
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${
                  pageNum === page
                    ? 'text-white border-transparent shadow-[0_0_15px_rgba(117,31,198,0.5)] scale-105'
                    : 'border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40'
                }`}
              >
                {pageNum + 1}
              </button>
            ))}

            {page < totalPages - 4 && (
              <>
                <span className="text-[var(--text-muted)] px-1">...</span>
                <button
                  onClick={() => goTo(totalPages - 1)}
                  className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 transition-all duration-200"
                >
                  {totalPages}
                </button>
              </>
            )}
          </div>
          
          <button
            onClick={() => goTo(page + 1)}
            disabled={page === totalPages - 1}
            className="px-6 py-2 rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] text-sm font-medium text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all duration-200"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

RankingTable.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    university: PropTypes.string,
    totalContribution: PropTypes.number,
    paperCount: PropTypes.number,
    authorCount: PropTypes.number,
    originalRank: PropTypes.number
  })),
  authorsByUniversity: PropTypes.object,
  onUniversityClick: PropTypes.func,
};