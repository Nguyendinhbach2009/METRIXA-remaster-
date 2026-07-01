import { useState, useEffect, useCallback } from 'react';
import { getMainFieldForSubfield, getFieldFileName, getMainFieldFolder } from '../lib/utils';
import fieldsData from '../data/fields.json';

export function useFieldData(selectedFields) {
  const [ranking, setRanking] = useState([]);
  const [authorsByUniversity, setAuthorsByUniversity] = useState({});
  const [uniFieldContrib, setUniFieldContrib] = useState({});
  const [fieldRankCache, setFieldRankCache] = useState(new Map());
  const [loading, setLoading] = useState(true);

  const loadFieldData = useCallback(async () => {
    setLoading(true);
    if (selectedFields.length === 0) {
      setRanking([]);
      setAuthorsByUniversity({});
      setUniFieldContrib({});
      setFieldRankCache(new Map());
      setLoading(false);
      return;
    }
    try {
      const fieldDataPromises = selectedFields.map(async (field) => {
        const mainField = getMainFieldForSubfield(field);
        if (!mainField || mainField === field) {
          return { field, data: null };
        }
        const mainFieldFolder = getMainFieldFolder(mainField);
        const fieldFileName = getFieldFileName(field);
        try {
          const module = await import('../data/' + mainFieldFolder + '/' + fieldFileName + '.json');
          return { field, data: module.default };
        } catch (err) {
          return { field, data: null };
        }
      });
      const fieldDataResults = await Promise.all(fieldDataPromises);
      const newFieldRankCache = new Map();
      const mergedAuthorsByUni = {};
      const mergedUniFieldContrib = {};
      const uniContributions = {};
      fieldDataResults.forEach(({ field, data }) => {
        if (!data) return;
        if (data.ranking) {
          data.ranking.forEach((uniData, index) => {
            newFieldRankCache.set(uniData.university + '-' + field, index + 1);
          });
        }
        if (data.authorsByUniversity) {
          Object.entries(data.authorsByUniversity).forEach(([uni, authors]) => {
            mergedAuthorsByUni[uni] = mergedAuthorsByUni[uni] || [];
            mergedAuthorsByUni[uni].push(...authors);
          });
        }
        if (data.uniFieldContrib) {
          Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
            mergedUniFieldContrib[uni] = mergedUniFieldContrib[uni] || {};
            if (fields[field] !== undefined) {
              mergedUniFieldContrib[uni][field] = (mergedUniFieldContrib[uni][field] || 0) + fields[field];
            }
          });
        }
        if (data.uniFieldContrib) {
          Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
            if (fields[field] !== undefined && fields[field] > 0) {
              uniContributions[uni] = uniContributions[uni] || { university: uni, totalContribution: 0, paperCount: 0, authorCount: 0 };
              uniContributions[uni].totalContribution += fields[field];
              const uniRankData = data.ranking?.find(r => r.university === uni);
              if (uniRankData) { uniContributions[uni].paperCount += uniRankData.paperCount || 0; uniContributions[uni].authorCount += uniRankData.authorCount || 0; }
            }
          });
        }
      });
      Object.keys(mergedAuthorsByUni).forEach(uni => {
        const authorMap = {};
        mergedAuthorsByUni[uni].forEach(author => {
          authorMap[author.author] = authorMap[author.author] || { author: author.author, contribution: 0 };
          authorMap[author.author].contribution += author.contribution || 0;
        });
        const totalContrib = Object.values(authorMap).reduce((sum, a) => sum + a.contribution, 0);
        mergedAuthorsByUni[uni] = Object.values(authorMap).map(a => ({ ...a, percent: totalContrib > 0 ? a.contribution / totalContrib : 0 }));
      });
      const mergedRanking = Object.values(uniContributions).sort((a, b) => b.totalContribution - a.totalContribution).map((uni, index) => ({ ...uni, originalRank: index + 1 }));
      setRanking(mergedRanking);
      setAuthorsByUniversity(mergedAuthorsByUni);
      setUniFieldContrib(mergedUniFieldContrib);
      setFieldRankCache(newFieldRankCache);
    } catch (error) {
      console.error('Error loading field data:', error);
    }
    setLoading(false);
  }, [selectedFields]);
  useEffect(() => { loadFieldData(); }, [loadFieldData]);
  return { ranking, authorsByUniversity, uniFieldContrib, fieldRankCache, loading };
}
export function useOverallRanking() {
  const [overallRanking, setOverallRanking] = useState([]);
  useEffect(() => {
    const loadOverallRanking = async () => {
      try {
        const allFields = fieldsData.fields || [];
        const fieldDataResults = await Promise.all(allFields.map(async (field) => {
          const mainField = getMainFieldForSubfield(field);
          if (!mainField || mainField === field) return { field, data: null };
          try { return { field, data: (await import('../data/' + getMainFieldFolder(mainField) + '/' + getFieldFileName(field) + '.json')).default }; }
          catch { return { field, data: null }; }
        }));
        const allContributions = {};
        fieldDataResults.forEach(({ field, data }) => {
          if (!data?.uniFieldContrib) return;
          Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
            allContributions[uni] = allContributions[uni] || { university: uni, totalContribution: 0, paperCount: 0, authorCount: 0 };
            if (fields[field] !== undefined) allContributions[uni].totalContribution += fields[field] || 0;
            const uniRankData = data.ranking?.find(r => r.university === uni);
            if (uniRankData) { allContributions[uni].paperCount += uniRankData.paperCount || 0; allContributions[uni].authorCount += uniRankData.authorCount || 0; }
          });
        });
        setOverallRanking(Object.values(allContributions).sort((a, b) => b.totalContribution - a.totalContribution).map((uni, index) => ({ ...uni, originalRank: index + 1 })));
      } catch (error) { console.error('Error loading overall ranking data:', error); setOverallRanking([]); }
    };
    loadOverallRanking();
  }, []);
  return overallRanking;
}
export function useMainfieldRankings(selectedFields) {
  const [mainfieldRankings, setMainfieldRankings] = useState({});
  useEffect(() => {
    const loadMainfieldRankings = async () => {
      if (selectedFields.length === 0) { setMainfieldRankings({}); return; }
      try {
        const fieldsByMainField = {};
        selectedFields.forEach(field => { const mainField = getMainFieldForSubfield(field); if (mainField) { fieldsByMainField[mainField] = fieldsByMainField[mainField] || []; fieldsByMainField[mainField].push(field); } });
        const rankingResults = await Promise.all(Object.keys(fieldsByMainField).map(async (mainField) => { try { return { mainField, data: (await import('../data/rankings/' + getFieldFileName(mainField) + '_rankings.json')).default }; } catch (err) { return { mainField, data: null }; } }));
        const rankings = {};
        rankingResults.forEach(({ mainField, data }) => { if (data?.mainfieldRankings?.[mainField]) { rankings[mainField] = data.mainfieldRankings[mainField]; } });
        setMainfieldRankings(rankings);
      } catch (error) { console.error('Error loading mainfield rankings:', error); setMainfieldRankings({}); }
    };
    loadMainfieldRankings();
  }, [selectedFields]);
  return mainfieldRankings;
}
