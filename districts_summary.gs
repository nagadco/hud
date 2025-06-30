/**
 * Google Apps Script to generate a district progress summary.
 *
 * Configuration:
 *  - AREAS_SHEET_NAME: name of the sheet holding area level data.
 *  - SUMMARY_SHEET_NAME: name for the summary sheet that will be created or updated.
 *  - TOTALS_SHEET_NAME: optional sheet containing total area counts per district.
 *    If present and USE_EXTERNAL_TOTALS is true, totals from this sheet will be
 *    used instead of counting rows in the Areas sheet. The totals sheet is
 *    expected to have headers in the first row with the district name in column A
 *    and the total count in column B.
 */

const AREAS_SHEET_NAME = 'Areas';
const SUMMARY_SHEET_NAME = 'Districts_Summary';
const TOTALS_SHEET_NAME = 'District_Totals';
const USE_EXTERNAL_TOTALS = true; // set to false to always calculate totals

/**
 * Main entry point to update the summary sheet.
 * Can be run manually or triggered on edit.
 */
function updateDistrictsSummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const areasSheet = ss.getSheetByName(AREAS_SHEET_NAME);
  if (!areasSheet) {
    SpreadsheetApp.getUi().alert('Areas sheet not found: ' + AREAS_SHEET_NAME);
    return;
  }
  const summarySheet =
    ss.getSheetByName(SUMMARY_SHEET_NAME) || ss.insertSheet(SUMMARY_SHEET_NAME);

  // Read area data
  const data = areasSheet.getDataRange().getValues();
  if (data.length < 2) {
    return; // nothing to summarise
  }
  const header = data[0];
  const districtIdx = header.indexOf('District');
  const statusIdx = header.indexOf('Status');
  if (districtIdx === -1 || statusIdx === -1) {
    SpreadsheetApp.getUi().alert('Areas sheet must contain District and Status columns.');
    return;
  }

  const stats = {};
  for (let i = 1; i < data.length; i++) {
    const district = String(data[i][districtIdx]).trim();
    const status = String(data[i][statusIdx]).trim();
    if (!district) {
      continue;
    }
    if (!stats[district]) {
      stats[district] = { total: 0, closed: 0 };
    }
    stats[district].total++;
    if (/^closed$/i.test(status) || /^off[- ]?plan$/i.test(status)) {
      stats[district].closed++;
    }
  }

  // Override totals from an external sheet if configured
  if (USE_EXTERNAL_TOTALS) {
    const totalsSheet = ss.getSheetByName(TOTALS_SHEET_NAME);
    if (totalsSheet) {
      const totals = totalsSheet.getDataRange().getValues();
      for (let i = 1; i < totals.length; i++) {
        const name = String(totals[i][0]).trim();
        const total = Number(totals[i][1]);
        if (!name) {
          continue;
        }
        if (!stats[name]) {
          stats[name] = { total: 0, closed: 0 };
        }
        if (!isNaN(total)) {
          stats[name].total = total;
        }
      }
    }
  }

  const rows = [['District', 'Total Areas', 'Closed/Off Plan', 'Remaining', 'Completion %', 'Status']];
  Object.keys(stats)
    .sort()
    .forEach(function (district) {
      const info = stats[district];
      const remaining = Math.max(0, info.total - info.closed);
      const completion = info.total ? (info.closed / info.total) * 100 : 0;
      let status = '⏳ In Progress';
      if (remaining === 0 && info.total > 0) {
        status = '✅ Complete';
      } else if (completion >= 95) {
        status = '🟡 Almost Complete';
      } else if (info.closed === 0) {
        status = '❌ Not Started';
      }
      rows.push([district, info.total, info.closed, remaining, completion, status]);
    });

  summarySheet.clear();
  summarySheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  summarySheet.autoResizeColumns(1, rows[0].length);
}

/**
 * Simple onEdit trigger that refreshes the summary when changes occur on the Areas sheet.
 */
function onEdit(e) {
  if (!e) return;
  const editedSheet = e.range.getSheet();
  if (editedSheet.getName() === AREAS_SHEET_NAME) {
    updateDistrictsSummary();
  }
}
