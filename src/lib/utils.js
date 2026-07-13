import fieldsData from "../data/fields.json";

export function getMainFieldForSubfield(subfield) {
  const subfieldsMap = fieldsData.subfieldsMap || {};
  const normalizedSubfield = subfield.toLowerCase();
  
  for (const [mainFieldKey] of Object.entries(subfieldsMap)) {
    if (mainFieldKey.toLowerCase() === normalizedSubfield) {
      return mainFieldKey;
    }
  }
  
  for (const [mainField, subfields] of Object.entries(subfieldsMap)) {
    const foundSubfield = subfields.find(s => s.toLowerCase() === normalizedSubfield);
    if (foundSubfield) {
      return mainField;
    }
  }
  
  return null;
}

export function getFieldFileName(field) {
  return field
    .replace(/ /g, '_')
    .replace(/\//g, '_')
    .replace(/&/g, 'and')
    .replace(/[–—-]/g, '-')
    .toLowerCase();
}

export function getMainFieldFolder(mainField) {
  return mainField.replace(/\s+/g, '_').toLowerCase();
}

export function mergeAuthorsByUniversity(fieldDataResults) {
  const mergedAuthorsByUni = {};
  
  fieldDataResults.forEach(({ data }) => {
    if (!data?.authorsByUniversity) return;
    
    Object.entries(data.authorsByUniversity).forEach(([uni, authors]) => {
      if (!mergedAuthorsByUni[uni]) {
        mergedAuthorsByUni[uni] = [];
      }
      mergedAuthorsByUni[uni].push(...authors);
    });
  });
  
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
    
    const totalContrib = Object.values(authorMap).reduce((sum, a) => sum + a.contribution, 0);
    mergedAuthorsByUni[uni] = Object.values(authorMap).map(a => ({
      ...a,
      percent: totalContrib > 0 ? a.contribution / totalContrib : 0
    }));
  });
  
  return mergedAuthorsByUni;
}

export function createFieldRankCache(fieldDataResults) {
  const newFieldRankCache = new Map();
  
  fieldDataResults.forEach(({ field, data }) => {
    if (!data?.ranking) return;
    
    data.ranking.forEach((uniData, index) => {
      const key = `${uniData.university}-${field}`;
      newFieldRankCache.set(key, index + 1);
    });
  });
  
  return newFieldRankCache;
}

export function aggregateUniContributions(fieldDataResults) {
  const uniContributions = {};
  
  fieldDataResults.forEach(({ field, data }) => {
    if (!data?.uniFieldContrib) return;
    
    Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
      if (fields[field] !== undefined && fields[field] > 0) {
        if (!uniContributions[uni]) {
          uniContributions[uni] = {
            university: uni,
            totalContribution: 0,
            paperCount: 0,
            authorCount: 0
          };
        }
        uniContributions[uni].totalContribution += fields[field];
        
        const uniRankData = data.ranking?.find(r => r.university === uni);
        if (uniRankData) {
          uniContributions[uni].paperCount += uniRankData.paperCount || 0;
          uniContributions[uni].authorCount += uniRankData.authorCount || 0;
        }
      }
    });
  });
  
  return Object.values(uniContributions)
    .sort((a, b) => b.totalContribution - a.totalContribution)
    .map((uni, index) => ({
      ...uni,
      originalRank: index + 1
    }));
}

export function createUniFieldContrib(fieldDataResults) {
  const mergedUniFieldContrib = {};
  
  fieldDataResults.forEach(({ field, data }) => {
    if (!data?.uniFieldContrib) return;
    
    Object.entries(data.uniFieldContrib).forEach(([uni, fields]) => {
      if (!mergedUniFieldContrib[uni]) {
        mergedUniFieldContrib[uni] = {};
      }
      if (fields[field] !== undefined) {
        mergedUniFieldContrib[uni][field] = 
          (mergedUniFieldContrib[uni][field] || 0) + fields[field];
      }
    });
  });
  
  return mergedUniFieldContrib;
}

export function formatNumber(value, decimals = 4) {
  return Number(value ?? 0).toFixed(decimals);
}