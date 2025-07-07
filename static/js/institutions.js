/**
 * Institutions page JavaScript functionality
 * Handles data loading, chart rendering, and table population for institution rankings
 */

// Load institution database to get URL-safe IDs
let institutionIdMap = {};

// Function to get URL-safe institution ID 
function getInstitutionUrl(institutionName) {
  return institutionIdMap[institutionName] || null;
}

// Function to populate the table (called after all data sources are loaded)
function populateTable(institutionData) {
  const tbody = document.getElementById('institutions-body');
  tbody.innerHTML = institutionData.slice(0, 100).map((inst, index) => {
    const rankClass = index === 0 ? 'rank-1' : index === 1 ? 'rank-2' : index === 2 ? 'rank-3' : '';
    const institutionUrl = getInstitutionUrl(inst.institution);
    
    // Create name cell with or without link based on institution URL availability
    const nameCell = institutionUrl 
      ? `<strong><a href="/institution/${institutionUrl}/" class="institution-link">${inst.institution}</a></strong>`
      : `<strong>${inst.institution}</strong>`;
    
    return `
      <tr class="animate-fade-in" style="animation-delay: ${Math.min(index * 0.02, 0.5)}s">
        <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
        <td>${nameCell}</td>
        <td>${inst.reviewer_count || '-'}</td>
        <td>${inst.reviewed || '-'}</td>
        <td><strong>${inst.recognized || '-'}</strong></td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <div class="progress-bar" style="flex: 1;">
              <div class="progress-fill" style="width: ${(inst.reviewed && inst.reviewed > 0) ? Math.min(((inst.recognized || 0) / inst.reviewed) * 100, 100) : 0}%"></div>
            </div>
            <span style="font-size: 0.875rem; color: var(--text-secondary);">${(inst.reviewed && inst.reviewed > 0) ? (((inst.recognized || 0) / inst.reviewed) * 100).toFixed(1) + '%' : '-'}</span>
          </div>
        </td>
      </tr>
    `;
  }).join('');
  
  // Make table enhanced
  makeEnhancedTable('institutions-table');
}

// Function to create institution bar chart
function createInstitutionChart(institutionData) {
  const topData = institutionData.slice(0, 20);
  const names = topData.map(d => d.institution);
  const values = topData.map(d => d.recognized || 0);
  
  const trace = {
    x: names,
    y: values,
    type: 'bar',
    marker: {
      color: values.map((v, i) => {
        const gradient = `rgba(59, 130, 246, ${0.9 - (i * 0.03)})`;
        return gradient;
      }),
      line: {
        color: '#2563eb',
        width: 1
      }
    },
    text: values.map(v => v.toString()),
    textposition: 'outside',
    hovertemplate: '<b>%{x}</b><br>Recognized Reviews: %{y}<extra></extra>'
  };
  
  const layout = {
    xaxis: {
      title: 'Institution',
      tickangle: -45
    },
    yaxis: {
      title: 'Number of Recognized Reviews'
    },
    margin: {
      l: 60,
      r: 30,
      t: 30,
      b: 150
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
  
  Plotly.newPlot('inst_abs', [trace], layout, config);
}

// Function to update statistics display
function updateInstitutionStats(institutionData) {
  document.getElementById('total-institutions').textContent = institutionData.length.toLocaleString();
  
  if (institutionData.length > 0) {
    const topInst = institutionData[0];
    document.getElementById('top-institution-name').textContent = topInst.institution;
    document.getElementById('top-institution-count').textContent = `${topInst.recognized} recognized reviews`;
    
    // Calculate average (simplified since we don't have total reviews)
    const totalRecognized = institutionData.reduce((sum, inst) => sum + (inst.recognized || 0), 0);
    const avgRecognized = (totalRecognized / institutionData.length).toFixed(1);
    document.getElementById('avg-recognition-rate').textContent = avgRecognized;
  }
}

// Main function to load and display institution data
function loadInstitutionData() {
  Promise.all([
    fetch('/data/metrics/top_institutions_absolute.json').then(r => r.json()),
    fetch('/data/metrics/top_people_absolute.json').then(r => r.json()),
    fetch('/data/institution_mappings.json').then(r => r.json()).catch(() => ({}))
  ])
    .then(([institutions, reviewers, institutionMappings]) => {
      // Institution data is already an array
      const institutionData = institutions;
      
      // Build institution ID mapping
      institutionIdMap = institutionMappings;
      
      // Update stats, chart, and table
      updateInstitutionStats(institutionData);
      createInstitutionChart(institutionData);
      populateTable(institutionData);
    })
    .catch(err => {
      console.error('Error loading institution data:', err);
      document.getElementById('inst_abs').innerHTML = 
        '<p style="text-align: center; color: var(--text-secondary);">Unable to load institution data</p>';
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', loadInstitutionData);