/**
 * ARR Great Reviewers - Main JavaScript
 * Handles site-wide functionality including navigation, search, and enhanced tables
 */

// Global variables
let reviewerDatabase = null;

// Initialize site functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  initializeNavigation();
  initializeNavSearch();
  initializeAnimations();
  loadReviewerDatabase();
});

/**
 * Initialize navigation functionality
 */
function initializeNavigation() {
  // Add active class to current nav item
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('nav a');
  
  navLinks.forEach(link => {
    if (link.getAttribute('href') === currentPath || 
        (currentPath === '/' && link.getAttribute('href') === '/')) {
      link.classList.add('active');
    }
  });

  // Mobile navigation toggle
  const mobileToggle = document.querySelector('.mobile-nav-toggle');
  const nav = document.getElementById('main-nav');
  
  if (mobileToggle && nav) {
    mobileToggle.addEventListener('click', function() {
      nav.classList.toggle('mobile-nav-open');
      const isOpen = nav.classList.contains('mobile-nav-open');
      mobileToggle.setAttribute('aria-expanded', isOpen);
      mobileToggle.textContent = isOpen ? '✕' : '☰';
    });
    
    // Close mobile nav when clicking nav links
    navLinks.forEach(link => {
      link.addEventListener('click', function() {
        nav.classList.remove('mobile-nav-open');
        mobileToggle.setAttribute('aria-expanded', 'false');
        mobileToggle.textContent = '☰';
      });
    });
    
    // Close mobile nav when clicking outside
    document.addEventListener('click', function(e) {
      if (!nav.contains(e.target) && !mobileToggle.contains(e.target)) {
        nav.classList.remove('mobile-nav-open');
        mobileToggle.setAttribute('aria-expanded', 'false');
        mobileToggle.textContent = '☰';
      }
    });
  }
}

/**
 * Initialize navigation search functionality
 */
function initializeNavSearch() {
  const navSearchToggle = document.querySelector('.nav-search-toggle');
  const navSearchDropdown = document.querySelector('.nav-search-dropdown');
  const navSearchInput = document.querySelector('.nav-search-input');
  const navSearchResults = document.querySelector('.nav-search-results');
  let searchTimeout = null;

  if (!navSearchToggle || !navSearchDropdown) return;

  // Toggle search dropdown
  navSearchToggle.addEventListener('click', function(e) {
    e.stopPropagation();
    const isActive = navSearchDropdown.classList.contains('active');
    if (!isActive) {
      navSearchDropdown.classList.add('active');
      navSearchInput.focus();
    } else {
      navSearchDropdown.classList.remove('active');
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', function(e) {
    if (!navSearchDropdown.contains(e.target) && !navSearchToggle.contains(e.target)) {
      navSearchDropdown.classList.remove('active');
    }
  });

  // Add escape key handling
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && navSearchDropdown.classList.contains('active')) {
      navSearchDropdown.classList.remove('active');
    }
  });

  // Add mobile overlay for search
  if (window.innerWidth <= 768 && navSearchDropdown) {
    const overlay = document.createElement('div');
    overlay.className = 'search-overlay';
    overlay.style.cssText = 'position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1099; display: none;';
    document.body.appendChild(overlay);

    // Update toggle click handler for mobile
    navSearchToggle.addEventListener('click', function() {
      overlay.style.display = navSearchDropdown.classList.contains('active') ? 'block' : 'none';
    });

    overlay.addEventListener('click', function() {
      navSearchDropdown.classList.remove('active');
      overlay.style.display = 'none';
    });
  }

  // Handle search input
  if (navSearchInput) {
    navSearchInput.addEventListener('input', function(e) {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchReviewers(e.target.value, navSearchResults);
      }, 300);
    });

    // Handle enter key
    navSearchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        const firstResult = navSearchResults.querySelector('.nav-search-result');
        if (firstResult) {
          window.location.href = firstResult.href;
        }
      }
    });
  }
}

/**
 * Initialize animations and intersection observers
 */
function initializeAnimations() {
  // Add smooth scroll behavior
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
  
  // Add intersection observer for fade-in animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };
  
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);
  
  // Observe all elements with animate-fade-in class
  document.querySelectorAll('.animate-fade-in').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(el);
  });
}

/**
 * Load reviewer database for search functionality
 */
function loadReviewerDatabase() {
  fetch('/data/reviewers_database.json')
    .then(r => r.json())
    .then(data => {
      reviewerDatabase = data;
    })
    .catch(err => console.error('Failed to load reviewer database:', err));
}

/**
 * Search functionality for reviewers
 * @param {string} query - Search query
 * @param {HTMLElement} resultsContainer - Container to display results
 */
function searchReviewers(query, resultsContainer) {
  if (!reviewerDatabase || !query.trim()) {
    resultsContainer.innerHTML = '';
    return;
  }

  const searchTerm = query.toLowerCase();
  const results = [];

  // Search through reviewer database
  for (const [openreviewId, reviewer] of Object.entries(reviewerDatabase)) {
    if (reviewer.name.toLowerCase().includes(searchTerm) || 
        (reviewer.institution && reviewer.institution.toLowerCase().includes(searchTerm))) {
      results.push({
        id: openreviewId,
        name: reviewer.name,
        institution: reviewer.institution,
        recognized: reviewer.total_recognized,
        rate: reviewer.recognition_rate
      });
    }
    if (results.length >= 10) break; // Limit results
  }

  // Display results
  if (results.length === 0) {
    resultsContainer.innerHTML = '<div class="nav-search-no-results">No reviewers found</div>';
  } else {
    resultsContainer.innerHTML = results.map(r => {
      const urlSafeId = r.id.replace('~', '').replace(/[\/\\]/g, '-');
      const initials = r.name.split(' ').map(n => n[0]).join('').toUpperCase();
      return `
        <a href="/reviewer/${urlSafeId}/" class="nav-search-result">
          <div class="nav-search-result-icon">${initials}</div>
          <div class="nav-search-result-info">
            <div class="nav-search-result-name">${r.name}</div>
            <div class="nav-search-result-institution">${r.institution || 'Unknown Institution'}</div>
          </div>
        </a>
      `;
    }).join('');
  }
}

/**
 * Add loading animation for data fetches
 * @param {string} elementId - ID of element to show loading in
 */
function showLoading(elementId) {
  const element = document.getElementById(elementId);
  if (element) {
    element.innerHTML = `
      <div style="display: flex; justify-content: center; align-items: center; height: 100%; min-height: 200px;">
        <div style="width: 40px; height: 40px; border: 3px solid var(--border-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1s linear infinite;"></div>
      </div>
    `;
  }
}

/**
 * Enhanced table functionality with mobile card view
 * @param {string} tableId - ID of the table
 * @param {Object} config - Configuration options
 */
function makeEnhancedTable(tableId, config = {}) {
  const table = document.getElementById(tableId);
  if (!table) return;
  
  const container = table.closest('.table-container');
  let tableData = [];
  let filteredData = [];
  let currentView = 'table';
  let currentSort = { column: -1, direction: 'asc' };
  let visibleColumns = new Set();
  
  // Detect table type and create appropriate column toggles
  const headers = Array.from(table.querySelectorAll('thead th'));
  const headerTexts = headers.map(h => h.textContent.toLowerCase());
  
  // Institution table: first column after rank should be "Institution" (not reviewer name)
  // For reviewer tables, we should see "reviewer" in headers, and Institution should NOT be the second column
  const hasReviewerHeaders = headerTexts.some(h => h.includes('reviewer'));
  const isInstitutionTable = !hasReviewerHeaders && headerTexts[1] && headerTexts[1].includes('institution');
  
  
  let columnToggles = '';
  if (isInstitutionTable) {
    columnToggles = `
      <span class="column-toggle active" data-column="0">🏆 Rank</span>
      <span class="column-toggle active" data-column="1">🏛️ Institution</span>
      <span class="column-toggle active" data-column="2,3,4,5">📊 Metrics</span>
    `;
  } else {
    // Check the number of columns to determine correct grouping
    const numColumns = headers.length;
    if (numColumns === 5) {
      // Index page table: Rank, Reviewer, Institution, Great Reviews, Total Reviews
      columnToggles = `
        <span class="column-toggle active" data-column="0">🏆 Rank</span>
        <span class="column-toggle active" data-column="1">👤 Name</span>
        <span class="column-toggle active" data-column="2">🏛️ Institution</span>
        <span class="column-toggle active" data-column="3,4">📊 Metrics</span>
      `;
    } else {
      // Full reviewers page table: Rank, Reviewer Name, Institution, Rewarded Reviews, Recognized Reviews, Recognition Rate
      columnToggles = `
        <span class="column-toggle active" data-column="0">🏆 Rank</span>
        <span class="column-toggle active" data-column="1">👤 Name</span>
        <span class="column-toggle active" data-column="2">🏛️ Institution</span>
        <span class="column-toggle active" data-column="3,4,5">📊 Metrics</span>
      `;
    }
  }
  
  // Create enhanced controls
  const controlsHtml = `
    <div class="table-controls">
      <input type="text" class="table-search" placeholder="Search by ${isInstitutionTable ? 'institution' : 'name, institution'}, or other fields..." />
      <div class="view-toggle">
        <button data-view="table" class="active">📊 Table</button>
        <button data-view="cards">📋 Cards</button>
      </div>
      <div class="column-toggles">
        ${columnToggles}
      </div>
    </div>
  `;
  
  container.insertAdjacentHTML('afterbegin', controlsHtml);
  
  // Initialize visible columns (all visible by default)
  headers.forEach((_, index) => visibleColumns.add(index));
  
  // Create cards container
  const cardsContainer = document.createElement('div');
  cardsContainer.className = 'cards-container';
  container.appendChild(cardsContainer);
  
  // Column toggle functionality
  function toggleColumns(columnIndices, isActive) {
    columnIndices.forEach(colIndex => {
      const thElement = table.querySelector(`thead th:nth-child(${colIndex + 1})`);
      const tdElements = table.querySelectorAll(`tbody td:nth-child(${colIndex + 1})`);
      
      if (thElement) {
        thElement.style.display = isActive ? '' : 'none';
      }
      tdElements.forEach(td => {
        td.style.display = isActive ? '' : 'none';
      });
      
      if (isActive) {
        visibleColumns.add(colIndex);
      } else {
        visibleColumns.delete(colIndex);
      }
    });
  }
  
  // Extract table data
  function extractTableData() {
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    tableData = rows.map(row => {
      const cells = Array.from(row.cells);
      return {
        element: row,
        rank: cells[0]?.textContent?.trim() || '',
        name: cells[1]?.textContent?.trim() || '',
        institution: cells[2]?.textContent?.trim() || '',
        metric1: cells[3]?.textContent?.trim() || '',
        metric2: cells[4]?.textContent?.trim() || '',
        metric3: cells[5]?.textContent?.trim() || '',
        searchText: cells.map(cell => cell.textContent?.trim() || '').join(' ').toLowerCase()
      };
    });
    filteredData = [...tableData];
  }
  
  // Search functionality
  function handleSearch(query) {
    const searchTerm = query.toLowerCase();
    filteredData = tableData.filter(item => item.searchText.includes(searchTerm));
    
    if (currentView === 'table') {
      updateTableView();
    } else {
      updateCardView();
    }
  }
  
  // Update table view
  function updateTableView() {
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    
    if (filteredData.length === 0) {
      tbody.innerHTML = '<tr><td colspan="100%" class="no-results">No results found</td></tr>';
      return;
    }
    
    filteredData.forEach(item => {
      tbody.appendChild(item.element);
    });
  }
  
  // Update card view
  function updateCardView() {
    cardsContainer.innerHTML = '';
    
    if (filteredData.length === 0) {
      cardsContainer.innerHTML = '<div class="no-results">No results found</div>';
      return;
    }
    
    filteredData.forEach((item, index) => {
      const rankClass = index === 0 ? 'rank-1' : index === 1 ? 'rank-2' : index === 2 ? 'rank-3' : '';
      const recognitionRate = item.metric3.includes('%') ? parseFloat(item.metric3.replace('%', '')) || 0 : 0;
      
      // Adapt card content based on table type
      let title, subtitle, metrics;
      if (isInstitutionTable) {
        title = item.institution;
        subtitle = `${item.metric1} reviewers recognized`;
        metrics = `
          <div class="card-metric">
            <span class="card-metric-label">Total Reviewers</span>
            <span class="card-metric-value">${item.metric1}</span>
          </div>
          <div class="card-metric">
            <span class="card-metric-label">Total Reviews</span>
            <span class="card-metric-value">${item.metric2}</span>
          </div>
          <div class="card-metric">
            <span class="card-metric-label">Recognized Reviews</span>
            <span class="card-metric-value">${item.metric3}</span>
          </div>
        `;
      } else {
        title = item.name;
        subtitle = item.institution;
        metrics = `
          <div class="card-metric">
            <span class="card-metric-label">Total Reviews</span>
            <span class="card-metric-value">${item.metric1}</span>
          </div>
          <div class="card-metric">
            <span class="card-metric-label">Recognized</span>
            <span class="card-metric-value">${item.metric2}</span>
          </div>
          <div class="card-metric">
            <span class="card-metric-label">Recognition Rate</span>
            <div>
              <span class="card-metric-value">${item.metric3}</span>
              <div class="card-metric-bar">
                <div class="progress-bar">
                  <div class="progress-fill" style="width: ${recognitionRate}%"></div>
                </div>
              </div>
            </div>
          </div>
        `;
      }
      
      const cardHtml = `
        <div class="data-card" style="animation-delay: ${Math.min(index * 0.05, 0.5)}s" data-index="${index}">
          <div class="card-header">
            <div>
              <h3 class="card-title">${title}</h3>
              <p class="card-subtitle">${subtitle}</p>
            </div>
            <div class="card-rank">
              <span class="rank-badge ${rankClass}">${item.rank}</span>
            </div>
          </div>
          <div class="card-content">
            ${metrics}
          </div>
        </div>
      `;
      cardsContainer.insertAdjacentHTML('beforeend', cardHtml);
    });
    
    // Add swipe support to cards
    addSwipeSupport();
  }
  
  // Add swipe support for mobile card interactions
  function addSwipeSupport() {
    const cards = cardsContainer.querySelectorAll('.data-card');
    
    cards.forEach(card => {
      let startX = 0;
      let startY = 0;
      let currentX = 0;
      let currentY = 0;
      let isDragging = false;
      
      // Touch start
      card.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isDragging = true;
        card.style.transition = 'none';
      }, { passive: true });
      
      // Touch move
      card.addEventListener('touchmove', (e) => {
        if (!isDragging) return;
        
        currentX = e.touches[0].clientX;
        currentY = e.touches[0].clientY;
        
        const diffX = currentX - startX;
        const diffY = currentY - startY;
        
        // Only handle horizontal swipes
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 10) {
          e.preventDefault();
          
          // Add subtle card movement feedback
          const translateX = Math.max(-50, Math.min(50, diffX * 0.3));
          card.style.transform = 'translateX(' + translateX + 'px)';
          
          // Add visual feedback
          if (Math.abs(diffX) > 30) {
            card.style.backgroundColor = diffX > 0 ? 
              'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)';
          }
        }
      }, { passive: false });
      
      // Touch end
      card.addEventListener('touchend', (e) => {
        if (!isDragging) return;
        
        const diffX = currentX - startX;
        const diffY = currentY - startY;
        
        // Reset card position and style
        card.style.transition = 'all 0.3s ease';
        card.style.transform = '';
        card.style.backgroundColor = '';
        
        // Handle swipe actions
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 80) {
          if (diffX > 0) {
            // Right swipe - show more details
            showCardDetails(card);
          } else {
            // Left swipe - quick actions or favorite
            handleCardAction(card);
          }
        }
        
        isDragging = false;
      }, { passive: true });
      
      // Add subtle hover effect for cards
      card.addEventListener('click', (e) => {
        if (!isDragging) {
          // Add a subtle pulse effect
          card.style.transform = 'scale(0.98)';
          setTimeout(() => {
            card.style.transform = '';
          }, 150);
        }
      });
    });
  }
  
  // Show card details (right swipe action)
  function showCardDetails(card) {
    const index = parseInt(card.dataset.index);
    const item = filteredData[index];
    
    // Create a temporary tooltip or modal with more details
    const tooltip = document.createElement('div');
    tooltip.style.cssText = 
      'position: fixed;' +
      'top: 50%;' +
      'left: 50%;' +
      'transform: translate(-50%, -50%);' +
      'background: var(--bg-primary);' +
      'border: 1px solid var(--primary-color);' +
      'border-radius: 0.75rem;' +
      'padding: 1.5rem;' +
      'box-shadow: var(--shadow-xl);' +
      'z-index: 1000;' +
      'max-width: 90vw;' +
      'opacity: 0;' +
      'transition: opacity 0.3s ease;';
    
    let detailContent;
    if (isInstitutionTable) {
      detailContent = 
        '<h3 style="margin: 0 0 1rem 0; color: var(--primary-color);">🏛️ Institution Details</h3>' +
        '<p><strong>Institution:</strong> ' + item.institution + '</p>' +
        '<p><strong>Rank:</strong> #' + item.rank + '</p>' +
        '<p><strong>Total Reviewers:</strong> ' + item.metric1 + '</p>' +
        '<p><strong>Total Reviews:</strong> ' + item.metric2 + '</p>' +
        '<p><strong>Recognized Reviews:</strong> ' + item.metric3 + '</p>';
    } else {
      detailContent = 
        '<h3 style="margin: 0 0 1rem 0; color: var(--primary-color);">👤 Reviewer Details</h3>' +
        '<p><strong>Name:</strong> ' + item.name + '</p>' +
        '<p><strong>Institution:</strong> ' + item.institution + '</p>' +
        '<p><strong>Rank:</strong> #' + item.rank + '</p>' +
        '<p><strong>Performance:</strong> ' + item.metric3 + ' recognition rate</p>';
    }
    
    tooltip.innerHTML = detailContent +
      '<button onclick="this.parentElement.remove()" style="' +
        'margin-top: 1rem;' +
        'padding: 0.5rem 1rem;' +
        'background: var(--primary-color);' +
        'color: white;' +
        'border: none;' +
        'border-radius: 0.5rem;' +
        'cursor: pointer;' +
      '">Close</button>';
    
    document.body.appendChild(tooltip);
    setTimeout(() => tooltip.style.opacity = '1', 10);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (tooltip.parentElement) {
        tooltip.style.opacity = '0';
        setTimeout(() => tooltip.remove(), 300);
      }
    }, 5000);
  }
  
  // Handle card action (left swipe action)
  function handleCardAction(card) {
    const index = parseInt(card.dataset.index);
    const item = filteredData[index];
    
    // Add a visual feedback
    card.style.borderColor = 'var(--success-color)';
    card.style.background = 'rgba(16, 185, 129, 0.05)';
    
    // Show action feedback
    const feedback = document.createElement('div');
    feedback.style.cssText = 
      'position: absolute;' +
      'top: 50%;' +
      'left: 50%;' +
      'transform: translate(-50%, -50%);' +
      'background: var(--success-color);' +
      'color: white;' +
      'padding: 0.5rem 1rem;' +
      'border-radius: 2rem;' +
      'font-size: 0.875rem;' +
      'font-weight: 500;' +
      'opacity: 0;' +
      'transition: opacity 0.3s ease;' +
      'pointer-events: none;' +
      'z-index: 10;';
    feedback.textContent = '⭐ Bookmarked!';
    
    card.appendChild(feedback);
    setTimeout(() => feedback.style.opacity = '1', 10);
    
    // Reset after animation
    setTimeout(() => {
      card.style.borderColor = '';
      card.style.background = '';
      feedback.remove();
    }, 2000);
  }
  
  // View toggle functionality
  function switchView(view) {
    currentView = view;
    const buttons = container.querySelectorAll('.view-toggle button');
    buttons.forEach(btn => btn.classList.remove('active'));
    container.querySelector(`[data-view="${view}"]`).classList.add('active');
    
    if (view === 'table') {
      table.style.display = 'table';
      cardsContainer.style.display = 'none';
      updateTableView();
    } else {
      table.style.display = 'none';
      cardsContainer.style.display = 'flex';
      updateCardView();
    }
  }
  
  // Auto-switch to cards on mobile
  function checkMobileView() {
    if (window.innerWidth <= 768 && currentView === 'table') {
      switchView('cards');
    }
  }
  
  // Event listeners
  const searchInput = container.querySelector('.table-search');
  searchInput.addEventListener('input', (e) => handleSearch(e.target.value));
  
  const viewButtons = container.querySelectorAll('.view-toggle button');
  viewButtons.forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });
  
  // Column toggle event listeners
  const columnToggleButtons = container.querySelectorAll('.column-toggle');
  columnToggleButtons.forEach(toggle => {
    toggle.addEventListener('click', () => {
      const isActive = toggle.classList.contains('active');
      const columnData = toggle.dataset.column;
      const columnIndices = columnData.split(',').map(idx => parseInt(idx.trim()));
      
      // Toggle visual state
      toggle.classList.toggle('active');
      
      // Toggle columns
      toggleColumns(columnIndices, !isActive);
      
      // Refresh data if needed
      if (currentView === 'table') {
        updateTableView();
      } else {
        updateCardView();
      }
    });
  });
  
  // Initialize
  extractTableData();
  checkMobileView();
  
  // Listen for window resize
  window.addEventListener('resize', checkMobileView);
  
  // Return original sorting function for backward compatibility
  return {
    sort: makeSortable(tableId),
    refresh: extractTableData,
    switchView: switchView
  };
}

/**
 * Table sorting functionality (legacy)
 * @param {string} tableId - ID of the table to make sortable
 */
function makeSortable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  
  const headers = table.querySelectorAll('th.sortable');
  let currentSort = { column: -1, direction: 'asc' };
  
  headers.forEach((header, index) => {
    header.addEventListener('click', () => {
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      
      // Determine sort direction
      let direction = 'asc';
      if (currentSort.column === index && currentSort.direction === 'asc') {
        direction = 'desc';
      }
      
      // Clear all sort indicators
      headers.forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      
      // Add sort indicator to current header
      header.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
      
      // Sort rows
      rows.sort((a, b) => {
        const cellA = a.cells[index];
        const cellB = b.cells[index];
        
        let valueA = cellA.textContent.trim();
        let valueB = cellB.textContent.trim();
        
        // Handle percentage values
        if (valueA.includes('%')) {
          valueA = parseFloat(valueA.replace('%', '')) || 0;
          valueB = parseFloat(valueB.replace('%', '')) || 0;
        }
        // Handle numeric values
        else if (!isNaN(parseFloat(valueA)) && !isNaN(parseFloat(valueB))) {
          valueA = parseFloat(valueA) || 0;
          valueB = parseFloat(valueB) || 0;
        }
        // Handle dash/empty values
        else if (valueA === '-' || valueA === '') {
          valueA = direction === 'asc' ? Infinity : -Infinity;
        }
        else if (valueB === '-' || valueB === '') {
          valueB = direction === 'asc' ? Infinity : -Infinity;
        }
        
        if (direction === 'asc') {
          return valueA > valueB ? 1 : valueA < valueB ? -1 : 0;
        } else {
          return valueA < valueB ? 1 : valueA > valueB ? -1 : 0;
        }
      });
      
      // Reappend sorted rows
      rows.forEach(row => tbody.appendChild(row));
      
      currentSort = { column: index, direction };
    });
  });
}