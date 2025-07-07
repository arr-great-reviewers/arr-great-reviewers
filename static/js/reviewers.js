/**
 * Reviewers page JavaScript functionality
 * Handles data loading, chart rendering, and table population for reviewer rankings
 */

// Load reviewer database to get OpenReview IDs
let reviewerIdMap = {};

// Function to get URL-safe reviewer ID 
function getReviewerUrl(name, institution) {
  const key = `${name}|${institution}`;
  const openreviewId = reviewerIdMap[key];
  
  if (openreviewId) {
    // Convert OpenReview ID to URL-safe format (~First_LastN -> First_LastN)
    return openreviewId.replace('~', '');
  }
  
  return null; // No OpenReview ID available
}

// Function to populate the table (called after both data sources are loaded)
function populateTable(reviewerData) {
  const tbody = document.getElementById('full-reviewers-body');
  tbody.innerHTML = reviewerData.slice(0, 100).map((reviewer, index) => {
    const rankClass = index === 0 ? 'rank-1' : index === 1 ? 'rank-2' : index === 2 ? 'rank-3' : '';
    const reviewerUrl = getReviewerUrl(reviewer.name || '', reviewer.institution || '');
    
    // Create name cell with or without link based on OpenReview ID availability
    const nameCell = reviewerUrl 
      ? `<strong><a href="/reviewer/${reviewerUrl}/" class="reviewer-link">${reviewer.name || 'Anonymous'}</a></strong>`
      : `<strong>${reviewer.name || 'Anonymous'}</strong>`;
    
    return `
      <tr class="animate-fade-in" style="animation-delay: ${Math.min(index * 0.02, 0.5)}s">
        <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
        <td>${nameCell}</td>
        <td>${reviewer.institution || 'N/A'}</td>
        <td>${reviewer.reviewed || '-'}</td>
        <td>${reviewer.recognized || '-'}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <div class="progress-bar" style="flex: 1;">
              <div class="progress-fill" style="width: ${(reviewer.reviewed && reviewer.reviewed > 0) ? Math.min(((reviewer.recognized || 0) / reviewer.reviewed) * 100, 100) : 0}%"></div>
            </div>
            <span style="font-size: 0.875rem; color: var(--text-secondary);">${(reviewer.reviewed && reviewer.reviewed > 0) ? (((reviewer.recognized || 0) / reviewer.reviewed) * 100).toFixed(1) + '%' : '-'}</span>
          </div>
        </td>
      </tr>
    `;
  }).join('');
  
  // Make table enhanced
  makeEnhancedTable('full-reviewers-table');
}

// Function to create reviewer recognition count chart
function createReviewerRecognitionChart(reviewerData) {
  const topData = reviewerData.slice(0, 20);
  const names = topData.map(d => d.name || 'Anonymous');
  const values = topData.map(d => d.recognized || 0);
  
  const trace = {
    x: names,
    y: values,
    type: 'bar',
    marker: {
      color: values.map((v, i) => {
        if (i === 0) return '#fbbf24';
        if (i === 1) return '#e5e7eb';
        if (i === 2) return '#c9975e';
        return '#3b82f6';
      }),
      line: {
        color: values.map((v, i) => {
          if (i === 0) return '#f59e0b';
          if (i === 1) return '#9ca3af';
          if (i === 2) return '#b97c45';
          return '#2563eb';
        }),
        width: 1
      }
    },
    text: values.map(v => v.toString()),
    textposition: 'outside',
    hovertemplate: '<b>%{x}</b><br>Recognized Reviews: %{y}<extra></extra>'
  };
  
  const layout = {
    xaxis: {
      title: 'Reviewer',
      tickangle: -45
    },
    yaxis: {
      title: 'Number of Recognized Reviews'
    },
    margin: {
      l: 60,
      r: 30,
      t: 30,
      b: 120
    },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      size: 12,
      color: '#64748b'
    },
    showlegend: false
  };
  
  const config = {
    responsive: true,
    displayModeBar: false
  };
  
  Plotly.newPlot('rev_abs', [trace], layout, config);
}

// Function to create reviewer percentage chart
function createReviewerPercentageChart() {
  fetch('/data/metrics/top_people_absolute.json')
    .then(r => r.json())
    .then(data => {
      // Filter to only include reviewers with at least 3 reviews
      const filteredData = data.filter(d => (d.reviewed || 0) >= 3);
      // Calculate percentage and sort by it
      const dataWithPercentage = filteredData.map(d => ({
        ...d,
        percentage: d.reviewed > 0 ? (d.recognized / d.reviewed) * 100 : 0
      })).sort((a, b) => b.percentage - a.percentage);
      
      const topData = dataWithPercentage.slice(0, 20);
      const names = topData.map(d => d.name || 'Anonymous');
      const percentages = topData.map(d => (d.percentage || 0).toFixed(1));
      
      const trace = {
        x: names,
        y: percentages,
        type: 'bar',
        marker: {
          color: '#10b981',
          line: {
            color: '#059669',
            width: 1
          }
        },
        text: percentages.map(p => p + '%'),
        textposition: 'outside',
        hovertemplate: '<b>%{x}</b><br>Recognition Rate: %{y}%<br>Reviews: %{customdata}<extra></extra>',
        customdata: topData.map(d => d.reviewed || 0)
      };
      
      const layout = {
        xaxis: {
          title: 'Reviewer',
          tickangle: -45
        },
        yaxis: {
          title: 'Recognition Rate (%)',
          range: [0, 100]
        },
        margin: {
          l: 60,
          r: 30,
          t: 30,
          b: 120
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: {
          family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          size: 12,
          color: '#64748b'
        },
        showlegend: false
      };
      
      const config = {
        responsive: true,
        displayModeBar: false
      };
      
      Plotly.newPlot('rev_pct', [trace], layout, config);
    })
    .catch(err => {
      console.error('Error loading percentage data:', err);
      document.getElementById('rev_pct').innerHTML = 
        '<p style="text-align: center; color: var(--text-secondary);">Unable to load percentage data</p>';
    });
}

// Main function to load and display reviewer data
function loadReviewerData() {
  // Load data in parallel and populate table when both are ready
  Promise.all([
    fetch('/data/metrics/top_people_absolute.json').then(r => r.json()),
    fetch('/data/reviewers_database.json').then(r => r.json()).catch(() => ({}))
  ]).then(([reviewerData, reviewerDatabase]) => {
    // Make reviewer database globally available for card clicks
    window.reviewerDatabase = reviewerDatabase;
    
    // Build ID mapping
    Object.values(reviewerDatabase).forEach(reviewer => {
      const key = `${reviewer.name}|${reviewer.institution}`;
      reviewerIdMap[key] = reviewer.openreview_id;
    });
    
    // Create recognition count chart and populate table
    createReviewerRecognitionChart(reviewerData);
    populateTable(reviewerData);
  })
    .catch(err => {
      console.error('Error loading reviewer data:', err);
      document.getElementById('rev_abs').innerHTML = 
        '<p style="text-align: center; color: var(--text-secondary);">Unable to load reviewer data</p>';
    });

  // Create percentage chart separately
  createReviewerPercentageChart();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', loadReviewerData);