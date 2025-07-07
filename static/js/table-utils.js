/**
 * Common table utilities for ARR Great Reviewers
 * Provides reusable functionality for populating and managing tables
 */

/**
 * Creates a progress bar cell with percentage display
 * @param {number} numerator - The numerator value (e.g., recognized reviews)
 * @param {number} denominator - The denominator value (e.g., total reviews)
 * @returns {string} HTML string for the progress bar cell
 */
function createProgressBarCell(numerator, denominator) {
  const percentage = denominator > 0 ? ((numerator / denominator) * 100) : 0;
  const displayPercentage = denominator > 0 ? percentage.toFixed(1) + '%' : '-';
  
  return `
    <div style="display: flex; align-items: center; gap: 0.5rem;">
      <div class="progress-bar" style="flex: 1;">
        <div class="progress-fill" style="width: ${Math.min(percentage, 100)}%"></div>
      </div>
      <span style="font-size: 0.875rem; color: var(--text-secondary);">${displayPercentage}</span>
    </div>
  `;
}

/**
 * Creates a rank badge with appropriate styling
 * @param {number} rank - The rank (1-based)
 * @returns {string} HTML string for the rank badge
 */
function createRankBadge(rank) {
  const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : '';
  return `<span class="rank-badge ${rankClass}">${rank}</span>`;
}

/**
 * Creates a linked or unlinked name cell
 * @param {string} name - The display name
 * @param {string|null} url - The URL to link to, or null for no link
 * @param {string} linkClass - CSS class for the link
 * @returns {string} HTML string for the name cell
 */
function createNameCell(name, url, linkClass = '') {
  const displayName = name || 'Anonymous';
  
  if (url) {
    return `<strong><a href="${url}" class="${linkClass}">${displayName}</a></strong>`;
  } else {
    return `<strong>${displayName}</strong>`;
  }
}

/**
 * Creates an animated table row
 * @param {number} index - Row index for animation delay
 * @param {string} content - HTML content for the row
 * @returns {string} HTML string for the complete table row
 */
function createAnimatedRow(index, content) {
  const animationDelay = Math.min(index * 0.02, 0.5);
  return `
    <tr class="animate-fade-in" style="animation-delay: ${animationDelay}s">
      ${content}
    </tr>
  `;
}

/**
 * Populates a table body with data
 * @param {string} tableBodyId - ID of the table body element
 * @param {Array} data - Array of data objects
 * @param {Function} rowRenderer - Function that takes (item, index) and returns row HTML
 * @param {number} maxRows - Maximum number of rows to display
 */
function populateTable(tableBodyId, data, rowRenderer, maxRows = 100) {
  const tbody = document.getElementById(tableBodyId);
  if (!tbody) {
    console.error(`Table body with ID "${tableBodyId}" not found`);
    return;
  }
  
  const limitedData = data.slice(0, maxRows);
  tbody.innerHTML = limitedData.map((item, index) => 
    createAnimatedRow(index, rowRenderer(item, index + 1))
  ).join('');
  
  // Make table enhanced (if function exists)
  if (typeof makeEnhancedTable === 'function') {
    const tableElement = tbody.closest('table');
    if (tableElement && tableElement.id) {
      makeEnhancedTable(tableElement.id);
    }
  } else if (typeof makeSortable === 'function') {
    const tableElement = tbody.closest('table');
    if (tableElement && tableElement.id) {
      makeSortable(tableElement.id);
    }
  }
}

/**
 * Standard sorting functions for common data types
 */
const TableSorters = {
  /**
   * Sort by recognition count with tie-breaking
   * @param {Array} data - Array of objects with recognized, reviewed properties
   * @returns {Array} Sorted array
   */
  byRecognitionCount: function(data) {
    return data.sort((a, b) => {
      // Primary: Recognition count (descending)
      if (b.recognized !== a.recognized) return b.recognized - a.recognized;
      
      // Tie-breaker 1: Recognition rate (descending)
      const rateA = a.reviewed > 0 ? a.recognized / a.reviewed : 0;
      const rateB = b.reviewed > 0 ? b.recognized / b.reviewed : 0;
      if (rateB !== rateA) return rateB - rateA;
      
      // Tie-breaker 2: Total reviews (descending)
      return b.reviewed - a.reviewed;
    });
  },

  /**
   * Sort by recognition rate with tie-breaking
   * @param {Array} data - Array of objects with recognized, reviewed properties
   * @returns {Array} Sorted array
   */
  byRecognitionRate: function(data) {
    return data.sort((a, b) => {
      // Primary: Recognition rate (descending)
      const rateA = a.reviewed > 0 ? a.recognized / a.reviewed : 0;
      const rateB = b.reviewed > 0 ? b.recognized / b.reviewed : 0;
      if (rateB !== rateA) return rateB - rateA;
      
      // Tie-breaker 1: Recognition count (descending)
      if (b.recognized !== a.recognized) return b.recognized - a.recognized;
      
      // Tie-breaker 2: Total reviews (descending)
      return b.reviewed - a.reviewed;
    });
  }
};

/**
 * URL utilities for generating profile links
 */
const URLUtils = {
  /**
   * Converts an OpenReview ID to a URL-safe format
   * @param {string} openreviewId - OpenReview ID (e.g., "~First_LastN")
   * @returns {string} URL-safe ID (e.g., "First_LastN")
   */
  openreviewIdToUrl: function(openreviewId) {
    return openreviewId.replace('~', '').replace(/[/\\]/g, '-');
  },

  /**
   * Creates a reviewer profile URL
   * @param {string} urlSafeId - URL-safe reviewer ID
   * @returns {string} Complete reviewer profile URL
   */
  reviewerProfileUrl: function(urlSafeId) {
    return `/reviewer/${urlSafeId}/`;
  },

  /**
   * Creates an institution profile URL
   * @param {string} urlSafeId - URL-safe institution ID
   * @returns {string} Complete institution profile URL
   */
  institutionProfileUrl: function(urlSafeId) {
    return `/institution/${urlSafeId}/`;
  }
};

/**
 * Data processing utilities
 */
const DataUtils = {
  /**
   * Converts string values to numbers for consistent processing
   * @param {Object} item - Data item with string numeric values
   * @returns {Object} Item with converted numeric values
   */
  normalizeNumericFields: function(item) {
    return {
      ...item,
      reviewed: parseInt(item.reviewed) || 0,
      recognized: parseInt(item.recognized) || 0,
      percentage: parseFloat(item.percentage) || 0
    };
  },

  /**
   * Processes an array of data items
   * @param {Array} data - Array of raw data items
   * @returns {Array} Array of normalized data items
   */
  normalizeDataArray: function(data) {
    return data.map(this.normalizeNumericFields);
  },

  /**
   * Filters data by minimum review count
   * @param {Array} data - Array of data items
   * @param {number} minReviews - Minimum number of reviews required
   * @returns {Array} Filtered array
   */
  filterByMinReviews: function(data, minReviews = 3) {
    return data.filter(item => (item.reviewed || 0) >= minReviews);
  }
};

/**
 * Error handling utilities for table operations
 */
const TableErrorHandlers = {
  /**
   * Displays an error message in a table body
   * @param {string} tableBodyId - ID of the table body element
   * @param {string} message - Error message to display
   * @param {number} colspan - Number of columns to span
   */
  showTableError: function(tableBodyId, message, colspan = 6) {
    const tbody = document.getElementById(tableBodyId);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="${colspan}" style="text-align: center; padding: 2rem; color: var(--text-secondary);">
            ${message}
          </td>
        </tr>
      `;
    }
  },

  /**
   * Displays a loading message in a table body
   * @param {string} tableBodyId - ID of the table body element
   * @param {string} message - Loading message to display
   * @param {number} colspan - Number of columns to span
   */
  showTableLoading: function(tableBodyId, message = 'Loading data...', colspan = 6) {
    const tbody = document.getElementById(tableBodyId);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="${colspan}" style="text-align: center; padding: 2rem;">
            ${message}
          </td>
        </tr>
      `;
    }
  }
};

// Export utilities for use in other modules
window.TableUtils = {
  createProgressBarCell,
  createRankBadge,
  createNameCell,
  createAnimatedRow,
  populateTable,
  TableSorters,
  URLUtils,
  DataUtils,
  TableErrorHandlers
};