/**
 * ARR Great Reviewers - Index Page JavaScript
 * Handles homepage-specific functionality including profile search and data visualization
 */

// Profile search functionality
let profileDatabase = null;
let profileSearchTimeout = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  initializeProfileSearch();
  loadIndexData();
});

/**
 * Initialize profile search functionality
 */
function initializeProfileSearch() {
  const profileSearchInput = document.getElementById('profile-search-input');
  const profileSearchButton = document.querySelector('.profile-search-button');
  const profileSearchResults = document.getElementById('profile-search-results');

  if (!profileSearchInput) return;

  // Load reviewer database for profile search (reuse global if available)
  if (!reviewerDatabase) {
    fetch('/data/reviewers_database.json')
      .then(r => r.json())
      .then(data => {
        profileDatabase = data;
      })
      .catch(err => console.error('Failed to load reviewer database for profile search:', err));
  } else {
    profileDatabase = reviewerDatabase;
  }

  // Profile search function
  function searchProfiles(query) {
    if (!profileDatabase || !query.trim()) {
      profileSearchResults.innerHTML = '';
      profileSearchResults.classList.remove('active');
      return;
    }

    const searchTerm = query.toLowerCase();
    const results = [];

    // Search through reviewer database
    for (const [openreviewId, reviewer] of Object.entries(profileDatabase)) {
      if (reviewer.name.toLowerCase().includes(searchTerm)) {
        results.push({
          id: openreviewId,
          name: reviewer.name,
          institution: reviewer.institution,
          recognized: reviewer.total_recognized,
          reviewed: reviewer.total_reviewed,
          rate: reviewer.recognition_rate
        });
      }
      if (results.length >= 8) break; // Limit results
    }

    // Display results
    if (results.length === 0) {
      profileSearchResults.innerHTML = '<div class="profile-search-no-results">No reviewers found matching your search</div>';
      profileSearchResults.classList.add('active');
    } else {
      profileSearchResults.innerHTML = results.map(r => {
        const urlSafeId = r.id.replace('~', '').replace(/[\/\\]/g, '-');
        const initials = r.name.split(' ').map(n => n[0]).join('').toUpperCase();
        const recognitionPercent = (r.rate * 100).toFixed(1);
        return `
          <a href="/reviewer/${urlSafeId}/" class="profile-search-result">
            <div class="profile-search-result-avatar">${initials}</div>
            <div class="profile-search-result-info">
              <div class="profile-search-result-name">${r.name}</div>
              <div class="profile-search-result-details">
                <span class="profile-search-result-stat">
                  <strong>${r.recognized}</strong> great reviews
                </span>
                <span class="profile-search-result-stat">
                  <strong>${recognitionPercent}%</strong> recognition rate
                </span>
              </div>
            </div>
          </a>
        `;
      }).join('');
      profileSearchResults.classList.add('active');
    }
  }

  // Handle search input
  profileSearchInput.addEventListener('input', function(e) {
    clearTimeout(profileSearchTimeout);
    profileSearchTimeout = setTimeout(() => {
      searchProfiles(e.target.value);
    }, 300);
  });

  profileSearchInput.addEventListener('focus', function() {
    if (this.value.trim()) {
      searchProfiles(this.value);
    }
  });

  // Handle enter key
  profileSearchInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      const firstResult = profileSearchResults.querySelector('.profile-search-result');
      if (firstResult) {
        window.location.href = firstResult.href;
      }
    }
  });

  // Handle search button click
  if (profileSearchButton) {
    profileSearchButton.addEventListener('click', function() {
      const firstResult = profileSearchResults.querySelector('.profile-search-result');
      if (firstResult) {
        window.location.href = firstResult.href;
      }
    });
  }

  // Close results when clicking outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.profile-finder-search') && !e.target.closest('.profile-search-results')) {
      profileSearchResults.classList.remove('active');
    }
  });
}

/**
 * Load and display index page data
 */
function loadIndexData() {
  // Fetch and display monthly snapshots
  fetch('/data/metrics/monthly_snapshots.json')
    .then(r => r.json())
    .then(data => {
      const iterations = data.map(d => d.iteration);
      const reviewed = data.map(d => d.reviewed);
      const recognized = data.map(d => d.recognized);
      
      const trace1 = {
        x: iterations,
        y: reviewed,
        name: 'Total Reviews',
        type: 'bar',
        marker: {
          color: '#3b82f6',
          line: {
            color: '#2563eb',
            width: 1
          }
        }
      };
      
      const trace2 = {
        x: iterations,
        y: recognized,
        name: 'Recognized Reviews',
        type: 'bar',
        marker: {
          color: '#10b981',
          line: {
            color: '#059669',
            width: 1
          }
        }
      };
      
      const layout = {
        barmode: 'grouped',
        xaxis: {
          title: 'Review Cycle',
          tickangle: -45,
          automargin: true
        },
        yaxis: {
          title: 'Number of Reviews',
          automargin: true
        },
        margin: {
          l: 60,
          r: 30,
          t: 30,
          b: 80
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: {
          family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          size: window.innerWidth < 768 ? 10 : 12,
          color: '#64748b'
        },
        showlegend: true,
        legend: {
          x: window.innerWidth < 768 ? 0 : 0,
          y: window.innerWidth < 768 ? -0.2 : 1,
          bgcolor: 'transparent',
          orientation: window.innerWidth < 768 ? 'h' : 'v'
        },
        hovermode: 'x unified'
      };
      
      const config = {
        responsive: true,
        displayModeBar: false
      };
      
      Plotly.newPlot('snapshot', [trace1, trace2], layout, config);
      
      // Update stats
      if (data.length > 0) {
        // Calculate average recognition rate across all cycles
        const totalRecognized = data.reduce((sum, cycle) => sum + cycle.recognized, 0);
        const totalReviewed = data.reduce((sum, cycle) => sum + cycle.reviewed, 0);
        const avgRecognitionRate = totalReviewed > 0 ? (totalRecognized / totalReviewed) * 100 : 0;
        const recognitionRateElement = document.getElementById('recognition-rate');
        if (recognitionRateElement) {
          recognitionRateElement.textContent = avgRecognitionRate.toFixed(1) + '%';
        }
      }
    })
    .catch(err => {
      console.error('Error loading data:', err);
      const snapshotElement = document.getElementById('snapshot');
      if (snapshotElement) {
        snapshotElement.innerHTML = 
          '<p style="text-align: center; color: var(--text-secondary);">Unable to load review activity data</p>';
      }
    });

  // Fetch top reviewers data
  Promise.all([
    fetch('/data/metrics/top_people_absolute.json').then(r => r.json()),
    fetch('/data/metrics/top_institutions_absolute.json').then(r => r.json()),
    fetch('/data/reviewers_database.json').then(r => r.json())
  ])
    .then(([reviewers, institutions, reviewerDatabase]) => {
      // Make reviewer database globally available for card clicks
      window.reviewerDatabase = reviewerDatabase;
      
      // Update total unique reviewers across all cycles
      const totalReviewersElement = document.getElementById('total-reviewers');
      if (totalReviewersElement) {
        totalReviewersElement.textContent = reviewers.length.toLocaleString();
      }
      
      // Update institution count
      const topInstitutionsElement = document.getElementById('top-institutions');
      if (topInstitutionsElement) {
        topInstitutionsElement.textContent = institutions.length.toLocaleString();
      }
      
      // Update total reviews (estimate based on recognized reviews)
      const totalReviews = reviewers.reduce((sum, r) => sum + (r.recognized || 0), 0);
      const totalReviewsElement = document.getElementById('total-reviews');
      if (totalReviewsElement) {
        totalReviewsElement.textContent = totalReviews.toLocaleString();
      }
      
      // Function to find reviewer profile URL
      function getReviewerProfileUrl(name, institution) {
        // Search through the reviewer database to find matching reviewer
        for (const [openreviewId, reviewerData] of Object.entries(reviewerDatabase)) {
          if (reviewerData.name === name && reviewerData.institution === institution) {
            // Convert OpenReview ID to URL-safe format
            const urlSafeId = openreviewId.replace('~', '').replace(/[\/\\]/g, '-');
            return `/reviewer/${urlSafeId}/`;
          }
        }
        return null; // No profile found
      }
      
      // Display top 10 reviewers
      const tbody = document.getElementById('top-reviewers-body');
      if (tbody) {
        tbody.innerHTML = reviewers.slice(0, 10).map((reviewer, index) => {
          const rankClass = index === 0 ? 'rank-1' : index === 1 ? 'rank-2' : index === 2 ? 'rank-3' : '';
          const profileUrl = getReviewerProfileUrl(reviewer.name, reviewer.institution);
          
          // Create reviewer name link if profile exists
          const reviewerNameDisplay = profileUrl 
            ? `<a href="${profileUrl}" class="reviewer-link"><strong>${reviewer.name || 'Anonymous'}</strong></a>`
            : `<strong>${reviewer.name || 'Anonymous'}</strong>`;
          
          return `
            <tr class="animate-fade-in" style="animation-delay: ${index * 0.05}s">
              <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
              <td>${reviewerNameDisplay}</td>
              <td>${reviewer.institution || 'N/A'}</td>
              <td><strong>${reviewer.recognized || '-'}</strong></td>
              <td>${reviewer.reviewed || '-'}</td>
            </tr>
          `;
        }).join('');
        
        // Make table enhanced
        makeEnhancedTable('top-reviewers-table');
      }
    })
    .catch(err => {
      console.error('Error loading reviewer data:', err);
      const tbody = document.getElementById('top-reviewers-body');
      if (tbody) {
        tbody.innerHTML = 
          '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">Unable to load reviewer data</td></tr>';
      }
    });
}