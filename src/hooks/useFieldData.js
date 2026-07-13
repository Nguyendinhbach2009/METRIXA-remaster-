import { useState, useEffect, useCallback, useRef } from 'react';
import { getMainFieldForSubfield, getFieldFileName, getMainFieldFolder } from '../lib/utils';
import fieldsData from '../data/fields.json';

const subfieldsMap = fieldsData.subfieldsMap || {};

async function loadJsonData(path) {
  if (import.meta.env.DEV) {
    const module = await import(/* @vite-ignore */ `../data/${path}.json`);
    return module.default;
  } else {
    const response = await fetch(`${import.meta.env.BASE_URL}data/${path}.json`);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${path}.json: ${response.statusText}`);
    }
    return await response.json();
  }
}

const getAllSubfields = () => {
  const all = [];
  fieldsData.mainFields.forEach(mf => {
    (subfieldsMap[mf] || []).forEach(sf => all.push(sf));
  });
  return all;
};

export function useFieldData(selectedFields) {
  const [ranking, setRanking] = useState([]);
  const [authorsByUniversity, setAuthorsByUniversity] = useState({});
  const [uniFieldContrib, setUniFieldContrib] = useState({});
  const [fieldRankCache, setFieldRankCache] = useState(new Map());
  const [loading, setLoading] = useState(true);
  const prevSelectedRef = useRef(null);
  const fieldDataCache = useRef(new Map());
  const allSubfieldsRef = useRef(getAllSubfields());

  const isAllSelected = (fields) => {
    const all = allSubfieldsRef.current;
    return fields.length === all.length && all.every(sf => fields.includes(sf));
  };

  const getFieldData = useCallback(async (field) => {
    const cacheKey = 'field|' + field;
    if (fieldDataCache.current.has(cacheKey)) {
      return fieldDataCache.current.get(cacheKey);
    }
    
    const mainField = getMainFieldForSubfield(field);
    if (!mainField || mainField === field) return { ranking: [], authors: {} };
    
    const fieldFileName = getFieldFileName(field);
    try {
      const data = await loadJsonData('rankings/' + getMainFieldFolder(mainField) + '/' + fieldFileName);
      const result = { ranking: data.ranking || [], authors: data.authorsByUniversity || {} };
      fieldDataCache.current.set(cacheKey, result);
      return result;
    } catch (err) {
      return { ranking: [], authors: {} };
    }
  }, []);

  const calculateAuthors = useCallback((authorsByUni) => {
    const result = {};
    Object.keys(authorsByUni).forEach(uni => {
      const authorMap = {};
      authorsByUni[uni].forEach(author => {
        authorMap[author.author] = authorMap[author.author] || { author: author.author, contribution: 0 };
        authorMap[author.author].contribution += author.contribution || 0;
      });
      const totalContrib = Object.values(authorMap).reduce((sum, a) => sum + a.contribution, 0);
      result[uni] = Object.values(authorMap).map(a => ({ ...a, percent: totalContrib > 0 ? a.contribution / totalContrib : 0 }));
    });
    return result;
  }, []);

  useEffect(() => {
    if (selectedFields.length === 0) {
      setRanking([]);
      setAuthorsByUniversity({});
      setUniFieldContrib({});
      setFieldRankCache(new Map());
      setLoading(false);
      return;
    }

    const isNowAllSelected = isAllSelected(selectedFields);

    const updateRanking = async () => {
      setLoading(true);
      try {
        if (isNowAllSelected) {
          const overallData = await loadJsonData('rankings/overall_rankings');
          const overall = overallData.ranking || [];
          setRanking(overall);
          setFieldRankCache(new Map(overall.map((uni, idx) => [uni.university, idx + 1])));
          setAuthorsByUniversity(overallData.authorsByUniversity || {});
          setUniFieldContrib(overallData.uniFieldContrib || {});
          setLoading(false);
          return;
        }

        const allSubfields = allSubfieldsRef.current;
        const baseRanking = {};
        const baseAuthors = {};
        const baseFieldContrib = {};

        if (selectedFields.length > allSubfields.length / 2) {
          // Optimization: Start from overall and subtract deselected fields
          const overallData = await loadJsonData('rankings/overall_rankings');
          const overallRanking = overallData.ranking || [];
          
          overallRanking.forEach(uni => {
            baseRanking[uni.university] = uni.totalContribution || 0;
            baseAuthors[uni.university] = {};
            const overallUniAuthors = overallData.authorsByUniversity[uni.university] || [];
            overallUniAuthors.forEach(a => {
              baseAuthors[uni.university][a.author] = a.contribution || 0;
            });
            baseFieldContrib[uni.university] = { ...overallData.uniFieldContrib[uni.university] };
          });

          const deselectedFields = allSubfields.filter(f => !selectedFields.includes(f));

          for (const field of deselectedFields) {
            const fieldData = await getFieldData(field);
            
            // Subtract total contribution
            fieldData.ranking.forEach(uniData => {
              if (baseRanking[uniData.university] !== undefined) {
                baseRanking[uniData.university] -= uniData.totalContribution || 0;
              }
            });
            
            // Subtract author contributions
            Object.keys(fieldData.authors).forEach(uni => {
              if (baseAuthors[uni]) {
                fieldData.authors[uni].forEach(a => {
                  if (baseAuthors[uni][a.author] !== undefined) {
                    baseAuthors[uni][a.author] -= a.contribution || 0;
                  }
                });
              }
            });
            
            // Subtract subfield contributions
            Object.keys(baseFieldContrib).forEach(uni => {
              if (baseFieldContrib[uni][field] !== undefined) {
                delete baseFieldContrib[uni][field];
              }
            });
          }
        } else {
          // Start from empty and add selected fields
          for (const field of selectedFields) {
            const fieldData = await getFieldData(field);
            
            // Add total contribution
            fieldData.ranking.forEach(uniData => {
              baseRanking[uniData.university] = (baseRanking[uniData.university] || 0) + (uniData.totalContribution || 0);
            });
            
            // Add author contributions
            Object.keys(fieldData.authors).forEach(uni => {
              baseAuthors[uni] = baseAuthors[uni] || {};
              fieldData.authors[uni].forEach(a => {
                baseAuthors[uni][a.author] = (baseAuthors[uni][a.author] || 0) + (a.contribution || 0);
              });
            });
            
            // Add subfield contributions
            fieldData.ranking.forEach(uniData => {
              const uni = uniData.university;
              baseFieldContrib[uni] = baseFieldContrib[uni] || {};
              baseFieldContrib[uni][field] = (baseFieldContrib[uni][field] || 0) + (uniData.totalContribution || 0);
            });
          }
        }

        // Format and sort the ranking list
        const mergedRanking = Object.entries(baseRanking)
          .map(([university, totalContribution]) => ({
            university,
            totalContribution,
            paperCount: 0,
            authorCount: 0
          }))
          .filter(uni => uni.totalContribution > 0.0001)
          .sort((a, b) => b.totalContribution - a.totalContribution)
          .map((uni, index) => ({ ...uni, originalRank: index + 1 }));

        // Format and percentage author lists
        const formattedAuthors = {};
        Object.keys(baseAuthors).forEach(uni => {
          const authorMap = baseAuthors[uni];
          const sortedAuthors = Object.entries(authorMap)
            .map(([author, contribution]) => ({ author, contribution }))
            .filter(a => a.contribution > 0.0001)
            .sort((a, b) => b.contribution - a.contribution);
            
          const totalContrib = sortedAuthors.reduce((sum, a) => sum + a.contribution, 0);
          formattedAuthors[uni] = sortedAuthors.map(a => ({
            ...a,
            percent: totalContrib > 0 ? a.contribution / totalContrib : 0
          }));
        });

        setRanking(mergedRanking);
        setAuthorsByUniversity(formattedAuthors);
        setUniFieldContrib(baseFieldContrib);
        
        const newCache = new Map();
        mergedRanking.forEach((uni, idx) => {
          newCache.set(uni.university, idx + 1);
        });
        setFieldRankCache(newCache);
      } catch (error) {
        console.error('Error updating ranking:', error);
      }
      setLoading(false);
    };

    updateRanking();
    prevSelectedRef.current = [...selectedFields];
  }, [selectedFields, getFieldData]);

  return { ranking, authorsByUniversity, uniFieldContrib, fieldRankCache, loading };
}

export function useOverallRanking() {
  const [overallRanking, setOverallRanking] = useState([]);
  useEffect(() => {
    const loadOverallRanking = async () => {
      try {
        const data = await loadJsonData('rankings/overall_rankings');
        setOverallRanking(data.ranking || []);
      } catch (error) {
        console.error('Error loading overall ranking data:', error);
        setOverallRanking([]);
      }
    };
    loadOverallRanking();
  }, []);
  return overallRanking;
}

export function useMainfieldRankings(selectedFields) {
  const [mainfieldRankings, setMainfieldRankings] = useState({});
  useEffect(() => {
    const loadMainfieldRankings = async () => {
      if (selectedFields.length === 0) {
        setMainfieldRankings({});
        return;
      }
      try {
        const fieldsByMainField = {};
        selectedFields.forEach(field => {
          const mainField = getMainFieldForSubfield(field);
          if (mainField) {
            fieldsByMainField[mainField] = fieldsByMainField[mainField] || [];
            fieldsByMainField[mainField].push(field);
          }
        });

        const rankingResults = await Promise.all(Object.keys(fieldsByMainField).map(async (mainField) => {
          try {
            const mainFieldFileName = getFieldFileName(mainField);
            const data = await loadJsonData(mainFieldFileName);
            return { mainField, data };
          } catch (err) {
            return { mainField, data: null };
          }
        }));

        const rankings = {};
        rankingResults.forEach(({ mainField, data }) => {
          if (data?.ranking) {
            rankings[mainField] = data.ranking;
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
  return mainfieldRankings;
}