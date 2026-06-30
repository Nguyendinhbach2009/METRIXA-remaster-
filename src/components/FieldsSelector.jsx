import React from "react";
import PropTypes from "prop-types";
import { Filter, ChevronDown, ChevronRight, Check } from "lucide-react";
import fieldsData from "../data/fields.json";

export default function FieldsSelector({ fields = [], selected = [], setSelected = () => {} }) {
  const [tempSelected, setTempSelected] = React.useState(selected);
  const [expandedFields, setExpandedFields] = React.useState(new Set());

  const mainFields = fieldsData.mainFields || [];
  const subfieldsMap = fieldsData.subfieldsMap || {};

  React.useEffect(() => {
    setTempSelected(selected);
  }, [selected]);

  React.useEffect(() => {
    const selectAllFields = () => {
      const allSubfields = [];
      mainFields.forEach(mainField => {
        const subfields = subfieldsMap[mainField] || [];
        allSubfields.push(...subfields);
      });
      const allFields = [...mainFields, ...allSubfields];
      setTempSelected(allFields);
    };
    selectAllFields();
  }, []);

  const toggleField = (f) => {
    setTempSelected(prevSelected => {
      const newSelected = prevSelected.includes(f)
        ? prevSelected.filter(x => x !== f)
        : [...prevSelected, f];
      return [...newSelected];
    });
  };

  const toggleMainField = (mainField) => {
    const subfields = subfieldsMap[mainField] || [];
    const allSubfieldsSelected = subfields.every(sf => tempSelected.includes(sf));

    setTempSelected(prevSelected => {
      if (allSubfieldsSelected) {
        return prevSelected.filter(f => !subfields.includes(f));
      } else {
        const newSelected = [...prevSelected];
        subfields.forEach(sf => {
          if (!newSelected.includes(sf)) newSelected.push(sf);
        });
        return newSelected;
      }
    });
  };

  const toggleExpand = (mainField) => {
    setExpandedFields(prev => {
      const newSet = new Set(prev);
      if (newSet.has(mainField)) newSet.delete(mainField);
      else newSet.add(mainField);
      return newSet;
    });
  };

  const applyChanges = () => {
    setSelected([...tempSelected]);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') applyChanges();
  };

  const clearAll = () => {
    setTempSelected([]);
    setExpandedFields(new Set());
  };

  const selectAll = () => {
    const allSubfields = [];
    mainFields.forEach(mainField => {
      const subfields = subfieldsMap[mainField] || [];
      allSubfields.push(...subfields);
    });
    const allFields = [...mainFields, ...allSubfields];
    setTempSelected(allFields);
  };

  const isMainFieldSelected = (mainField) => {
    const subfields = subfieldsMap[mainField] || [];
    return subfields.length > 0 && subfields.every(sf => tempSelected.includes(sf));
  };

  const isMainFieldPartiallySelected = (mainField) => {
    const subfields = subfieldsMap[mainField] || [];
    const selectedCount = subfields.filter(sf => tempSelected.includes(sf)).length;
    return selectedCount > 0 && selectedCount < subfields.length;
  };

  return (
    <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] shadow-lg backdrop-blur-sm p-6 sticky top-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-purple-500/20">
          <Filter size={20} className="text-[var(--primary)]" />
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Filter by field
        </h2>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={selectAll}
          className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 transition-colors cursor-pointer border border-purple-500/30"
          style={{ cursor: 'pointer' }}
        >
          Select all
        </button>
        <button
          onClick={clearAll}
          className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg bg-[var(--bg-primary)] text-[var(--text-secondary)] hover:bg-purple-500/10 transition-colors cursor-pointer border border-[var(--border)]"
          style={{ cursor: 'pointer' }}
        >
          Clear
        </button>
      </div>

      {tempSelected.length === 0 && (
        <div className="mb-4 p-3 rounded-lg bg-purple-500/20 border border-purple-500/30">
          <p className="text-xs text-purple-300 leading-relaxed font-medium">
            Select at least one field by clicking on one or more boxes
          </p>
        </div>
      )}

      <div className="mb-4">
        <button
          onClick={applyChanges}
          onKeyDown={handleKeyDown}
          className={`w-full px-4 py-3 text-sm font-medium rounded-lg transition-all duration-300 shadow-lg ${
            tempSelected.length === 0
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:from-purple-500 hover:to-pink-500 cursor-pointer'
          }`}
          disabled={tempSelected.length === 0}
          style={tempSelected.length === 0 ? {} : { cursor: 'pointer' }}
        >
          View results
        </button>
      </div>

      <div className="space-y-1 max-h-[calc(100vh-280px)] overflow-y-auto pr-2" style={{
        scrollbarWidth: 'thin',
        scrollbarColor: '#64748B transparent',
      }}>
        {mainFields.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)] py-4 text-center">
            No fields found
          </p>
        ) : (
          mainFields.map((mainField) => {
            const subfields = subfieldsMap[mainField] || [];
            const isExpanded = expandedFields.has(mainField);
            const isSelected = isMainFieldSelected(mainField);
            const isPartial = isMainFieldPartiallySelected(mainField);
            
            return (
              <div key={mainField} className="space-y-1">
                <div
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-lg transition-all cursor-pointer ${
                    isSelected || isPartial
                      ? 'bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30' 
                      : 'hover:bg-purple-500/10'
                  }`}
                  onClick={() => toggleMainField(mainField)}
                  style={{ cursor: 'pointer' }}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(mainField);
                    }}
                    className="flex-shrink-0 w-7 h-7 flex items-center justify-center hover:bg-purple-500/20 rounded transition-colors cursor-pointer"
                    style={{ cursor: 'pointer' }}
                  >
                    {isExpanded ? (
                      <ChevronDown size={20} className="text-[var(--text-secondary)]" />
                    ) : (
                      <ChevronRight size={20} className="text-[var(--text-secondary)]" />
                    )}
                  </button>

                  <div className="flex items-center gap-3 flex-1">
                    <div
                      className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${
                        isSelected || isPartial
                          ? 'bg-purple-500 border-purple-500'
                          : 'border-gray-600 bg-[var(--bg-primary)]'
                      }`}
                    >
                      {(isSelected || isPartial) && (
                        <Check size={12} className="text-white" strokeWidth={3} />
                      )}
                    </div>
                    <span className={`text-sm font-medium ${
                      isSelected || isPartial ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'
                    }`}>
                      {mainField}
                    </span>
                    {subfields.length > 0 && (
                      <span className="text-xs text-[var(--text-muted)] ml-auto">
                        ({subfields.filter(sf => tempSelected.includes(sf)).length}/{subfields.length})
                      </span>
                    )}
                  </div>
                </div>

                {isExpanded && subfields.length > 0 && (
                  <div className="ml-7 space-y-1">
                    {subfields.map((subfield) => {
                      const isSubfieldSelected = tempSelected.includes(subfield);
                      return (
                        <div
                          key={subfield}
                          onClick={() => toggleField(subfield)}
                          className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                            isSubfieldSelected 
                              ? 'bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30' 
                              : 'hover:bg-purple-500/10'
                          }`}
                          style={{ cursor: 'pointer' }}
                        >
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${
                              isSubfieldSelected
                                ? 'bg-purple-500 border-purple-500'
                                : 'border-gray-600 bg-[var(--bg-primary)]'
                            }`}
                          >
                            {isSubfieldSelected && (
                              <Check size={12} className="text-white" strokeWidth={3} />
                            )}
                          </div>
                          <span className={`text-sm ${
                            isSubfieldSelected ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'
                          }`}>
                            {subfield}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

FieldsSelector.propTypes = {
  fields: PropTypes.arrayOf(PropTypes.string),
  selected: PropTypes.arrayOf(PropTypes.string),
  setSelected: PropTypes.func,
  papers: PropTypes.array,
};
