import React from 'react';
import PropTypes from 'prop-types';
import { Filter, Loader2 } from 'lucide-react';
import FieldsSelector from './FieldsSelector';
import ChartComponent from './ChartComponent';
import SearchBar from './SearchBar';

export default function MainContent({
  loading,
  selectedFields,
  ranking,
  searchTerm,
  authorsByUniversity,
  onSearchChange,
  onUniversityClick,
  onFieldsChange
}) {
  const [currentPage, setCurrentPage] = React.useState(0);
  const pageSize = 15;
  
  const filteredRanking = React.useMemo(() => {
    if (!searchTerm.trim()) {
      return ranking;
    }
    const lowerSearch = searchTerm.toLowerCase();
    return ranking.filter(uni =>
      uni.university.toLowerCase().includes(lowerSearch)
    );
  }, [ranking, searchTerm]);
  
  const totalPages = Math.max(1, Math.ceil(filteredRanking.length / pageSize));
  
  const handlePageChange = (page) => {
    setCurrentPage(Math.max(0, Math.min(totalPages - 1, page)));
  };
  
  const handlePrevPage = () => {
    if (currentPage > 0) handlePageChange(currentPage - 1);
  };
  
  const handleNextPage = () => {
    if (currentPage < totalPages - 1) handlePageChange(currentPage + 1);
  };

  return (
    <div className='max-w-7xl mx-auto px-6 py-8'>
      <div className='flex gap-6 items-start'>
        <aside className='w-80 flex-shrink-0'>
          <FieldsSelector 
            selected={selectedFields} 
            setSelected={onFieldsChange}
          />
        </aside>

        <main className='flex-1 min-w-0'>
          <div className='space-y-4 mb-6'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-[var(--text-secondary)]'>
                  {filteredRanking.length > 0 ? (
                    <>
                      Page {currentPage + 1} of {totalPages} | Showing {Math.min(pageSize, filteredRanking.length)} universities
                      {searchTerm && ' (filtered from ' + ranking.length + ')'}
                    </>
                  ) : searchTerm ? (
                    'No matching universities found'
                  ) : null}
                </p>
              </div>
            </div>

            <SearchBar 
              searchTerm={searchTerm} 
              onSearchChange={onSearchChange}
            />
          </div>

          {loading ? (
            <div className='bg-[var(--surface)] rounded-xl border border-[var(--border)] p-12 text-center backdrop-blur-sm'>
              <div className='max-w-md mx-auto'>
                <div className='w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/20 flex items-center justify-center'>
                  <Loader2 size={32} className='text-purple-400 animate-spin' />
                </div>
                <h3 className='text-lg font-semibold text-[var(--text-primary)] mb-2'>
                  Loading data...
                </h3>
                <p className='text-sm text-[var(--text-secondary)]'>
                  Initializing application. Please wait a moment.
                </p>
              </div>
            </div>
          ) : selectedFields.length === 0 ? (
            <div className='bg-[var(--surface)] rounded-xl border border-[var(--border)] p-12 text-center backdrop-blur-sm'>
              <div className='max-w-md mx-auto'>
                <div className='w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/20 flex items-center justify-center'>
                  <Filter size={32} className='text-purple-400' />
                </div>
                <h3 className='text-lg font-semibold text-[var(--text-primary)] mb-2'>
                  No field selected
                </h3>
                <p className='text-sm text-[var(--text-secondary)]'>
                  Please select at least one specialization from the filter on the left to view the rankings.
                </p>
              </div>
            </div>
          ) : (
            <>
              <ChartComponent
                data={filteredRanking}
                pageSize={pageSize}
                currentPage={currentPage}
                onPageChange={handlePageChange}
                onUniversityClick={onUniversityClick}
                selectedFields={selectedFields}
                authorsByUniversity={authorsByUniversity}
              />
              {totalPages > 1 && (
                <div className='mt-8 flex justify-center items-center gap-3 pt-6 border-t border-[var(--border)]'>
                  <button
                    onClick={handlePrevPage}
                    disabled={currentPage === 0}
                    className='px-6 py-2 rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] text-sm font-medium text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all duration-200'
                  >
                    Previous
                  </button>
                  
                  <div className='flex gap-2 items-center'>
                    {currentPage > 3 && (
                      <>
                        <button
                          onClick={() => handlePageChange(0)}
                          className='w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 transition-all duration-200'
                        >
                          1
                        </button>
                        <span className='text-[var(--text-muted)] px-1'>...</span>
                      </>
                    )}
                    
                    {Array.from({ length: totalPages }, (_, i) => i).filter(i => {
                      if (currentPage <= 3) return i < 7;
                      if (currentPage >= totalPages - 4) return i >= totalPages - 7;
                      return i >= currentPage - 3 && i <= currentPage + 3;
                    }).map(pageNum => (
                      <button
                        key={pageNum}
                        onClick={() => handlePageChange(pageNum)}
                        style={pageNum === currentPage ? { background: 'linear-gradient(to right bottom in oklab, var(--primary) 0%, var(--accent) 100%)' } : {}}
                        className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${
                          pageNum === currentPage
                            ? 'text-white border-transparent shadow-[0_0_15px_rgba(117,31,198,0.5)] scale-105'
                            : 'border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40'
                        }`}
                      >
                        {pageNum + 1}
                      </button>
                    ))}

                    {currentPage < totalPages - 4 && (
                      <>
                        <span className='text-[var(--text-muted)] px-1'>...</span>
                        <button
                          onClick={() => handlePageChange(totalPages - 1)}
                          className='w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 transition-all duration-200'
                        >
                          {totalPages}
                        </button>
                      </>
                    )}
                  </div>
                  
                  <button
                    onClick={handleNextPage}
                    disabled={currentPage >= totalPages - 1}
                    className='px-6 py-2 rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] text-sm font-medium text-[var(--text-secondary)] hover:bg-white/10 hover:border-purple-400/40 disabled:opacity-20 disabled:cursor-not-allowed transition-all duration-200'
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

MainContent.propTypes = {
  loading: PropTypes.bool.isRequired,
  selectedFields: PropTypes.arrayOf(PropTypes.string).isRequired,
  ranking: PropTypes.array.isRequired,
  searchTerm: PropTypes.string.isRequired,
  authorsByUniversity: PropTypes.object.isRequired,
  onSearchChange: PropTypes.func.isRequired,
  onUniversityClick: PropTypes.func.isRequired,
  onFieldsChange: PropTypes.func.isRequired
};