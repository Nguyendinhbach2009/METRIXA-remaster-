import React, { useMemo, useState, useEffect } from "react";
import PropTypes from "prop-types";
import { Trophy, Award, Medal } from "lucide-react";
import fieldsData from "../data/fields.json";
import overallRankings from "../data/rankings/overall_rankings.json";

// Helper function to parse CSV and create university name to URL mapping
const parseUniversityUrls = (csvText) => {
  const lines = csvText.trim().split('\n');
  const headers = lines[0].split(',');
  const nameIndex = headers.findIndex(h => h.trim() === 'English Name');
  const websiteIndex = headers.findIndex(h => h.trim() === 'Website');
  
  if (nameIndex === -1 || websiteIndex === -1) {
    console.warn('CSV headers not found as expected');
    return {};
  }
  
  const urlMap = {};
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    
    // Handle CSV parsing with quoted fields
    const values = [];
    let current = '';
    let inQuotes = false;
    
    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        values.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    values.push(current.trim());
    
    const name = values[nameIndex]?.replace(/"/g, '');
    const url = values[websiteIndex]?.replace(/"/g, '');
    
    if (name && url) {
      urlMap[name] = url;
    }
  }
  
  return urlMap;
};

// Load university URLs (this will be populated via useEffect with fetch)
const universityUrlsMap = {};

// Helper function to find the main field folder for a given subfield
function getMainFieldForSubfield(subfield) {
  const subfieldsMap = fieldsData.subfieldsMap || {};
  
  // Check if it's a main field itself
  if (subfieldsMap[subfield]) {
    return subfield;
  }
  
  // Find which main field contains this subfield
  for (const [mainField, subfields] of Object.entries(subfieldsMap)) {
    if (subfields.includes(subfield)) {
      return mainField;
    }
  }
  
  // If not found in mapping, return null
  return null;
}

export default function ChartComponent({ 
  data = [], 
  pageSize = 10,
  currentPage = 0,
  onPageChange = () => {},
  onUniversityClick = () => {},
  selectedFields = [],
  authorsByUniversity = {},
  getUniversityFieldRank = () => null,
  mainfieldRankings = {}
}) {
  const rowsAll = Array.isArray(data) ? data : [];
  const totalPages = Math.max(1, Math.ceil(rowsAll.length / pageSize));
  const page = currentPage;
  const setPage = onPageChange;
  const [animatedWidths, setAnimatedWidths] = useState({});
  const [universityUrls, setUniversityUrls] = useState({});

  const globalMax = useMemo(() => {
    const vals = rowsAll.map(r => Number(r.totalContribution ?? 0));
    return vals.length ? Math.max(...vals) : 1e-6;
  }, [rowsAll]);

  // Trigger animation when data changes or page changes
  useEffect(() => {
    // Reset all widths to 0
    setAnimatedWidths({});
    
    // Use requestAnimationFrame to ensure the reset is rendered before animation starts
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // Calculate target widths for current page
        const newWidths = {};
        const startIdx = page * pageSize;
        const pageRows = rowsAll.slice(startIdx, startIdx + pageSize);
        
        pageRows.forEach((r, idx) => {
          const key = r.university ?? idx;
          const val = Number(r.totalContribution ?? 0);
          const pctOfGlobal = globalMax > 0 ? (val / globalMax) * 100 : 0;
          newWidths[key] = Math.max(2, pctOfGlobal);
        });
        
        setAnimatedWidths(newWidths);
      });
    });
  }, [data, page, pageSize, rowsAll, globalMax]);

  // Load university URLs from CSV file
  useEffect(() => {
    const loadUniversityUrls = async () => {
      try {
        const response = await fetch('/paper-project-redo/urls.csv');
        if (!response.ok) {
          console.warn('Could not load urls.csv file');
          return;
        }
        const csvText = await response.text();
        const urlMap = parseUniversityUrls(csvText);
        setUniversityUrls(urlMap);
      } catch (error) {
        console.warn('Error loading university URLs:', error);
      }
    };

    loadUniversityUrls();
  }, []);

  const startIdx = page * pageSize;
  const pageRows = rowsAll.slice(startIdx, startIdx + pageSize);

  const getMedalIcon = (rank) => {
    if (rank === 1) return <Trophy size={18} className="text-yellow-500" />;
    if (rank === 2) return <Award size={18} className="text-gray-400" />;
    if (rank === 3) return <Medal size={18} className="text-amber-600" />;
    return null;
  };

  return (
    <div className="space-y-4">
      {pageRows.length === 0 ? (
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-12 text-center backdrop-blur-sm">
          <p className="text-[var(--text-secondary)]">No data to display</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pageRows.map((r, idx) => {
            // Debug: log the data to see if originalRank exists
            if (idx === 0) {
              console.log('ChartComponent data sample:', {
                university: r.university,
                totalContribution: r.totalContribution,
                originalRank: r.originalRank,
                hasOriginalRank: 'originalRank' in r
              });
            }
            
            const rank = r.originalRank || (idx + 1);
            const val = Number(r.totalContribution ?? 0);
            const pctOfGlobal = globalMax > 0 ? (val / globalMax) * 100 : 0;

            return (
              <div
                key={r.university ?? idx}
                className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-5 hover:shadow-lg hover:border-purple-500/50 transition-all duration-300 cursor-pointer backdrop-blur-sm"
                onClick={() => onUniversityClick(r.university)}
              >
                <div className="flex items-center gap-4">
                  {/* Rank badge */}
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center shadow-lg">
                    <span className="text-white font-bold text-lg">{rank}</span>
                  </div>

                  {/* University info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-[var(--text-primary)] mb-0.5 line-clamp-1">
                          {universityUrls[r.university] ? (
                              <a
                              href={universityUrls[r.university]}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:text-purple-400 hover:underline transition-colors cursor-pointer"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {r.university}
                            </a>
                          ) : (
                            r.university
                          )}
                        </h3>
                        
                        {/* Field ranks for this university - filtered based on selected subfields */}
                        {selectedFields.length > 0 && (() => {
                          // Use pre-calculated mainfield rankings from imported overall_rankings.json
                          const universityRanks = [];
                          const allMainfieldRankings = overallRankings.allMainfieldRankings || {};
                          
                          // Get unique main fields corresponding to selected subfields
                          const selectedMainFields = [...new Set(
                            selectedFields.map(subfield => getMainFieldForSubfield(subfield))
                          )].filter(Boolean);
                          
                          // Get rankings only for the main fields corresponding to selected subfields
                          selectedMainFields.forEach((mainField) => {
                            const fieldData = allMainfieldRankings[mainField];
                            if (fieldData) {
                              const rankingData = fieldData?.mainfieldRankings?.[mainField] || [];
                              // Find this university's rank in the mainfield ranking
                              const uniRankData = rankingData.find(uni => uni.university === r.university);
                              if (uniRankData && uniRankData.rank && uniRankData.rank <= 25) {
                                universityRanks.push({
                                  field: mainField,
                                  rank: uniRankData.rank
                                });
                              }
                            }
                          });
                          
                          // Sort by rank and limit to top 4
                          universityRanks.sort((a, b) => a.rank - b.rank);
                          
                           return universityRanks.length > 0 ? (
                            <div className="mb-2">
                              {universityRanks.slice(0, 4).map((item) => (
                                <span 
                                  key={item.field}
                                  className="inline-block text-xs bg-purple-500/20 text-purple-300 px-2 py-1 rounded mr-1 mb-1 border border-purple-500/30"
                                >
                                  #{item.rank} {item.field}
                                </span>
                              ))}
                              {universityRanks.length > 4 && (
                                <span className="inline-block text-xs text-[var(--text-muted)]">
                                  +{universityRanks.length - 4} more
                                </span>
                              )}
                            </div>
                          ) : null;
                        })()}
                        
                        <p className="text-xs text-[var(--text-muted)]">
                          {(authorsByUniversity[r.university]?.length || 0)} authors
                        </p>
                      </div>

                      {/* Score */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {getMedalIcon(rank)}
                        <div className="text-right">
                          <div className="text-xl font-bold text-[var(--primary)]">
                            {val.toFixed(4)}
                          </div>
                          <div className="text-xs text-[var(--text-muted)]">Score</div>
                        </div>
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="relative h-7 bg-[var(--bg-primary)] rounded-full overflow-hidden border border-[var(--border)]">
                      <div
                        className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-600 to-pink-600 rounded-full flex items-center justify-end pr-3 shadow-lg"
                        style={{ 
                          width: `${animatedWidths[r.university ?? idx] ?? 0}%`,
                          transition: 'width 1.2s cubic-bezier(0.4, 0, 0.2, 1)'
                        }}
                      >
                        {pctOfGlobal >= 15 && (
                          <span className="text-white text-xs font-semibold">
                            {pctOfGlobal.toFixed(1)}%
                          </span>
                        )}
                      </div>
                      {pctOfGlobal < 15 && (
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-[var(--text-secondary)]">
                          {pctOfGlobal.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 pt-2">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-gradient-to-r hover:from-purple-600 hover:to-pink-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 hover:shadow-lg"
          >
            Previous
          </button>
          
          <div className="flex gap-1 items-center">
            {/* First page */}
            {totalPages > 7 && page > 3 && (
              <>
                <button
                  onClick={() => setPage(0)}
                  className="w-10 h-10 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-gradient-to-r hover:from-purple-600 hover:to-pink-600 hover:text-white transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
                >
                  1
                </button>
                <span className="text-[var(--text-secondary)] px-1">...</span>
              </>
            )}
            
            {/* Page numbers around current page */}
            {Array.from({ length: totalPages }, (_, i) => i).filter(i => {
              // If total pages <= 7, show all pages
              if (totalPages <= 7) return true;
              
              // Otherwise, use smart pagination
              if (page <= 3) return i < 7; // Show first 7 pages
              if (page >= totalPages - 4) return i >= totalPages - 7; // Show last 7 pages
              return i >= page - 3 && i <= page + 3; // Show 3 before and after current
            }).map(pageNum => (
              <button
                key={pageNum}
                onClick={() => setPage(pageNum)}
                className={`w-10 h-10 rounded-lg text-sm font-medium transition-all duration-200 ${
                  pageNum === page
                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                    : 'text-[var(--text-secondary)] hover:bg-gradient-to-r hover:from-purple-600 hover:to-pink-600 hover:text-white hover:shadow-lg hover:-translate-y-0.5'
                }`}
              >
                {pageNum + 1}
              </button>
            ))}
            
            {/* Last page */}
            {totalPages > 7 && page < totalPages - 4 && (
              <>
                <span className="text-[var(--text-secondary)] px-1">...</span>
                <button
                  onClick={() => setPage(totalPages - 1)}
                  className="w-10 h-10 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-gradient-to-r hover:from-purple-600 hover:to-pink-600 hover:text-white transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
                >
                  {totalPages}
                </button>
              </>
            )}
          </div>
          
          <button
            onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
            disabled={page === totalPages - 1}
            className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-gradient-to-r hover:from-purple-600 hover:to-pink-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 hover:shadow-lg"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

ChartComponent.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    university: PropTypes.string,
    totalContribution: PropTypes.number,
    paperCount: PropTypes.number,
    authorCount: PropTypes.number,
    originalRank: PropTypes.number
  })),
  pageSize: PropTypes.number,
  currentPage: PropTypes.number,
  onPageChange: PropTypes.func,
  onUniversityClick: PropTypes.func,
  selectedFields: PropTypes.arrayOf(PropTypes.string),
  getUniversityFieldRank: PropTypes.func,
  mainfieldRankings: PropTypes.object
};