"""
NewGenaratePTReportCommonSLA.py
================================
Processes a JMeter HTML performance report using a **single common SLA**
threshold (or a comma-separated list mapped positionally to transactions).

Workflow:
  1. Inject CSS styles and update table column headers.
  2. Apply the SLA threshold to each transaction row, colour-coding each
     as Pass/Fail against its average response time.
  3. Build an Overall Summary table and (when applicable) a paginated
     "Transactions That Need Attention" section.
  4. Persist the modified HTML report and email the results via SMTP.

Usage (CLI):
    python NewGenaratePTReportCommonSLA.py <SLA> <app> <Environment> <VastID>
        <ScopeOftheTest> <User_load> <Duration> <CA> <start_time> <end_time>
        <ModuleName> <distro> <locFile>

    SLA may be a single integer (ms) or a comma-separated list of integers
    mapped positionally to each transaction row.

Dependencies:
    beautifulsoup4
"""

import sys
import math
import smtplib
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Constants ─────────────────────────────────────────────────────────────────

SMTP_HOST = "vzsmtp.CompanyName.com"   # Internal SMTP relay hostname
SMTP_PORT = 25                      # SMTP relay port (no auth required on internal relay)
SMTP_FROM = "NSPET_PT_reports@CompanyName.com"   # Envelope sender address

# Base Artifactory URL where published JMeter HTML reports are stored.
ARTIFACT_BASE = "https://oneartifactoryci.CompanyName.com/artifactory/TCEV_CICD/JMeterFiles"

# This distribution list address is always included in the To: header,
# regardless of what the caller passes in the distro argument.
REQUIRED_RECIPIENT = "vz-it-performance@CompanyName.com"

# Fallback recipient list used when distro is empty or "NA".
DEFAULT_RECIPIENTS = [
    "sreenivasula.reddy.mukkamalla@CompanyName.com",
    "pachala.siddhartha@CompanyName.com",
    REQUIRED_RECIPIENT,
]


# ── 1. Config ─────────────────────────────────────────────────────────────────

def get_config() -> dict:
    """
    Build and return the test-run configuration dictionary from CLI arguments.

    Reads positional arguments from ``sys.argv[1:]`` and maps them to named
    keys.  One value is hard-coded and not accepted via the CLI:

    - ``threshold``: minimum acceptable success percentage (default ``"99.00"``).

    The ``SLA`` argument may be a single integer in milliseconds (e.g. ``"2000"``)
    or a comma-separated list (e.g. ``"2000,3000,5000"``) that is applied
    positionally to each transaction row during processing.

    Returns
    -------
    dict
        Keys: threshold, SLA, app, Environment, VastID, ScopeOftheTest,
              User_load, Duration, CA, start_time, end_time, ModuleName,
              distro, locFile.
    """
    keys = [
        "SLA", "app", "Environment", "VastID", "ScopeOftheTest",
        "User_load", "Duration", "CA", "start_time", "end_time",
        "ModuleName", "distro", "locFile",
    ]
    cfg = {"threshold": "99.00"}
    cfg.update(dict(zip(keys, sys.argv[1:])))
    return cfg


# ── 2. HTML I/O ───────────────────────────────────────────────────────────────

def load_html(path: str) -> BeautifulSoup:
    """
    Read an HTML file from disk and parse it with BeautifulSoup.

    Parameters
    ----------
    path : str
        Absolute or relative path to the JMeter HTML report file.

    Returns
    -------
    BeautifulSoup
        Parsed document tree ready for querying and in-place modification.
    """
    with open(path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f, "html.parser")


def save_html(soup: BeautifulSoup, path: str) -> None:
    """
    Serialise a BeautifulSoup document tree and write it back to disk.

    Parameters
    ----------
    soup : BeautifulSoup
        The modified document tree to persist.
    path : str
        Destination file path.  The existing file is overwritten.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(soup))


# ── 3. HTML transformations ───────────────────────────────────────────────────

def add_css_styles(soup: BeautifulSoup) -> None:
    """
    Append a ``<style>`` block to the document ``<head>``.

    The injected CSS covers:
      - Global body and table typography / spacing.
      - Responsive behaviour for small viewports.
      - ``.Success`` (green) and ``.Failure`` (red) row highlight classes
        used later to colour-code SLA results.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    """
    style = soup.new_tag("style")
    style.string = """
        /* ── Base typography ─────────────────────────────────────── */
        body {
            background-color: #f2f2f2;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: #333333;
            margin: 0;
            padding: 20px;
        }

        /* ── H1 banner ───────────────────────────────────────────── */
        h1 {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 22px;
            font-weight: 700;
            color: #1a1a2e;
            text-align: center;
            padding: 12px 0;
            border-bottom: 3px solid #007BFF;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }

        /* ── H2 section headings ─────────────────────────────────── */
        h2 {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0056b3;
            border-left: 5px solid #007BFF;
            padding-left: 12px;
            margin: 24px 0 12px;
            letter-spacing: 0.3px;
        }

        /* ── General table layout ────────────────────────────────── */
        table {
            border-collapse: collapse;
            border-spacing: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            width: 100%;
            margin: 0 auto 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            border-radius: 6px;
            overflow: hidden;
        }

        /* ── Table cells ─────────────────────────────────────────── */
        th, td {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            padding: 11px 15px;
            text-align: center;
            border: 1px solid #ddd;
            word-break: normal;
        }

        /* ── Standard header cells ───────────────────────────────── */
        th {
            background-color: #f2f2f2;
            font-weight: 700;
            font-size: 13px;
            color: #333;
        }

        /* ── Sticky thead header ─────────────────────────────────── */
        thead th {
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: #007BFF;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        /* ── Alternating row stripe ──────────────────────────────── */
        tbody tr:nth-child(even) { background-color: #f9f9f9; }
        tbody tr:hover { background-color: #e8f4fd !important; cursor: default; }

        /* ── Button inside table ─────────────────────────────────── */
        table td button {
            width: 25%; height: 50px;
            background-color: #5c8b95;
            box-shadow: 0 5px #666;
            font-size: 16px;
            font-family: Arial, sans-serif;
        }

        /* ── SLA status classes ──────────────────────────────────────── */
        .Failure {
            color: red;
            border-bottom: 1px solid red !important;
            background-color: #FFCCCC !important;
            font-weight: 700;
        }
        .Success {
            color: green;
            border-bottom: 1px solid green !important;
            background-color: #CCFFCC !important;
            font-weight: 700;
        }
  /* ── Overall Summary table ───────────────────────────────────── */
        #Overall-Summary {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            width: auto !important;          /* ← override the 100% table rule */
            min-width: 600px;                /* ← keep it readable on wide screens */
        }
        #Overall-Summary th {
            background-color: #343a40;
            color: #ffffff;
            width: 200px;                    /* label column */
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        #Overall-Summary td {
            font-size: 14px;
            font-weight: 500;
            width: 220px;
            max-width: 260px;
            word-break: break-word;
        }
        #Overall-Summary tr.Success td {
            background-color: #CCFFCC !important;
        }
        #Overall-Summary tr.Failure td {
            background-color: #FFCCCC !important;
        }
        /* ── Responsive ──────────────────────────────────────────── */
        @media screen and (max-width: 767px) {
            table { width: auto !important; }
            table col { width: auto !important; }
            .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        }
          /* ── Expand/Collapse detail rows ─────────────────────────────── */
        .page_details          { display: none !important; }
        .page_details_expanded { display: table-row !important; }

        /* Expand/collapse button cell – no border, transparent bg */
        td:last-child a img    { cursor: pointer; }      
    """
    soup.head.append(style)
def fix_expand_collapse_images(soup: BeautifulSoup) -> None:
    """
    Fix the expand/collapse toggle in the Pages table so it works in a
    standalone / emailed HTML file with NO external image files.

    Structure produced per transaction row (last <td>):
        <a href="javascript:change('page_details_N')" class="ec-link">
            <img src="[EXPAND_DATA_URI]"
                 id="page_details_N_image"
                 alt="Expand"
                 class="ec-icon">
            <span id="page_details_N_label" class="ec-label">Expand</span>
        </a>

    The <img> keeps its original id so the existing JS
    src.match("expand") / src.match("collapse") check still works.
    A sibling <span> with id="page_details_N_label" holds the visible
    text and is toggled by the updated change() function.
    """

    # ── Inline SVG data-URIs ───────────────────────────────────────────────────
    # URL-encode '#' → %23 so they are valid in src= attributes.
    # The words "expand" / "collapse" appear in <title> so src.match() still works.
    EXPAND_URI = (
        "data:image/svg+xml;charset=UTF-8,"
        "%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20"
        "width%3D'16'%20height%3D'16'%20viewBox%3D'0%200%2016%2016'%3E"
        "%3Ctitle%3Eexpand%3C%2Ftitle%3E"
        "%3Cpolygon%20points%3D'3%2C6%2013%2C6%208%2C12'%20fill%3D'%23ffffff'%2F%3E"
        "%3C%2Fsvg%3E"
    )
    COLLAPSE_URI = (
        "data:image/svg+xml;charset=UTF-8,"
        "%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20"
        "width%3D'16'%20height%3D'16'%20viewBox%3D'0%200%2016%2016'%3E"
        "%3Ctitle%3Ecollapse%3C%2Ftitle%3E"
        "%3Cpolygon%20points%3D'3%2C10%2013%2C10%208%2C4'%20fill%3D'%23ffffff'%2F%3E"
        "%3C%2Fsvg%3E"
    )

    # ── 1. Inject CSS for the anchor link and label ───────────────────────────
    ec_style = soup.new_tag("style")
    ec_style.string = """
        /* ── Expand/Collapse anchor button ──────────────────────────────── */
        a.ec-link {
            display:         inline-flex;
            align-items:     center;
            gap:             5px;
            text-decoration: none;
            cursor:          pointer;
            padding:         4px 10px;
            border-radius:   4px;
            background-color: #007BFF;
            border:          1px solid #0056b3;
            color:           #ffffff !important;
            font-size:       12px;
            font-weight:     600;
            font-family:     -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            white-space:     nowrap;
            user-select:     none;
        }
        a.ec-link:hover        { background-color: #0056b3; }
        a.ec-link.ec-collapsed { background-color: #6c757d; border-color: #495057; }
        a.ec-link.ec-collapsed:hover { background-color: #495057; }

        /* Icon inside the link */
        img.ec-icon {
            width:          14px;
            height:         14px;
            border:         none;
            vertical-align: middle;
            display:        inline-block;
        }

        /* Visible text label inside the link */
        span.ec-label {
            vertical-align: middle;
            line-height:    1;
        }
    """
    soup.head.append(ec_style)


def update_table_headers(soup: BeautifulSoup) -> None:
    """
    Rename existing column headers and insert two new columns in the Pages table.

    Existing header renames:
      - Column 0 → ``"Transaction Name"``
      - Column 3 → ``"Error Rate"``
      - Column 4 → ``"Average Time"``
      - Column 5 → ``"Min Time"``

    New headers injected:
      - ``"SLA"``     inserted immediately after the Average Time header.
      - ``"SLA Met"`` inserted immediately before the Min Time header.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    """
    headers = soup.find("h2", string="Pages").find_next_sibling("table").find_all("th")
    headers[0].string = "Transaction Name"
    headers[3].string = "Error Rate"
    headers[4].string = "Average Time"
    headers[5].string = "Min Time"

    sla_th, sla_met_th = soup.new_tag("th"), soup.new_tag("th")
    sla_th.string, sla_met_th.string = "SLA", "SLA Met"
    headers[4].insert_after(sla_th)
    headers[5].insert_before(sla_met_th)


def _parse_ms(text: str) -> float:
    """
    Safely parse a millisecond time value from a table cell string.

    Strips the ``"ms"`` suffix and any surrounding whitespace before
    attempting float conversion.  Returns ``0.0`` instead of raising an
    exception when the cell is blank or contains non-numeric content
    (e.g. a dash or an empty JMeter row).

    Parameters
    ----------
    text : str
        Raw cell text such as ``"411 ms"``, ``"411ms"``, or ``""``.

    Returns
    -------
    float
        Parsed millisecond value, or ``0.0`` if parsing fails.
    """
    try:
        return float(text.replace("ms", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def process_table_rows(soup: BeautifulSoup, sla: str) -> dict:
    """
    Iterate every data row in the Pages table and enrich it with SLA data.

    For each transaction row the function:
      1. Calculates the error percentage and updates the Error Rate cell.
      2. Selects the SLA threshold for this row from ``sla_list``
         (last value is reused if the list is shorter than the row count).
      3. Inserts ``SLA`` and ``SLA Met`` cells and colour-codes them using
         ``.Success`` / ``.Failure`` based on whether the average response
         time is within the SLA threshold.
      4. Converts all time values from milliseconds to seconds.
      5. Accumulates totals used later to determine overall test status.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    sla : str
        Comma-separated SLA threshold(s) in milliseconds.
        A single value (e.g. ``"2000"``) applies the same threshold to
        every row.  Multiple values (e.g. ``"2000,3000"``) are mapped
        positionally; the last value is reused for any extra rows.

    Returns
    -------
    dict
        Aggregated statistics with the following keys:

        - ``cnt_failure`` (int): transactions whose avg time exceeded the SLA.
        - ``total_samples`` (int): sum of all sample counts.
        - ``total_failures`` (int): sum of all failure counts.
        - ``has_txn_error_breach`` (bool): ``True`` if any transaction
          has an error rate above 3 %.
        - ``has_txn_error_count`` (int): number of transactions with
          error rate above 3 %.
        - ``transactions_tested`` (int): total data rows evaluated.
    """
    table    = soup.find("h2", string="Pages").find_next_sibling("table")
    sla_list = [s.strip() for s in sla.split(",")]

    cnt_failure = total_samples = total_failures = has_txn_error_count = 0
    has_txn_error_breach = False
    data_rows = table.find_all("tr", attrs={"valign": "top"})
    transactions_tested = len(data_rows) - 1   # subtract the header row

    for idx, tr in enumerate(data_rows):
        tds = tr.find_all("td")
        if len(tds) <= 7:
            continue   # skip header or malformed rows

        samples_td, failures_td, error_rate_td = tds[1], tds[2], tds[3]
        avg_time_td, min_time_td, max_time_td  = tds[4], tds[5], tds[6]

        # Insert the two new cells at the correct column positions.
        sla_td, sla_met_td = soup.new_tag("td"), soup.new_tag("td")
        avg_time_td.insert_after(sla_td)       # SLA cell sits right after Avg Time
        min_time_td.insert_before(sla_met_td)  # SLA Met cell sits right before Min Time

        # ── Sample / failure counts ───────────────────────────────────────────
        try:
            samples, failures = int(samples_td.text), int(failures_td.text)
        except ValueError:
            samples = failures = 0

        total_samples  += samples
        total_failures += failures

        # ── Error rate calculation ────────────────────────────────────────────
        error_perc = (failures / samples * 100) if samples > 0 else 0.0
        if error_perc > 3:
            has_txn_error_breach = True
            has_txn_error_count += 1
        error_rate_td.string = f"{round(error_perc, 2)}%"
        print(f"Transactions with failure above 3%: {has_txn_error_count}")

        # ── Safe time parsing (handles blank / non-numeric cells) ─────────────
        avg_ms    = _parse_ms(avg_time_td.text)
        min_ms    = _parse_ms(min_time_td.text)
        max_ms    = _parse_ms(max_time_td.text)

        # Pick the SLA for this row; reuse the last value if the list is shorter.
        sla_value = int(sla_list[min(idx, len(sla_list) - 1)])

        # Overwrite all time cells with human-readable seconds values.
        sla_td.string      = f"{sla_value / 1000} sec"
        avg_time_td.string = f"{avg_ms / 1000} sec"
        min_time_td.string = f"{min_ms / 1000} sec"
        max_time_td.string = f"{max_ms / 1000} sec"

        # ── SLA Met determination ─────────────────────────────────────────────
        if avg_ms <= sla_value:
            sla_met_td["class"], sla_met_td.string = "Success", "✅ Met"
        else:
            sla_met_td["class"], sla_met_td.string = "Failure", "❌ Missed"
            cnt_failure += 1

    return {
        "cnt_failure":          cnt_failure,
        "total_samples":        total_samples,
        "total_failures":       total_failures,
        "has_txn_error_breach": has_txn_error_breach,
        "has_txn_error_count":  has_txn_error_count,
        "transactions_tested":  transactions_tested,
    }


def sort_transactions_table(soup: BeautifulSoup) -> None:
    """
    Sort the Pages table data rows alphabetically by Transaction Name.

    Uses ``recursive=False`` when locating direct child ``<tr>`` elements
    so that rows belonging to nested sub-tables are not accidentally
    included in the sort.  Header rows (those containing ``<th>`` but no
    ``<td>``) are always preserved at the top of the table.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    """
    table = soup.find("h2", string="Pages").find_next_sibling("table")
    tbody = table.find("tbody") or table
    rows  = tbody.find_all("tr", recursive=False)

    header_rows = [r for r in rows if r.find("th") and not r.find("td", recursive=False)]
    data_rows   = [r for r in rows if r.find("td", recursive=False)]
    data_rows.sort(key=lambda r: (r.find("td", recursive=False).get_text(strip=True).lower()
                                  if r.find("td", recursive=False) else ""))
    tbody.clear()
    for row in header_rows + data_rows:
        tbody.append(row)


def calculate_status(total_samples, total_failures, cnt_failure,
                     has_txn_error_breach, threshold) -> dict:
    """
    Determine the overall PASS / FAIL status for the test run.

    The run is marked **FAIL** if any of the following conditions are true:
      - The overall success percentage falls below ``threshold``.
      - At least one transaction exceeded its SLA (``cnt_failure >= 1``).
      - At least one transaction had an error rate above 3 %
        (``has_txn_error_breach``).

    Parameters
    ----------
    total_samples : int
        Total number of requests across all transactions.
    total_failures : int
        Total number of failed requests across all transactions.
    cnt_failure : int
        Number of transactions whose average response time exceeded the SLA.
    has_txn_error_breach : bool
        ``True`` if any transaction's error rate exceeded 3 %.
    threshold : str
        Minimum acceptable success percentage as a string (e.g. ``"99.00"``).
        Falls back to ``99.0`` when the value cannot be parsed as a float.

    Returns
    -------
    dict
        Keys:

        - ``status`` (str): ``"PASS"`` or ``"FAIL"``.
        - ``error_percentage`` (float): overall error rate (0–100).
        - ``success_percentage`` (float): overall success rate (0–100).
    """
    error_pct   = (total_failures / total_samples * 100) if total_samples > 0 else 100.0
    success_pct = 100 - error_pct
    try:
        threshold_value = float(threshold)
    except ValueError:
        threshold_value = 99.0

    failed = success_pct < threshold_value or cnt_failure >= 1 or has_txn_error_breach
    return {
        "status":             "FAIL" if failed else "PASS",
        "error_percentage":   error_pct,
        "success_percentage": success_pct,
    }


def build_summary_table(soup, cfg, status, error_pct,
                        transactions_tested, sla_not_met, has_txn_error_count):
    """
    Build the Overall Summary ``<table>`` and insert it into the document.

    Replaces the existing JMeter summary table that follows the
    ``<h2>Summary`` heading with a new two-column key/value table.
    The heading text is updated to ``"Overall Summary"``.  Every row is
    styled with ``.Success`` or ``.Failure`` depending on overall status.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    cfg : dict
        Test-run configuration dictionary returned by :func:`get_config`.
    status : str
        ``"PASS"`` or ``"FAIL"``.
    error_pct : float
        Overall error percentage displayed in the table.
    transactions_tested : int
        Total number of transactions evaluated.
    sla_not_met : int
        Number of transactions whose average response time exceeded the SLA.
    has_txn_error_count : int
        Number of transactions whose error rate exceeded 3 %.

    Returns
    -------
    Tag
        The newly created ``<table>`` tag, needed by subsequent functions
        to anchor additional sections directly below it.
    """
    duration_min = round(int(cfg["Duration"]) / 60) if cfg["Duration"].isdigit() else 0

    summary_table = soup.new_tag(
        "table", id="Overall-Summary",
        attrs={"width": "auto", "cellspacing": "2", "cellpadding": "5",
               "border": "0", "align": "auto"},
    )

    # Each inner list represents one table row: [label, value, label, value, …].
    rows = [
        ["Application", f"{cfg['app']}({cfg['VastID']})", "ModuleName", cfg["ModuleName"]],
        ["Scope", cfg["ScopeOftheTest"], "VastID", cfg["VastID"]],
        ["Environment", cfg["Environment"], "CA#", cfg["CA"]],
        ["TestDuration",
         f"{duration_min}Min ({cfg['start_time']} to {cfg['end_time']})",
         "User load", cfg["User_load"]],
        ["Test Status",
         " PASS / GO " if status == "PASS" else " FAIL / NO GO ",
         "Error%", f"{error_pct:.2f}"],
        ["Transactions Tested#", str(transactions_tested),
         "SLA not Met#", str(sla_not_met)],
        ["Transactions With Errors#", str(has_txn_error_count)],
    ]

    row_class = "Success" if status == "PASS" else "Failure"
    for row in rows:
        tr = soup.new_tag("tr", attrs={"valign": "top"})
        tr["class"] = row_class
        for i in range(0, len(row), 2):
            th = soup.new_tag("th")
            th.string = row[i]
            tr.append(th)
            if i + 1 < len(row):
                td = soup.new_tag("td", attrs={"align": "center"})
                td.string = row[i + 1]
                tr.append(td)
        summary_table.append(tr)

    # Replace the existing JMeter summary table and update the heading text.
    summary_header = soup.find("h2", string="Summary")
    summary_header.find_next_sibling("table").decompose()
    summary_header.insert_after(summary_table)
    summary_header.string = "Overall Summary"
    return summary_table


def update_page_header(soup, app, vast_id, start_time, end_time) -> None:
    """
    Update the document ``<title>`` and ``<h1>`` banner with run details.

    Also updates the date/time cell in the small header table that sits
    directly below the ``<h1>`` element in the JMeter report template.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    app : str
        Application name included in the title and heading.
    vast_id : str
        VAST ID included in the title and heading.
    start_time : str
        Test start timestamp (e.g. ``"Mon-Apr-13-2026_02:37:10_EDT"``).
    end_time : str
        Test end timestamp.
    """
    h1_tag = soup.find("h1", string="Load Test Results")
    soup.find("title", string="Load Test Results").string = f"{app}|{vast_id}|Load Test Results|"
    h1_tag.string = f"{app}|{vast_id}|Load Test Results|"
    h1_tag.find_next_sibling("table").find_all("td")[0].string = (
        f"Date report: {start_time} to {end_time}"
    )


def build_transactions_attention_section(soup, summary_table, status) -> None:
    """
    Build and insert the paginated "Transactions That Need Attention" section.

    Only executed when ``status == "FAIL"``.  Collects every transaction
    that has a non-zero error rate or did not meet its SLA, then splits
    them across paginated ``<table>`` elements (5 rows per page) controlled
    by an inline jQuery pagination script.

    The section is inserted immediately below the Overall Summary table,
    separated by a horizontal rule.

    Parameters
    ----------
    soup : BeautifulSoup
        The document tree to modify in-place.
    summary_table : Tag
        The Overall Summary ``<table>`` tag returned by
        :func:`build_summary_table`; used as the DOM insertion anchor.
    status : str
        ``"PASS"`` or ``"FAIL"``.  The function returns immediately for
        ``"PASS"`` without making any changes.
    """
    if status != "FAIL":
        return

    tta_table = soup.find("h2", string="Pages").find_next_sibling("table")

    # Insert a horizontal rule and a new section heading below the summary.
    summary_hr = soup.new_tag("hr", attrs={"size": "1"})
    summary_table.insert_after(summary_hr)
    transactions_header = soup.new_tag("h2", string="Transactions That Need Attention")
    summary_hr.insert_after(transactions_header)

    # Build the shared column header row cloned into each page table.
    header_row = soup.new_tag("tr", attrs={"valign": "top"})
    for label in ["Transactions_Name", "Avg ResponseTime", "SLA", "ErrorRate"]:
        th = soup.new_tag("th", attrs={"align": "center"})
        th.string = label
        header_row.append(th)

    # Collect all rows that need attention (error > 0 % or SLA not met).
    failing_rows = []
    for t_tr in tta_table.find_all("tr", attrs={"valign": "top"}):
        t_tds = t_tr.find_all("td")
        if len(t_tds) <= 7:
            continue
        error_rate = float(t_tds[3].text.replace("%", "").strip())
        sla_met    = t_tds[6].text.strip()
        if error_rate > 0 or sla_met == "❌ Missed": #Comparing to get Failed transactions
            tr = soup.new_tag("tr", attrs={"valign": "top", "class": "failure"})
            for value in [
                t_tds[0].text,          # Transaction Name
                t_tds[4].text.strip(),  # Avg Response Time
                t_tds[5].text.strip(),  # SLA
                t_tds[3].text.strip(),  # Error Rate
            ]:
                td = soup.new_tag("td", attrs={"align": "center"})
                td.string = value
                tr.append(td)
            failing_rows.append(tr)

    # Split failing rows across pages of 5 and create a <table> per page.
    rows_per_page = 5
    total_pages   = math.ceil(len(failing_rows) / rows_per_page) if failing_rows else 1
    container     = soup.new_tag("div", id="Transactions-That-Need-Attention")
    page_tables   = {}

    for page_num in range(1, total_pages + 1):
        page_table = soup.new_tag(
            "table",
            attrs={"width": "95%", "cellspacing": "2", "cellpadding": "5", "border": "0",
                   "align": "center", "id": f"page-{page_num}", "style": "display: none;"},
        )

        # ── Wrap header row in <thead> so that  thead th { background:#007BFF }
        #    CSS rule fires correctly ──────────────────────────────────────────
        thead = soup.new_tag("thead")
        thead.append(header_row.__copy__())
        page_table.append(thead)

        # ── Wrap data rows in <tbody> for proper CSS alternating-stripe rules ─
        tbody = soup.new_tag("tbody")
        start_i = (page_num - 1) * rows_per_page
        for row in failing_rows[start_i: start_i + rows_per_page]:
            tbody.append(row)
        page_table.append(tbody)

        page_tables[page_num] = page_table
        container.append(page_table)
    if page_tables:
        page_tables[1].attrs.pop("style", None)   # page 1 is visible by default

    # Append numeric page-navigation anchor links.
    for n in range(1, total_pages + 1):
        container.append(soup.new_tag("a", href=f"#page-{n}", string=f" | Page {n} |"))

    container.append(soup.new_tag("br"))

    # Inline jQuery script: hides all page tables, shows only the clicked page.
    script = soup.new_tag("script")
    script.string = """
    var s = document.createElement('script');
    s.src = "https://code.jquery.com/jquery-3.6.0.min.js";
    document.head.appendChild(s);
    s.onload = function() {
        $("table[id^='page-']").hide(); $("#page-1").show();
        $("a[href^='#page-']").click(function(e) {
            e.preventDefault();
            $("table[id^='page-']").hide();
            $($(this).attr("href")).show();
        });
    };
    """
    container.append(script)
    transactions_header.insert_after(container)


# ── 4. Email ──────────────────────────────────────────────────────────────────

def get_email_css() -> str:
    """
    Return the inline CSS string embedded in every outgoing HTML email.

    The styles fix the width of the Overall Summary table, normalise
    table cell borders, and define the ``.Success`` / ``.Failure``
    background colour classes for email clients that strip ``<style>``
    blocks from ``<head>``.

    Returns
    -------
    str
        A complete ``<style>…</style>`` block ready for insertion into
        an HTML email ``<head>``.
    """
    return """
    <style>
        /* ── Base typography ─────────────────────────────────────────── */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: #333333;
            background-color: #f2f2f2;
            margin: 0;
            padding: 20px;
        }

        /* ── H2 headings ─────────────────────────────────────────────── */
        h2 {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0056b3;
            border-left: 5px solid #007BFF;
            padding-left: 12px;
            margin: 20px 0 10px;
            letter-spacing: 0.3px;
        }

        /* ── Tables ──────────────────────────────────────────────────── */
        table {
            border-collapse: collapse;
            border-spacing: 0;
            width: 100%;
            margin: 0 auto 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        /* ── Cells ───────────────────────────────────────────────────── */
        th, td {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            padding: 11px 15px;
            text-align: center;
            border: 1px solid #ddd;
        }

        /* ── Standard header row ─────────────────────────────────────── */
        th {
            background-color: #007BFF;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        /* ── Alternating rows (email-safe: applied via nth-child) ────── */
        table tr:nth-child(even) { background-color: #f9f9f9; }

  /* ── Overall Summary table ───────────────────────────────────── */
        #Overall-Summary {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            width: auto !important;          /* ← override the 100% table rule */
            min-width: 600px;                /* ← keep it readable on wide screens */
        }
        #Overall-Summary th {
            background-color: #343a40;
            color: #ffffff;
            width: 200px;                    /* label column */
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        #Overall-Summary td {
            font-size: 14px;
            font-weight: 500;
            width: 220px;
            max-width: 260px;
            word-break: break-word;
        }
        #Overall-Summary tr.Success td {
            background-color: #CCFFCC !important;
        }
        #Overall-Summary tr.Failure td {
            background-color: #FFCCCC !important;
        }
        /* ── SLA status classes ──────────────────────────────────────── */
        .Failure {
            color: red;
            border-bottom: 1px solid red !important;
            background-color: #FFCCCC !important;
            font-weight: 700;
        }
        .Success {
            color: green;
            border-bottom: 1px solid green !important;
            background-color: #CCFFCC !important;
            font-weight: 700;
        }
    </style>
    """

def build_email_body(soup: BeautifulSoup, status: str,
                     summary_table_html: str, file_path: str,
                     cfg: dict, transactions_tested: int,
                     success_pct: float, sla_not_met: int,
                     has_txn_error_count: int) -> str:
    """
    Compose the full HTML email body string.

    For a **PASS** result only the Overall Summary table and a brief
    confirmation message are included.

    For a **FAIL** result the body additionally contains all rows from the
    "Transactions That Need Attention" section (merged from all pagination
    pages into a single flat table for readability in email clients).

    Parameters
    ----------
    soup : BeautifulSoup
        The saved/re-loaded document tree (used to extract the attention
        section for FAIL emails).
    status : str
        ``"PASS"`` or ``"FAIL"``.
    summary_table_html : str
        Serialised HTML of the Overall Summary ``<table>`` element.
    file_path : str
        Artifactory URL to the full HTML report, included in the email
        footer so recipients can open the interactive report.

    Returns
    -------
    str
        Complete ``<html>…</html>`` string ready to attach as the email body.
    """
    css = get_email_css()
    status_color = "#28a745" if status == "PASS" else "#dc3545"
    status_text = "✅ PASS / GO" if status == "PASS" else "❌ FAIL / NO GO"

    header_html = f"""
    <div style="background:{status_color};padding:22px 20px;text-align:center;
                border-radius:8px;margin-bottom:24px;
                box-shadow:0 4px 10px rgba(0,0,0,0.2);">
      <span style="color:#ffffff;font-size:26px;font-weight:800;
                   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                   letter-spacing:1.5px;display:block;margin-bottom:4px;">
        PT Signoff Status
      </span>
      <span style="color:#ffffff;font-size:20px;font-weight:600;
                   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                   letter-spacing:1px;">
        {status_text}
      </span>
    </div>
    """
    if status == "PASS":
        verdict = (f"<p style='font-size:15px;color:#333;margin:12px 0;'>"
                   f"The performance test for <b>{cfg['app']}</b> completed successfully. "
                   f"All <b>{transactions_tested}</b> transactions met their SLA thresholds "
                   f"with a <b>{success_pct:.1f}%</b> success rate.</p>")
    else:
        _parts = []
        if sla_not_met > 0:
            _parts.append(f"<b>{sla_not_met}</b> transaction(s) exceeded the SLA")
        if has_txn_error_count > 0:
            _parts.append(f"<b>{has_txn_error_count}</b> transaction(s) had error rates above 3%")
        _reason = " and ".join(_parts) if _parts else "one or more SLA / error criteria were breached"
        verdict = (f"<p style='font-size:15px;color:#333;margin:12px 0;'>"
                   f"The performance test for <b>{cfg['app']}</b> requires attention. "
                   f"{_reason}.</p>")
    footer = f"""
    <div style="margin-top:30px;padding-top:15px;border-top:2px solid #dee2e6;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
            font-size:13px;color:#555555;line-height:1.8;">
      <p>📎 <a href="{file_path}" style="color:#007BFF;font-weight:600;text-decoration:none;">
           View Full HTML Report</a></p>
      <p>📩 Queries: <a href="mailto:{REQUIRED_RECIPIENT}"
           style="color:#007BFF;text-decoration:none;">{REQUIRED_RECIPIENT}</a></p>
      <p>💬 Use <b style="color:#333;">#help-ns-perf-testing</b> Slack for Performance Execution requests.</p>
      <p style="margin-top:12px;font-weight:700;font-size:14px;color:#333;">
         NS Performance Engineering Team</p>
      <p style="font-size:11px;color:#aaaaaa;font-style:italic;margin-top:4px;">
         ⚠️ This report is auto-generated. Please do not reply to this email.</p>
    </div>
    """

    h2_style = "color:#0056b3;font-size:18px;font-weight:700;border-left:5px solid #007BFF;padding-left:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;letter-spacing:0.3px;margin:20px 0 10px;"

    if status == "PASS":
        return (f"<html><head>{css}</head>"
                f"<body style=\"margin:0;padding:20px;background:#f2f2f2;"
                f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;\">"
                f"<div style=\"max-width:920px;margin:auto;background:white;padding:28px;"
                f"border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.12);\">"
                f"{header_html}</div>"
                f"<div> <p> {verdict}</p></div>"
                f"<h2 style=\"{h2_style}\"> Overall Summary</h2>"
                f"{summary_table_html}"
                f"<p style=\"color:#555;font-size:14px;\">✅ All transactions have met the SLA criteria.</p>"
                f"{footer}</body></html>")


    # FAIL: merge all paginated attention tables into a single flat table.
    attention_section = soup.find("div", {"id": "Transactions-That-Need-Attention"})
    attention_tables  = attention_section.find_all("table")
    headers_html  = "".join(str(th) for th in attention_tables[0].find_all("th"))
    all_rows_html = "".join(
        "".join(str(tr) for tr in t.find_all("tr")[1:]) for t in attention_tables
    )

    return (f"<html><head>{css}</head>"
            f"<body style=\"margin:0;padding:20px;background:#f2f2f2;"
            f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;\">"
            f"<div style=\"max-width:920px;margin:auto;background:white;padding:28px;"
            f"border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.12);\">"
            f"{header_html} </div>"
            f"<div> <p> {verdict}</p></div>"
            f"<h2 style=\"{h2_style}\"> Overall Summary</h2>"
            f"{summary_table_html}"
            f"<h2 style=\"{h2_style}\">⚠️ Transactions That Need Attention</h2>"
            f"<table><tr>{headers_html}</tr>{all_rows_html}</table>"
            f"<p style=\"color:#555;font-size:14px;\">Please review the transactions that need attention.</p>"
            f"{footer}</body></html>")


def resolve_recipients(distro: str) -> list:
    """
    Build the final deduplicated recipient list for the report email.

    Rules applied in order:
      1. If ``distro`` is blank or exactly ``"NA"`` (case-insensitive),
         use ``DEFAULT_RECIPIENTS``.
      2. Otherwise split ``distro`` on ``";"`` to obtain individual addresses.
      3. Deduplicate using ``dict.fromkeys`` (insertion order is preserved).
      4. Always append ``REQUIRED_RECIPIENT`` if it is not already present.

    Parameters
    ----------
    distro : str
        Semicolon-separated email address string supplied via the CLI,
        e.g. ``"alice@example.com;bob@example.com"``.  May be empty or
        ``"NA"`` to use the default distribution list.

    Returns
    -------
    list[str]
        Ordered, deduplicated list of recipient email addresses.
    """
    _distro = distro.strip()
    if _distro.upper() in ("", "NA"):
        recipients = list(DEFAULT_RECIPIENTS)
    else:
        recipients = list(dict.fromkeys(
            addr.strip() for addr in _distro.split(";") if addr.strip()
        ))
    if REQUIRED_RECIPIENT not in recipients:
        recipients.append(REQUIRED_RECIPIENT)
    return recipients


def send_email(email_body: str, subject: str, str_to: list) -> None:
    """
    Send the HTML report email via the internal SMTP relay.

    Connects to ``SMTP_HOST:SMTP_PORT`` without authentication (corporate
    relay) and uses ``SMTP_FROM`` as the envelope sender.  Any SMTP error
    (including connection timeouts) is caught and logged to stdout rather
    than re-raised, so a mail failure does not abort the overall script.

    Parameters
    ----------
    email_body : str
        Full HTML email body returned by :func:`build_email_body`.
    subject : str
        Email subject line.
    str_to : list[str]
        List of recipient email addresses used as SMTP envelope recipients.
    """
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = ",".join(str_to)   # display header (comma-separated)
    msg.attach(MIMEText(email_body, "html"))
    try:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=120)
        smtp.sendmail(SMTP_FROM, str_to, msg.as_string())
        smtp.quit()
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")


# ── 5. Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    """
    Orchestrate the end-to-end report generation and email dispatch.

    Execution steps
    ---------------
    1.  Load configuration from CLI arguments via :func:`get_config`.
    2.  Parse the JMeter HTML report and inject custom CSS.
    3.  Update table headers to include SLA and SLA Met columns.
    4.  Process each transaction row: calculate error rate, apply the
        common SLA threshold, and colour-code the result.
    5.  Sort transactions alphabetically by name.
    6.  Calculate the overall PASS / FAIL status.
    7.  Build and insert the Overall Summary table.
    8.  Update the report ``<title>`` and ``<h1>`` banner.
    9.  Build the "Transactions That Need Attention" section (FAIL only).
    10. Rename the "Pages" heading to "Transactions Summary" and save HTML.
    11. Re-parse the saved file to extract a clean summary table string.
    12. Compose the email body and resolve the recipient list.
    13. Send the report email via SMTP.
    """
    cfg      = get_config()
    loc_file = cfg["locFile"]

    # ── Steps 2–5: Load, style, enrich, and sort the HTML report ─────────────
    soup = load_html(loc_file)
    add_css_styles(soup)
    update_table_headers(soup)
    stats = process_table_rows(soup, cfg["SLA"])
    sort_transactions_table(soup)

    # ── Step 6: Determine overall PASS / FAIL ────────────────────────────────
    status_info = calculate_status(
        stats["total_samples"], stats["total_failures"],
        stats["cnt_failure"], stats["has_txn_error_breach"], cfg["threshold"]
    )
    status    = status_info["status"]
    error_pct = status_info["error_percentage"]

    # ── Steps 7–9: Build summary, update header, add attention section ────────
    summary_table = build_summary_table(
        soup, cfg, status, error_pct,
        stats["transactions_tested"], stats["cnt_failure"], stats["has_txn_error_count"]
    )
    update_page_header(soup, cfg["app"], cfg["VastID"], cfg["start_time"], cfg["end_time"])
    build_transactions_attention_section(soup, summary_table, status)

    # ── Step 10: Rename heading and persist the modified HTML ─────────────────
    soup.find("h2", string="Pages").string = "Transactions Summary"
    save_html(soup, loc_file)

    # ── Steps 11–13: Build and send the report email ──────────────────────────
    soup               = load_html(loc_file)   # re-parse for a clean serialised tree
    summary_table_html = str(soup.find("table", {"id": "Overall-Summary"}))
    file_path          = f"{ARTIFACT_BASE}/{cfg['app']}/{cfg['Environment']}/{loc_file}"
    subject            = (f"{cfg['app']}({cfg['VastID']}) | {cfg['ModuleName']} | "
                          f"Performance Test Report | CA#{cfg['CA']} | Test Status: {status}")

    email_body = build_email_body(
        soup, status, summary_table_html, file_path,
        cfg=cfg,
        transactions_tested=stats["transactions_tested"],
        success_pct=status_info["success_percentage"],
        sla_not_met=stats["cnt_failure"],
        has_txn_error_count=stats["has_txn_error_count"],
    )
    recipients = resolve_recipients(cfg.get("distro", ""))
    send_email(email_body, subject, recipients)

if __name__ == "__main__":
    main()
