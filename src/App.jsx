import React, { useState } from 'react';
import { getMainFieldForSubfield } from './lib/utils';
import { useFieldData, useOverallRanking, useMainfieldRankings } from './hooks/useFieldData';
import fieldsData from './data/fields.json';
import Header from './components/Header';
import MainContent from './components/MainContent';
import UniversityModal from './components/UniversityModal';
import './App.css';

export default function App() {
  const uniqueFields = fieldsData.fields || [];
  const [selectedFields, setSelectedFields] = useState(uniqueFields.slice());
  const [selectedUni, setSelectedUni] = useState(null);
  const [open, setOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const { 
    ranking, 
    authorsByUniversity, 
    uniFieldContrib, 
    loading 
  } = useFieldData(selectedFields);
  
  const overallRanking = useOverallRanking();
  const mainfieldRankings = useMainfieldRankings(selectedFields);

  const openAuthors = (uni) => { setSelectedUni(uni); setOpen(true); };
  const closeAuthors = () => { setOpen(false); setSelectedUni(null); };

  const handleSearchChange = (value) => {
    setSearchTerm(value);
  };

  return (
    <div className='min-h-screen'>
      <Header />
      
      <MainContent
        loading={loading}
        selectedFields={selectedFields}
        ranking={ranking}
        searchTerm={searchTerm}
        authorsByUniversity={authorsByUniversity}
        onSearchChange={handleSearchChange}
        onUniversityClick={openAuthors}
        onFieldsChange={setSelectedFields}
      />

      <UniversityModal
        open={open}
        onClose={closeAuthors}
        selectedUni={selectedUni}
        authorsByUniversity={authorsByUniversity}
        uniFieldContrib={uniFieldContrib}
        overallRanking={overallRanking}
        mainfieldRankings={mainfieldRankings}
        getMainFieldForSubfield={getMainFieldForSubfield}
      />
    </div>
  );
}