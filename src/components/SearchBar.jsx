import React from "react";
import PropTypes from "prop-types";
import { Search, X } from "lucide-react";

export default function SearchBar({ searchTerm, onSearchChange }) {
  return (
    <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
        <Search size={18} className="text-[var(--text-secondary)]" />
      </div>
      <input
        type="text"
        placeholder="Search for university affiliation..."
        value={searchTerm}
        onChange={(e) => onSearchChange(e.target.value)}
        className="w-full pl-11 pr-4 py-3 bg-[var(--surface)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition-all duration-200"
      />
      {searchTerm && (
        <button
          onClick={() => onSearchChange("")}
          className="absolute inset-y-0 right-0 pr-4 flex items-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <X size={18} />
        </button>
      )}
    </div>
  );
}

SearchBar.propTypes = {
  searchTerm: PropTypes.string,
  onSearchChange: PropTypes.func.isRequired
};