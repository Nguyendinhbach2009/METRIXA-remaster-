import React, { useEffect, useState } from "react";
import { GraduationCap, BarChart3, Table as TableIcon, X, Globe, Filter, Loader2, Users, Search } from "lucide-react";
import RankingTable from "./components/RankingTable";
import ChartComponent from "./components/ChartComponent";
import FieldsSelector from "./components/FieldsSelector";

// Import preprocessed data
import fieldsData from "./data/fields.json";

// Helper function to find the main field folder for a given subfield
function getMainFieldForSubfield(subfield) {
  const subfieldsMap = fieldsData.subfieldsMap || {};
  
  // Normalize input to lowercase for case-insensitive comparison
  const normalizedSubfield = subfield.toLowerCase();
  
  // Check if it's a main field itself (case-insensitive)
  for (const [mainFieldKey, subfields] of Object.entries(subfieldsMap)) {
    if (mainFieldKey.toLowerCase() === normalizedSubfield) {
      return mainFieldKey; // Return the original case from the mapping
    }
  }
  
  // Find which main field contains this subfield (case-insensitive)
  for (const [mainField, subfields] of Object.entries(subfieldsMap)) {
    const foundSubfield = subfields.find(s => s.toLowerCase() === normalizedSubfield);
    if (foundSubfield) {
      return mainField; // Return the main field that contains this subfield
    }
  }
  
  // If not found in mapping, return null
  return null;
}

/* ---------------- App ---------------- */

export default function App() {
  // Get all fields (which includes both main fields and subfields)
  const uniqueFields = fieldsData.fields || [];
  const [selectedFields, setSelectedFields] = useState(uniqueFields.slice());
  const [ranking, setRanking] = useState([]);
  const [overallRanking, setOverallRanking] = useState([]); // Ranking based on all fields
  const [authorsByUniversity, setAuthorsByUniversity] = useState({});
  const [uniFieldContrib, setUniFieldContrib] = useState({});
  const [selectedUni, setSelectedUni] = useState(null);
  const [open, setOpen] = useState(false);
  const [viewMode, setViewMode] = useState("chart"); // "chart" or "table"
  const [loading, setLoading] = useState(true);
  const [fieldRankCache, setFieldRankCache] = useState(new Map());
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = 15;
  const [mainfieldRankings, setMainfieldRankings] = useState({});
  const [searchTerm, setSearchTerm] = useState("");

  // Load initial data when component mounts
  useEffect(() => {
    const loadFieldData = async () => {
      setLoading(true);
      
      if (selectedFields.length === 0) {
        setRanking([]);
        setAuthorsByUniversity({});
        setUniFieldContrib({});
        setFieldRankCache(new Map());
        setLoading(false);
        return;
      }

      // Load and merge data from individual field files
      try {
        const fieldDataPromises = selectedFields.map(async (field) => {
          const mainField = getMainFieldForSubfield(field);
          const fieldFileName = field.toLowerCase().replace(/[–—-]/g, '-').replace(/ /g, '_');
          
          if (mainField) {
            // Load from main field folder
            const mainFieldFolder = mainField.replace(/\s+/g, '_');
            try {
              // Check if this is a main field that should be handled differently
              if (mainField === field) {
                // This is trying to load data for a main field itself, not a subfield
                // Skip main fields in individual field loading
                // console.warn(`Skipping main field ${field} - main fields are loaded separately`);
                return { field, data: null };
              }
              
              const module = await import(`./data/${mainFieldFolder}/${fieldFileName}.json`);
              return { field, data: module.default };
            } catch (err) {
              console.warn(`Could not load data for field: ${field} from ${mainFieldFolder}`, err);
              return { field, data: null };
            }
          } else {
            console.warn(`Could not find main field for: ${field}`);
            return { field, data: null };
          }
        });

        const fieldDataResults = await Promise.all(fieldDataPromises);
        
        // Create field rank cache
        const newFieldRankCache = new Map();
        
        // Merge the data from all selected fields
        const mergedAuthorsByUni = {};
        const mergedUniFieldContrib = {};
        const uniContributions = {};

        fieldDataResults.forEach(({ field, data }) => {
          if (!data) return;

          // Populate field rank cache
          if (data.ranking) {
            data.ranking.forEach((uniData, index) => {
              const key = `${uniData.university}-${field}`;
              newFieldRankCache.set(key, index + 1);
            });
          }

          // Merge authorsByUniversity
          if (data.authorsByUniversity) {
            Object.entries(data.authorsByUniversity).forEach(([uni, authors]) => {
              if (!mergedAuthorsByUni[uni]) {
                mergedAuthorsByUni[uni] = [];
              }
              mergedAuthorsByUni[uni].push(...authors);
            });
          }

          // Merge uniFieldContrib - only include the current field being processed
          if (data.uniFieldContrib) {
            Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
              if (!mergedUniFieldContrib[uni]) {
                mergedUniFieldContrib[uni] = {};
              }
              // Only include contributions for the current field
              if (fields[field] !== undefined) {
                mergedUniFieldContrib[uni][field] = 
                  (mergedUniFieldContrib[uni][field] || 0) + fields[field];
              }
            });
          }

          // Aggregate university contributions based on uniFieldContrib for the current field
          if (data.uniFieldContrib) {
            Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
              // Only process if this university has contribution in the current field
              if (fields[field] !== undefined && fields[field] > 0) {
                if (!uniContributions[uni]) {
                  uniContributions[uni] = {
                    university: uni,
                    totalContribution: 0,
                    paperCount: 0,
                    authorCount: 0
                  };
                }
                // Add the contribution for this specific field only
                uniContributions[uni].totalContribution += fields[field];
                
                // Get paper and author counts from the ranking data for this university
                const uniRankData = data.ranking?.find(r => r.university === uni);
                if (uniRankData) {
                  uniContributions[uni].paperCount += uniRankData.paperCount || 0;
                  uniContributions[uni].authorCount += uniRankData.authorCount || 0;
                }
              }
            });
          }
        });

        // Consolidate authors by university (remove duplicates and sum contributions)
        Object.keys(mergedAuthorsByUni).forEach(uni => {
          const authorMap = {};
          mergedAuthorsByUni[uni].forEach(author => {
            if (!authorMap[author.author]) {
              authorMap[author.author] = {
                author: author.author,
                contribution: 0
              };
            }
            authorMap[author.author].contribution += author.contribution || 0;
          });
          
          // Calculate percentages
          const totalContrib = Object.values(authorMap).reduce((sum, a) => sum + a.contribution, 0);
          mergedAuthorsByUni[uni] = Object.values(authorMap).map(a => ({
            ...a,
            percent: totalContrib > 0 ? a.contribution / totalContrib : 0
          }));
        });

        // Create ranking array and sort by total contribution
        const mergedRanking = Object.values(uniContributions)
          .sort((a, b) => b.totalContribution - a.totalContribution)
          .map((uni, index) => ({
            ...uni,
            originalRank: index + 1
          }));

        // Debug: log sample of ranking data
        console.log('App.jsx mergedRanking sample:', mergedRanking.slice(0, 3).map(uni => ({
          university: uni.university,
          totalContribution: uni.totalContribution,
          originalRank: uni.originalRank
        })));

        setRanking(mergedRanking);
        setAuthorsByUniversity(mergedAuthorsByUni);
        setUniFieldContrib(mergedUniFieldContrib);
        setFieldRankCache(newFieldRankCache);
      } catch (error) {
        console.error('Error loading field data:', error);
        // Clear data on error
        setRanking([]);
        setAuthorsByUniversity({});
        setUniFieldContrib({});
        setFieldRankCache(new Map());
        setOverallRanking([]);
      }
      
      setLoading(false);
    };

    loadFieldData();
  }, [selectedFields, uniqueFields]);

  // Load overall ranking data (all fields) for proper overall ranking display
  useEffect(() => {
    const loadOverallRanking = async () => {
      try {
        // Get all available fields (both main fields and subfields)
        const allFields = fieldsData.fields || [];
        const fieldDataPromises = allFields.map(async (field) => {
          const mainField = getMainFieldForSubfield(field);
          const fieldFileName = field.toLowerCase().replace(/[–—-]/g, '-').replace(/ /g, '_');
          
          if (mainField) {
            // Load from main field folder
            const mainFieldFolder = mainField.replace(/\s+/g, '_');
            try {
              // Check if this is a main field that should be handled differently
              if (mainField === field) {
                // This is trying to load data for a main field itself, not a subfield
                // Skip main fields in individual field loading
                // console.warn(`Skipping main field ${field} - main fields are loaded separately`);
                return { field, data: null };
              }
              
              const module = await import(`./data/${mainFieldFolder}/${fieldFileName}.json`);
              return { field, data: module.default };
            } catch (err) {
              console.warn(`Could not load data for field: ${field} from ${mainFieldFolder}`, err);
              return { field, data: null };
            }
          } else {
            console.warn(`Could not find main field for: ${field}`);
            return { field, data: null };
          }
        });

        const fieldDataResults = await Promise.all(fieldDataPromises);
        
        // Aggregate contributions from all fields
        const allContributions = {};
        
        fieldDataResults.forEach(({ field, data }) => {
          if (!data || !data.uniFieldContrib) return;
          
          Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
            if (!allContributions[uni]) {
              allContributions[uni] = {
                university: uni,
                totalContribution: 0,
                paperCount: 0,
                authorCount: 0
              };
            }
            
            // Add contribution for this specific field
            if (fields[field] !== undefined) {
              allContributions[uni].totalContribution += fields[field] || 0;
            }
            
            // Get paper and author counts if available
            const uniRankData = data.ranking?.find(r => r.university === uni);
            if (uniRankData) {
              allContributions[uni].paperCount += uniRankData.paperCount || 0;
              allContributions[uni].authorCount += uniRankData.authorCount || 0;
            }
          });
        });
        
        // Calculate overall ranking based on all fields
        const overallRanking = Object.values(allContributions)
          .sort((a, b) => b.totalContribution - a.totalContribution)
          .map((uni, index) => ({
            ...uni,
            originalRank: index + 1
          }));
        
        setOverallRanking(overallRanking);
      } catch (error) {
        console.error('Error loading overall ranking data:', error);
        setOverallRanking([]);
      }
    };
    
    loadOverallRanking();
  }, []); // Only run once on mount

  // Load mainfield rankings for better performance
  useEffect(() => {
    const loadMainfieldRankings = async () => {
      if (selectedFields.length === 0) {
        setMainfieldRankings({});
        return;
      }

      try {
        // Group selected fields by their main field
        const fieldsByMainField = {};
        selectedFields.forEach(field => {
          const mainField = getMainFieldForSubfield(field);
          if (mainField) {
            if (!fieldsByMainField[mainField]) {
              fieldsByMainField[mainField] = [];
            }
            fieldsByMainField[mainField].push(field);
          }
        });

        // Load ranking data for each main field
        const rankingPromises = Object.keys(fieldsByMainField).map(async (mainField) => {
          try {
            const mainFieldFileName = mainField.toLowerCase().replace(/\s+/g, '_');
            const module = await import(`./data/rankings/${mainFieldFileName}_rankings.json`);
            return { mainField, data: module.default };
          } catch (err) {
            console.warn(`Could not load ranking data for ${mainField}:`, err);
            return { mainField, data: null };
          }
        });

        const rankingResults = await Promise.all(rankingPromises);
        
        // Build mainfield rankings object
        const rankings = {};
        rankingResults.forEach(({ mainField, data }) => {
          if (data && data.mainfieldRankings && data.mainfieldRankings[mainField]) {
            rankings[mainField] = data.mainfieldRankings[mainField];
          }
        });
        
        setMainfieldRankings(rankings);
      } catch (error) {
        console.error('Error loading mainfield rankings:', error);
        setMainfieldRankings({});
      }
    };

    loadMainfieldRankings();
  }, [selectedFields]);

  const openAuthors = (uni) => { setSelectedUni(uni); setOpen(true); };
  const closeAuthors = () => { setOpen(false); setSelectedUni(null); };
  const authorsForSelected = selectedUni ? (authorsByUniversity[selectedUni] || []) : [];

  const fieldRowsForUni = (uni) => {
    const map = uniFieldContrib[uni] || {};
    
    // Group contributions by mainfield
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
        // If no main field found, treat as standalone field
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

  const topFieldsForSelected = (n = 5) => {
    if (!selectedUni) return [];
    const map = uniFieldContrib[selectedUni] || {};
    const total = Object.values(map).reduce((s, x) => s + (Number(x) || 0), 0);
    return Object.keys(map).map(f => ({ field: f, contrib: map[f], pct: total > 0 ? (map[f] / total) * 100 : 0 })).sort((a,b)=>b.contrib - a.contrib).slice(0, n);
  };

  // Filter ranking data based on search term
  const filteredRanking = React.useMemo(() => {
    if (!searchTerm.trim()) {
      return ranking;
    }
    const lowerSearch = searchTerm.toLowerCase();
    const filtered = ranking.filter(uni =>
      uni.university.toLowerCase().includes(lowerSearch)
    );
    
    // Debug: log filtered data
    console.log('App.jsx filteredRanking sample:', filtered.slice(0, 3).map(uni => ({
      university: uni.university,
      totalContribution: uni.totalContribution,
      originalRank: uni.originalRank
    })));
    
    return filtered;
  }, [ranking, searchTerm]);

  // Reset to first page when search term changes
  useEffect(() => {
    setCurrentPage(0);
  }, [searchTerm]);

  return (
    <div className="min-h-screen">
      {/* Header */}
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
              onClick={() => window.location.href = "/paper-project-redo/"}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:from-purple-500 hover:to-pink-500 transition-all duration-300 flex-shrink-0 shadow-lg"
            >
            Papers Distribution Page →
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex gap-6 items-start">
          {/* Sidebar */}
          <aside className="w-80 flex-shrink-0">
            <FieldsSelector 
              fields={uniqueFields} 
              selected={selectedFields} 
              setSelected={setSelectedFields}
            />
          </aside>

          {/* Main area */}
          <main className="flex-1 min-w-0">
            {/* View toggle and title */}
            <div className="space-y-4 mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
                    Contribution Chart
                  </h2>
                  <p className="text-sm text-[var(--text-secondary)]">
                    {filteredRanking.length > 0 ? (
                      <>
                        Page {currentPage + 1}/{Math.ceil(filteredRanking.length / pageSize)} - Showing {Math.min(pageSize, filteredRanking.length - currentPage * pageSize)} universities
                        {searchTerm && ` (filtered from ${ranking.length})`}
                      </>
                    ) : searchTerm ? (
                      'No matching universities found'
                    ) : (
                      'No data'
                    )}
                  </p>
                </div>
              </div>

              {/* Search bar */}
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Search size={18} className="text-[var(--text-secondary)]" />
                </div>
                <input
                  type="text"
                  placeholder="Search for university affiliation..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-[var(--surface)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition-all duration-200"
                />
                {searchTerm && (
                  <button
                    onClick={() => setSearchTerm("")}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>
            </div>

            {/* Content */}
            {loading ? (
              <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-12 text-center backdrop-blur-sm">
                <div className="max-w-md mx-auto">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <Loader2 size={32} className="text-purple-400 animate-spin" />
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Loading data...
                  </h3>
                  <p className="text-sm text-[var(--text-secondary)]">
                    Initializing application. Please wait a moment.
                  </p>
                </div>
              </div>
            ) : selectedFields.length === 0 ? (
              <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-12 text-center backdrop-blur-sm">
                <div className="max-w-md mx-auto">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <Filter size={32} className="text-purple-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    No field selected
                  </h3>
                  <p className="text-sm text-[var(--text-secondary)]">
                    Please select at least one specialization from the filter on the left to view the rankings.
                  </p>
                </div>
              </div>
            ) : viewMode === "chart" ? (
              <ChartComponent
                data={filteredRanking}
                pageSize={pageSize}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                onUniversityClick={openAuthors}
                selectedFields={selectedFields}
                authorsByUniversity={authorsByUniversity}
                mainfieldRankings={mainfieldRankings}
                getUniversityFieldRank={(university, field) => {
                  // Find the rank of a university within a specific field
                  const fieldFileName = field.toLowerCase().replace(/[–—-]/g, '-').replace(/ /g, '_');
                  try {
                    // Synchronously look up pre-loaded field data
                    // Since field data is loaded when selectedFields changes, we need to cache it
                    return fieldRankCache.get(`${university}-${field}`) || null;
                  } catch (err) {
                    console.warn(`Could not find rank for ${university} in ${field}:`, err);
                    return null;
                  }
                }}
              />
            ) : (
              <RankingTable
                data={filteredRanking}
                authorsByUniversity={authorsByUniversity}
                onUniversityClick={openAuthors}
              />
            )}
          </main>
        </div>
      </div>

      {/* Modal */}
      {open && (
        <div 
          className="fixed inset-0 bg-black/70 z-50 flex items-start justify-center overflow-y-auto p-4"
          onClick={closeAuthors}
        >
          <div 
            className="bg-[var(--surface)] rounded-2xl shadow-2xl w-full max-w-4xl my-8"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="relative p-6 border-b border-[var(--border)]">
              <button
                onClick={closeAuthors}
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
                    {(() => {
                      // Use pre-calculated rankings from backend for better performance
                      const displayRanks = [];
                      
                      // Add overall ranking at the top
                      const overallRankIndex = overallRanking.findIndex(uni => uni.university === selectedUni);
                      const overallRank = overallRankIndex >= 0 ? overallRankIndex + 1 : null;
                      
                      if (overallRank) {
                        displayRanks.push({
                          field: "Overall",
                          rank: overallRank,
                          isOverall: true
                        });
                      }
                      
                      // Get rankings for each main field from pre-calculated data
                      const mainFieldRanks = [];
                      
                      Object.entries(mainfieldRankings).forEach(([mainField, rankingData]) => {
                        // Find this university's rank in the mainfield ranking
                        const uniRankData = rankingData.find(uni => uni.university === selectedUni);
                        if (uniRankData && uniRankData.rank) {
                          mainFieldRanks.push({
                            field: mainField,
                            rank: uniRankData.rank,
                            isOverall: false
                          });
                        }
                      });
                      
                      // Sort by rank and add to display
                      mainFieldRanks.sort((a, b) => a.rank - b.rank);
                      displayRanks.push(...mainFieldRanks);
                      
                       return displayRanks.length > 0 ? (
                        displayRanks.map((item) => (
                          <p key={item.field} className={`text-xs ${item.isOverall ? 'text-purple-400 font-semibold' : 'text-[var(--text-muted)]'}`}>
                            #{item.rank} {item.field}
                          </p>
                        ))
                      ) : (
                        <p className="text-xs text-[var(--text-muted)]">
                          No ranking data available.
                        </p>
                      );
                    })()}
                  </div>
                )}
              </div>
            </div>

            {/* Modal content */}
            <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto scrollbar-custom">
              {/* Authors section */}
              <div>
                {(() => {
                  // Sort authors by contribution in descending order
                  const sortedAuthors = [...authorsForSelected].sort((a, b) => 
                    (Number(b.contribution) || 0) - (Number(a.contribution) || 0)
                  );
                  
                  const totalAuthors = sortedAuthors.length;
                  const MAX_AUTHORS_DISPLAY = 100;
                  const displayAuthors = sortedAuthors.slice(0, MAX_AUTHORS_DISPLAY);
                  const remainingAuthors = totalAuthors - MAX_AUTHORS_DISPLAY;
                  
                  // Calculate total contribution from ALL authors
                  const totalContribution = sortedAuthors.reduce((s, x) => s + (Number(x.contribution) || 0), 0);
                  
                  // Calculate stats for remaining authors
                  const remainingAuthorsList = sortedAuthors.slice(MAX_AUTHORS_DISPLAY);
                  const remainingContribution = remainingAuthorsList.reduce((s, x) => s + (Number(x.contribution) || 0), 0);
                  
                  return (
                    <>
                      <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                        {totalAuthors > MAX_AUTHORS_DISPLAY ? `Top ${MAX_AUTHORS_DISPLAY} Authors` : 'Authors'}
                      </h3>
                      {totalAuthors === 0 ? (
                        <p className="text-[var(--text-secondary)]">No authors found for this university.</p>
                      ) : (
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
                                  <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">{Number(a.contribution ?? 0).toFixed(4)}</td>
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
                                          Additional contribution: {remainingContribution.toFixed(4)} ({((remainingContribution / totalContribution) * 100).toFixed(1)}%)
                                        </p>
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                              <tr className="bg-[var(--bg-primary)] font-semibold">
                                <td className="px-4 py-3"></td>
                                 <td className="px-4 py-3 text-sm text-[var(--text-primary)]">
                                  {totalAuthors > MAX_AUTHORS_DISPLAY 
                                    ? `TOTAL` 
                                    : 'TOTAL'}
                                </td>
                                <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">
                                  {totalContribution.toFixed(4)}
                                </td>
                                <td className="px-4 py-3"></td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>

              {/* Fields section */}
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                  Contribution by Field
                </h3>
                {selectedUni ? (() => {
                  const { rows, total } = fieldRowsForUni(selectedUni);
                  if (rows.length === 0) {
                    return <p className="text-[var(--text-secondary)]">No contribution by field.</p>;
                  }
                  return (
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
                              <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">{Number(r.contribution ?? 0).toFixed(4)}</td>
                              <td className="px-4 py-3 text-sm text-[var(--text-secondary)] text-right">
                                {total > 0 ? ((r.contribution / total) * 100).toFixed(1) : "0.0"}%
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-[var(--bg-primary)] font-semibold">
                            <td className="px-4 py-3 text-sm text-[var(--text-primary)]">TOTAL</td>
                            <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">{Number(total).toFixed(4)}</td>
                            <td className="px-4 py-3 text-sm text-[var(--text-primary)] text-right">100.0%</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })() : null}
              </div>
            </div>

            {/* Modal footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-[var(--border)]">
              <button
                onClick={closeAuthors}
                className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:from-purple-500 hover:to-pink-500 transition-all duration-300 shadow-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
