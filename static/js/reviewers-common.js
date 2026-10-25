/**
 * Common reviewer functionality for ARR Great Reviewers
 * Shared between all-cycles and cycle-specific reviewer pages
 */

/**
 * Reviewer page manager class
 */
class ReviewerPageManager {
  constructor(config = {}) {
    this.config = {
      tableBodyId: 'full-reviewers-body',
      tableId: 'full-reviewers-table',
      maxTableRows: 100,
      chartTopCount: 20,
      minReviewsForPercentage: 5,
      ...config
    };
    
    this.reviewerIdMap = {};
    this.reviewerDatabase = {};
  }

  /**
   * Initializes the reviewer page
   * @param {Object} options - Configuration options
   * @param {string|null} options.cycle - Cycle ID for cycle-specific pages, null for all-cycles
   * @param {boolean} options.loadCharts - Whether to load charts (default: true)
   */
  async initialize(options = {}) {
    const { cycle = null, loadCharts = true } = options;
    
    try {
      if (cycle) {
        await this.loadCycleData(cycle, loadCharts);
      } else {
        await this.loadAllCyclesData(loadCharts);
      }
    } catch (error) {
      console.error('Error initializing reviewer page:', error);
      this.handleError('Unable to load reviewer data');
    }
  }

  /**
   * Loads data for all cycles
   */
  async loadAllCyclesData(loadCharts = true) {
    const [reviewerData, reviewerDatabase] = await Promise.all([
      fetch('/data/metrics/top_people_absolute.json').then(r => r.json()),
      fetch('/data/reviewers_database.json').then(r => r.json()).catch(() => ({}))
    ]);

    this.setupReviewerDatabase(reviewerDatabase);
    this.populateReviewerTable(reviewerData);
    
    if (loadCharts) {
      this.createRecognitionChart(reviewerData, 'rev_abs');
      this.createPercentageChart();
    }
  }

  /**
   * Loads data for a specific cycle
   */
  async loadCycleData(cycle, loadCharts = true) {
    const [sortedData, reviewerDatabase] = await Promise.all([
      fetch(`/data/metrics/reviewers_${cycle}.json`).then(r => r.json()),
      fetch('/data/reviewers_database.json').then(r => r.json()).catch(() => ({}))
    ]);

    this.setupReviewerDatabase(reviewerDatabase);
    this.populateReviewerTable(sortedData);
    
    if (loadCharts) {
      this.createRecognitionChart(sortedData, 'rev_abs');
      this.createPercentageChartFromData(sortedData, 'rev_pct');
    }
  }

  /**
   * Sets up the reviewer database and ID mapping
   */
  setupReviewerDatabase(reviewerDatabase) {
    this.reviewerDatabase = reviewerDatabase;
    window.reviewerDatabase = reviewerDatabase; // Make globally available
    
    // Build ID mapping for URL generation: current name|institution plus every
    // name|institution pair the reviewer appeared under in earlier cycles
    Object.values(reviewerDatabase).forEach(reviewer => {
      this.reviewerIdMap[`${reviewer.name}|${reviewer.institution}`] = reviewer.openreview_id;
      (reviewer.source_keys || []).forEach(key => {
        this.reviewerIdMap[key] = reviewer.openreview_id;
      });
    });
  }

  /**
   * Gets the URL for a reviewer profile
   */
  getReviewerUrl(name, institution) {
    const key = `${name}|${institution}`;
    const openreviewId = this.reviewerIdMap[key];
    
    if (openreviewId) {
      const urlSafeId = TableUtils.URLUtils.openreviewIdToUrl(openreviewId);
      return TableUtils.URLUtils.reviewerProfileUrl(urlSafeId);
    }
    
    return null;
  }

  /**
   * Creates a reviewer table row
   */
  createReviewerRow(reviewer, rank) {
    const reviewerUrl = this.getReviewerUrl(reviewer.name || '', reviewer.institution || '');
    const nameCell = TableUtils.createNameCell(
      reviewer.name || 'Anonymous', 
      reviewerUrl, 
      'reviewer-link'
    );
    
    const progressBarCell = TableUtils.createProgressBarCell(
      reviewer.recognized || 0,
      reviewer.reviewed || 0
    );

    return `
      <td>${TableUtils.createRankBadge(rank)}</td>
      <td>${nameCell}</td>
      <td>${reviewer.institution || 'N/A'}</td>
      <td>${reviewer.reviewed || '-'}</td>
      <td>${reviewer.recognized || '-'}</td>
      <td>${progressBarCell}</td>
    `;
  }

  /**
   * Populates the reviewer table
   */
  populateReviewerTable(reviewerData) {
    const rowRenderer = (reviewer, rank) => this.createReviewerRow(reviewer, rank);
    
    TableUtils.populateTable(
      this.config.tableBodyId,
      reviewerData,
      rowRenderer,
      this.config.maxTableRows
    );
  }

  /**
   * Creates recognition count chart
   */
  createRecognitionChart(reviewerData, chartElementId) {
    const topData = reviewerData.slice(0, this.config.chartTopCount);
    renderRankedBarChart(chartElementId, {
      items: topData.map(d => ({
        label: d.name || 'Anonymous',
        value: d.recognized || 0,
        text: String(d.recognized || 0)
      })),
      valueTitle: 'Great reviews',
      hovertemplate: '<b>%{customdata[0]}</b><br>Great reviews: %{x}<extra></extra>',
      onClick: index => this.openReviewer(topData[index])
    });
  }

  openReviewer(reviewer) {
    const url = this.getReviewerUrl(reviewer.name || '', reviewer.institution || '');
    if (url) {
      window.location.href = url;
    }
  }

  /**
   * Creates percentage chart from all-cycles data
   */
  createPercentageChart() {
    fetch('/data/metrics/top_people_absolute.json')
      .then(r => r.json())
      .then(data => {
        this.createPercentageChartFromData(data, 'rev_pct');
      })
      .catch(err => {
        console.error('Error loading percentage data:', err);
        this.handleChartError('rev_pct', 'Unable to load percentage data');
      });
  }

  /**
   * Creates percentage chart from provided data
   */
  createPercentageChartFromData(data, chartElementId) {
    // Filter to reviewers with minimum review count
    const filteredData = TableUtils.DataUtils.filterByMinReviews(data, this.config.minReviewsForPercentage);
    
    // Calculate percentages and sort
    const dataWithPercentage = filteredData.map(d => ({
      ...d,
      percentage: d.reviewed > 0 ? (d.recognized / d.reviewed) * 100 : 0
    })).sort((a, b) => b.percentage - a.percentage);
    
    const topData = dataWithPercentage.slice(0, this.config.chartTopCount);
    renderRankedBarChart(chartElementId, {
      items: topData.map(d => ({
        label: d.name || 'Anonymous',
        value: d.percentage,
        text: `${d.percentage.toFixed(1)}% (${d.recognized || 0})`,
        extra: [d.recognized || 0, d.reviewed || 0]
      })),
      valueTitle: 'Recognition rate (%)',
      range: [0, 100],
      hovertemplate: '<b>%{customdata[0]}</b><br>Recognition rate: %{x:.1f}%<br>Great reviews: %{customdata[1]}<br>Total reviews: %{customdata[2]}<extra></extra>',
      onClick: index => this.openReviewer(topData[index])
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
    this.handleChartError('rev_abs', message);
    this.handleChartError('rev_pct', message);
  }
}

// Export for use in page-specific scripts
window.ReviewerPageManager = ReviewerPageManager;
