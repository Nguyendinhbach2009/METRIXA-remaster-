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
  const filteredRanking = React.useMemo(() => {
    if (!searchTerm.trim()) {
      return ranking;
    }
    const lowerSearch = searchTerm.toLowerCase();
    return ranking.filter(uni =>
      uni.university.toLowerCase().includes(lowerSearch)
    );
  }, [ranking, searchTerm]);

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
                <h2 className='text-xl font-semibold text-[var(--text-primary)] mb-1'>
                  Contribution Chart
                </h2>
                <p className='text-sm text-[var(--text-secondary)]'>
                  {filteredRanking.length > 0 ? (
                    <>
                      Showing {Math.min(15, filteredRanking.length)} universities
                      {searchTerm && ' (filtered from ' + ranking.length + ')'}
                    </>
                  ) : searchTerm ? (
                    'No matching universities found'
                  ) : (
                    'No data'
                  )}
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
            <ChartComponent
              data={filteredRanking}
              pageSize={15}
              currentPage={0}
              onUniversityClick={onUniversityClick}
              selectedFields={selectedFields}
              authorsByUniversity={authorsByUniversity}
            />
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