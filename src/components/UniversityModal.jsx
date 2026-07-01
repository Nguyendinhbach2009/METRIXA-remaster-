import React from "react";
import PropTypes from "prop-types";
import { X, Users } from "lucide-react";
import { formatNumber } from "../lib/utils";

const MAX_AUTHORS_DISPLAY = 100;

export default function UniversityModal({ 
  open, 
  onClose, 
  selectedUni, 
  authorsByUniversity, 
  uniFieldContrib,
  overallRanking,
  mainfieldRankings,
  getMainFieldForSubfield 
}) {
  const authorsForSelected = selectedUni ? (authorsByUniversity[selectedUni] || []) : [];
  const sortedAuthors = [...authorsForSelected].sort((a, b) => 
    (Number(b.contribution) || 0) - (Number(a.contribution) || 0)
  );
  
  const totalAuthors = sortedAuthors.length;
  const displayAuthors = sortedAuthors.slice(0, MAX_AUTHORS_DISPLAY);
  const remainingAuthors = totalAuthors - MAX_AUTHORS_DISPLAY;
  const totalContribution = sortedAuthors.reduce((s, x) => s + (Number(x.contribution) || 0), 0);
  const remainingContribution = sortedAuthors.slice(MAX_AUTHORS_DISPLAY)
    .reduce((s, x) => s + (Number(x.contribution) || 0), 0);

  const fieldRowsForUni = (uni) => {
    const map = uniFieldContrib[uni] || {};
    
    const mainFieldContributions = {};
    let totalContribution = 0;
    
    Object.entries(map).forEach(([subfield, contribution]) => {
      const mainField = getMainFieldForSubfield(subfield);
      if (mainField) {
        if (!mainFieldContributions[mainField]) {
          mainFieldContributions[mainField] = 0;
        }
        mainFieldContributions[mainField] += contribution;
        totalContribution += contribution;
      } else {
        if (!mainFieldContributions[subfield]) {
          mainFieldContributions[subfield] = 0;
        }
        mainFieldContributions[subfield] += contribution;
        totalContribution += contribution;
      }
    });
    
    const rows = Object.entries(mainFieldContributions).map(([field, contribution]) => ({ 
      field, 
      contribution 
    }));
    rows.sort((a, b) => b.contribution - a.contribution);
    
    return { rows, total: totalContribution };
  };

  const { rows, total } = selectedUni ? fieldRowsForUni(selectedUni) : { rows: [], total: 0 };

  if (!open || !selectedUni) return null;

  const overallRankIndex = overallRanking.findIndex(uni => uni.university === selectedUni);
  const overallRank = overallRankIndex >= 0 ? overallRankIndex + 1 : null;

  const displayRanks = [];
  
  if (overallRank) {
    displayRanks.push({ field: "Overall", rank: overallRank, isOverall: true });
  }
  
  const mainFieldRanks = [];
  
  Object.entries(mainfieldRankings).forEach(([mainField, rankingData]) => {
    const uniRankData = rankingData.find(uni => uni.university === selectedUni);
    if (uniRankData && uniRankData.rank && uniRankData.rank <= 25) {
      mainFieldRanks.push({ field: mainField, rank: uniRankData.rank, isOverall: false });
    }
  });
  
  mainFieldRanks.sort((a, b) => a.rank - b.rank);
  displayRanks.push(...mainFieldRanks);

  return (
    <div 
      className="fixed inset-0 bg-black/70 z-50 flex items-start justify-center overflow-y-auto p-4"
      onClick={onClose}
    >
      <div 
        className="bg-[var(--surface)] rounded-2xl shadow-2xl w-full max-w-4xl my-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative p-6 border-b border-[var(--border)]">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-10 h-10 rounded-lg hover:bg-purple-500/20 hover:border hover:border-purple-500/50 flex items-center justify-center transition-all duration-200 z-10 group"
          >
            <X size={20} className="text-[var(--text-secondary)] group-hover:text-purple-400 transition-colors" />
          </button>
          
          <div className="pr-12">
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
              {selectedUni ? `University Information - ${selectedUni}` : "University Information"}
            </h2>

            {selectedUni && (
              <div className="mt-2 space-y-1">
                {displayRanks.length > 0 ? (
                  displayRanks.map((item) => (
                    <p key={item.field} className={`text-xs ${item.isOverall ? 'text-purple-400 font-semibold' : 'text-[var(--text-muted)]'}`}>
                      #{item.rank} {item.field}
                    </p>
                  ))
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">
                    No ranking data available.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto scrollbar-custom">
          <div>
            {totalAuthors === 0 ? (
              <p className="text-[var(--text-secondary)]">No authors found for this university.</p>
            ) : (
              <>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                  {totalAuthors > MAX_AUTHORS_DISPLAY ? `Top ${MAX_AUTHORS_DISPLAY} Authors` : 'Authors'}
                </h3>
                <div className="bg-[var(--bg-secondary)] rounded-lg overflow-hidden border border-[var(--border)]">
                  <table className="w-full">
                    <thead className="bg-[var(--bg-primary)]">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">#</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">Author</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-secondary)]">Contribution</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-secondary)]">Percentage %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {displayAuthors.map((a, i) => (
                        <tr key={a.author ?? i} className="hover:bg-purple-500/10 transition-colors">
                          <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">{i + 1}</td>
                          <td className="px-4 py-3 text-sm text-[var(--text-primary)]">{a.author}</td>
                          <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">{formatNumber(a.contribution, 4)}</td>
                          <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">{((a.percent ?? 0) * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                      {remainingAuthors > 0 && (
                        <tr className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border-t-2 border-[var(--border)]">
                          <td colSpan="4" className="px-4 py-4">
                            <div className="flex items-center justify-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                                <Users size={20} className="text-purple-400" />
                              </div>
                              <div className="text-center">
                                <p className="text-sm font-semibold text-[var(--text-secondary)]">
                                  +{remainingAuthors} more authors
                                </p>
                                <p className="text-xs text-[var(--text-muted)]">
                                  Additional contribution: {formatNumber(remainingContribution, 4)} ({((remainingContribution / totalContribution) * 100).toFixed(1)}%)
                                </p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                      <tr className="bg-[var(--bg-primary)] font-semibold">
                        <td className="px-4 py-3"></td>
                        <td className="px-4 py-3 text-sm text-[var(--text-primary)]">
                          {totalAuthors > MAX_AUTHORS_DISPLAY ? `TOTAL` : 'TOTAL'}
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">
                          {formatNumber(totalContribution, 4)}
                        </td>
                        <td className="px-4 py-3"></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          <div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
              Contribution by Field
            </h3>
            {selectedUni ? (
              <>
                {rows.length === 0 ? (
                  <p className="text-[var(--text-secondary)]">No contribution by field.</p>
                ) : (
                  <div className="bg-[var(--bg-secondary)] rounded-lg overflow-hidden border border-[var(--border)]">
                    <table className="w-full">
                      <thead className="bg-[var(--bg-primary)]">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">Field</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-secondary)]">Contribution</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-secondary)]">Percentage %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {rows.map((r, i) => (
                          <tr key={r.field ?? i} className="hover:bg-purple-500/10 transition-colors">
                            <td className="px-4 py-3 text-sm text-[var(--text-primary)]">{r.field}</td>
                            <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">{formatNumber(r.contribution, 4)}</td>
                            <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">
                              {total > 0 ? ((r.contribution / total) * 100).toFixed(1) : "0.0"}%
                            </td>
                          </tr>
                        ))}
                        <tr className="bg-[var(--bg-primary)] font-semibold">
                          <td className="px-4 py-3 text-sm text-[var(--text-primary)]">TOTAL</td>
                          <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">{formatNumber(total, 4)}</td>
                          <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">100.0%</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : null}
          </div>
        </div>

        <div className="flex justify-end gap-3 p-6 border-t border-[var(--border)]">
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:from-purple-500 hover:to-pink-500 transition-all duration-300 shadow-lg"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

UniversityModal.propTypes = {
  open: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  selectedUni: PropTypes.string,
  authorsByUniversity: PropTypes.object,
  uniFieldContrib: PropTypes.object,
  overallRanking: PropTypes.array,
  mainfieldRankings: PropTypes.object,
  getMainFieldForSubfield: PropTypes.func.isRequired
};