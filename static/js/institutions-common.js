/**
 * Common institution functionality for ARR Great Reviewers
 * Shared between all-cycles and cycle-specific institution pages
 */

/**
 * Institution page manager class
 */
class InstitutionPageManager {
  constructor(config = {}) {
    this.config = {
      tableBodyId: 'institutions-body',
      tableId: 'institutions-table',
      maxTableRows: 100,
      chartTopCount: 20,
      statsConfig: {
        totalInstitutionsId: 'total-institutions',
        topInstitutionNameId: 'top-institution-name',
        topInstitutionCountId: 'top-institution-count',
        avgRecognizedReviewsId: 'avg-recognized-reviews',
        macroAvgRecognitionRateId: 'macro-avg-recognition-rate'
      },
      ...config
    };
    
    this.institutionIdMap = {};
  }

  /**
   * Initializes the institution page
   * @param {Object} options - Configuration options
   * @param {string|null} options.cycle - Cycle ID for cycle-specific pages, null for all-cycles
   * @param {boolean} options.loadCharts - Whether to load charts (default: true)
   * @param {boolean} options.loadStats - Whether to load stats (default: true)
   */
  async initialize(options = {}) {
    const { cycle = null, loadCharts = true, loadStats = true } = options;
    
    try {
      if (cycle) {
        await this.loadCycleData(cycle, loadCharts, loadStats);
      } else {
        await this.loadAllCyclesData(loadCharts, loadStats);
      }
    } catch (error) {
      console.error('Error initializing institution page:', error);
      this.handleError('Unable to load institution data');
    }
  }

  /**
   * Loads data for all cycles
   */
  async loadAllCyclesData(loadCharts = true, loadStats = true) {
    const [institutionData, reviewerData, institutionMappings] = await Promise.all([
      fetch('/data/metrics/top_institutions_absolute.json').then(r => r.json()),
      fetch('/data/metrics/top_people_absolute.json').then(r => r.json()),
      fetch('/data/institution_mappings.json').then(r => r.json()).catch(() => ({}))
    ]);

    this.institutionIdMap = institutionMappings;
    
    if (loadStats) {
      this.updateInstitutionStats(institutionData);
    }
    
    if (loadCharts) {
      this.createInstitutionChart(institutionData, 'inst_abs');
    }
    
    this.populateInstitutionTable(institutionData);
  }

  /**
   * Loads data for a specific cycle
   */
  async loadCycleData(cycle, loadCharts = true, loadStats = true) {
    const [institutionData, institutionMappings] = await Promise.all([
      fetch(`/data/metrics/institutions_${cycle}.json`).then(r => r.json()),
      fetch('/data/institution_mappings.json').then(r => r.json()).catch(() => ({}))
    ]);

    this.institutionIdMap = institutionMappings;
    
    if (loadStats) {
      this.updateInstitutionStats(institutionData);
    }
    
    if (loadCharts) {
      this.createInstitutionChart(institutionData, 'inst_abs');
    }
    
    this.populateInstitutionTable(institutionData);
  }


  /**
   * Gets the URL for an institution profile
   */
  getInstitutionUrl(institutionName) {
    const urlSafeId = this.institutionIdMap[institutionName];
    return urlSafeId ? TableUtils.URLUtils.institutionProfileUrl(urlSafeId) : null;
  }

  /**
   * Creates an institution table row
   */
  createInstitutionRow(institution, rank) {
    const institutionUrl = this.getInstitutionUrl(institution.institution);
    const nameCell = TableUtils.createNameCell(
      institution.institution, 
      institutionUrl, 
      'institution-link'
    );
    
    const progressBarCell = TableUtils.createProgressBarCell(
      institution.recognized || 0,
      institution.reviewed || 0
    );

    return `
      <td>${TableUtils.createRankBadge(rank)}</td>
      <td>${nameCell}</td>
      <td>${institution.reviewer_count || '-'}</td>
      <td>${institution.reviewed || '-'}</td>
      <td><strong>${institution.recognized || '-'}</strong></td>
      <td>${progressBarCell}</td>
    `;
  }

  /**
   * Populates the institution table
   */
  populateInstitutionTable(institutionData) {
    const rowRenderer = (institution, rank) => this.createInstitutionRow(institution, rank);
    
    TableUtils.populateTable(
      this.config.tableBodyId,
      institutionData,
      rowRenderer,
      this.config.maxTableRows
    );
  }

  /**
   * Updates institution statistics display
   */
  updateInstitutionStats(institutionData) {
    const stats = this.config.statsConfig;
    
    // Update total institutions count
    const totalElement = document.getElementById(stats.totalInstitutionsId);
    if (totalElement) {
      totalElement.textContent = institutionData.length.toLocaleString();
    }
    
    if (institutionData.length > 0) {
      const topInst = institutionData[0];
      
      // Update top institution name
      const nameElement = document.getElementById(stats.topInstitutionNameId);
      if (nameElement) {
        nameElement.textContent = topInst.institution;
      }
      
      // Update top institution count
      const countElement = document.getElementById(stats.topInstitutionCountId);
      if (countElement) {
        countElement.textContent = `${topInst.recognized} recognized reviews`;
      }
      
      // Calculate and update average recognized reviews per institution
      const totalRecognized = institutionData.reduce((sum, inst) => sum + (inst.recognized || 0), 0);
      const avgRecognized = (totalRecognized / institutionData.length).toFixed(1);
      const avgElement = document.getElementById(stats.avgRecognizedReviewsId);
      if (avgElement) {
        avgElement.textContent = avgRecognized;
      }
      
      // Calculate and update macro average recognition rate across institutions
      const institutionsWithRates = institutionData.filter(inst => inst.reviewed && inst.reviewed > 0);
      const macroElement = document.getElementById(stats.macroAvgRecognitionRateId);
      if (macroElement) {
        if (institutionsWithRates.length > 0) {
          const totalRecognitionRate = institutionsWithRates.reduce((sum, inst) => {
            const rate = (inst.recognized || 0) / inst.reviewed;
            return sum + rate;
          }, 0);
          const macroAvgRate = (totalRecognitionRate / institutionsWithRates.length * 100).toFixed(1);
          macroElement.textContent = `${macroAvgRate}%`;
        } else {
          macroElement.textContent = '-';
        }
      }
    }
  }

  /**
   * Creates institution recognition chart
   */
  createInstitutionChart(institutionData, chartElementId) {
    const topData = institutionData.slice(0, this.config.chartTopCount);
    const names = topData.map(d => d.institution);
    const values = topData.map(d => d.recognized || 0);
    
    const trace = {
      x: names,
      y: values,
      type: 'bar',
      marker: {
        color: values.map((v, i) => {
          const gradient = `rgba(30, 58, 95, ${0.9 - (i * 0.03)})`;
          return gradient;
        }),
        line: {
          color: '#0f2744',
          width: 1
        }
      },
      text: values.map(v => v.toString()),
      textposition: 'inside',
      textfont: { color: 'white', size: 12 },
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
      margin: { l: 60, r: 30, t: 30, b: 150 },
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
    
    Plotly.newPlot(chartElementId, [trace], layout, config);
  }

  /**
   * Handles chart rendering errors
   */
  handleChartError(chartElementId, message) {
    const element = document.getElementById(chartElementId);
    if (element) {
      element.innerHTML = `<p style="text-align: center; color: var(--text-secondary);">${message}</p>`;
    }
  }

  /**
   * Handles general page errors
   */
  handleError(message) {
    TableUtils.TableErrorHandlers.showTableError(this.config.tableBodyId, message, 6);
    this.handleChartError('inst_abs', message);
  }
}

// Export for use in page-specific scripts
window.InstitutionPageManager = InstitutionPageManager;