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
      minReviewsForPercentage: 20,
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
      this.createPercentageChart();
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
      this.createPercentageChartFromData(institutionData, 'inst_pct');
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
    renderRankedDotChart(chartElementId, {
      linkClass: 'institution-link',
      items: topData.map(d => ({
        label: d.institution,
        url: this.getInstitutionUrl(d.institution),
        value: d.recognized || 0,
        text: String(d.recognized || 0),
        detail: `of ${d.reviewed || 0}`,
        extra: [d.reviewed || 0]
      })),
      valueTitle: 'Great reviews',
      integerValues: true,
      hovertemplate: '<b>%{customdata[0]}</b><br>Great reviews: %{x} of %{customdata[1]}<extra></extra>',
      onClick: index => this.openInstitution(topData[index])
    });
  }

  openInstitution(institution) {
    const url = this.getInstitutionUrl(institution.institution);
    if (url) {
      window.location.href = url;
    }
  }

  /**
   * Creates percentage chart from all-cycles data
   */
  createPercentageChart() {
    fetch('/data/metrics/top_institutions_percentage.json')
      .then(r => r.json())
      .then(data => {
        this.createPercentageChartFromData(data, 'inst_pct');
      })
      .catch(err => {
        console.error('Error loading percentage data:', err);
        this.handleChartError('inst_pct', 'Unable to load percentage data');
      });
  }

  /**
   * Creates percentage chart from provided data
   */
  createPercentageChartFromData(data, chartElementId) {
    // Filter to institutions with minimum review count
    const filteredData = data.filter(d => (d.reviewed || 0) >= this.config.minReviewsForPercentage);

    // Calculate percentages and sort; ties as documented on About: more great reviews, then more reviews
    const dataWithPercentage = filteredData.map(d => ({
      ...d,
      percentage: d.reviewed > 0 ? (d.recognized / d.reviewed) * 100 : 0
    })).sort((a, b) =>
      b.percentage - a.percentage || b.recognized - a.recognized || b.reviewed - a.reviewed
    );

    const topData = dataWithPercentage.slice(0, this.config.chartTopCount);
    renderRankedDotChart(chartElementId, {
      linkClass: 'institution-link',
      items: topData.map(d => ({
        label: d.institution,
        url: this.getInstitutionUrl(d.institution),
        value: d.percentage,
        text: `${d.percentage.toFixed(1)}%`,
        detail: `${d.recognized || 0} of ${d.reviewed || 0}`,
        extra: [d.recognized || 0, d.reviewed || 0]
      })),
      valueTitle: 'Recognition rate',
      tickSuffix: '%',
      hovertemplate: '<b>%{customdata[0]}</b><br>Recognition rate: %{x:.1f}%<br>Great reviews: %{customdata[1]}<br>Total reviews: %{customdata[2]}<extra></extra>',
      onClick: index => this.openInstitution(topData[index])
    });
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
    this.handleChartError('inst_pct', message);
  }
}

// Export for use in page-specific scripts
window.InstitutionPageManager = InstitutionPageManager;