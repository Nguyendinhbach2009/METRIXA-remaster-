import React, { useState, useMemo, useEffect } from "react";
import PropTypes from "prop-types";
import { getMainFieldForSubfield } from "../lib/utils";
import UniversityCard from "./UniversityCard";

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

export default function ChartComponent({ 
  data = [], 
  pageSize = 10,
  currentPage = 0,
  onUniversityClick = () => {},
  selectedFields = [],
  authorsByUniversity = {},
  mainfieldRankings = {}
}) {
  const page = currentPage;
  const [animatedWidths, setAnimatedWidths] = useState({});
  const [universityUrls, setUniversityUrls] = useState({});

  const rowsAllMemo = useMemo(() => {
    const rowsAll = Array.isArray(data) ? data : [];
    return rowsAll;
  }, [data]);

  const globalMax = useMemo(() => {
    const vals = rowsAllMemo.map(r => Number(r.totalContribution ?? 0));
    return vals.length ? Math.max(...vals) : 1e-6;
  }, [rowsAllMemo]);

  useEffect(() => {
    setAnimatedWidths({});
    
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const newWidths = {};
        const startIdx = page * pageSize;
        const pageRows = rowsAllMemo.slice(startIdx, startIdx + pageSize);
        
        pageRows.forEach((r, idx) => {
          const key = r.university ?? idx;
          const val = Number(r.totalContribution ?? 0);
          const pctOfGlobal = globalMax > 0 ? (val / globalMax) * 100 : 0;
          newWidths[key] = Math.max(2, pctOfGlobal);
        });
        
        setAnimatedWidths(newWidths);
      });
    });
  }, [data, page, pageSize, rowsAllMemo, globalMax]);

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
  const pageRows = rowsAllMemo.slice(startIdx, startIdx + pageSize);

  return (
    <div className="space-y-4">
      {pageRows.length === 0 ? null : (
        <div className="space-y-3">
          {pageRows.map((r, idx) => {
            const rank = r.rank || r.originalRank || (startIdx + idx + 1);
            const val = Number(r.totalContribution ?? 0);
            const pctOfGlobal = globalMax > 0 ? (val / globalMax) * 100 : 0;
            const animationWidth = animatedWidths[r.university ?? idx] ?? 0;

            const universityRanks = [];
            const allMainfieldRankings = mainfieldRankings || {};
            
            const selectedMainFields = [...new Set(
              selectedFields.map(subfield => getMainFieldForSubfield(subfield))
            )].filter(Boolean);
            
            selectedMainFields.forEach((mainField) => {
              const rankingData = allMainfieldRankings[mainField] || [];
              const uniRankData = rankingData.find(uni => uni.university === r.university);
              if (uniRankData && uniRankData.rank && uniRankData.rank <= 25) {
                universityRanks.push({
                  field: mainField,
                  rank: uniRankData.rank
                });
              }
            });
            
            universityRanks.sort((a, b) => a.rank - b.rank);

            return (
              <UniversityCard
                key={r.university ?? idx}
                university={r.university}
                rank={rank}
                contribution={val}
                authorCount={authorsByUniversity[r.university]?.length || 0}
                percentage={pctOfGlobal}
                onClick={() => onUniversityClick(r.university)}
                animationWidth={animationWidth}
                universityUrls={universityUrls}
              />
            );
          })}
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
  authorsByUniversity: PropTypes.object,
  mainfieldRankings: PropTypes.object,
  fieldRankCache: PropTypes.instanceOf(Map)
};