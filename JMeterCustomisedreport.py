import sys
import re
import requests
import math
from bs4 import BeautifulSoup
# Send email with summary and transactions tables
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket

#SLA = sys.argv[1]
#threshold = float(sys.argv[2])
#locFile = sys.argv[3]
SLA = "2000"
threshold = "99.00"
locFile = "/htmlpath"
app = "VBUILD"
# Read the HTML file
with open(locFile, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")
# Remove existing style tags
#for s in soup.select('style'):
 #   s.extract()
# Add CSS for styling
new_style = soup.new_tag("style")
new_style.string = """

                 body{
                 background-color: #FFF;
                 }
                table td button {
                 width: 25%;
                 height: 50px;
                 background-color: #5c8b95;
                 box-shadow: 0 5px #666;
                 font-size: 20px;
                
                 }
                 .font-weight-bold{font-weight:bold;}
                 table  {
                 border-collapse: separate;
                 border-spacing:1px;
                 font-family:ui-rounded;
                 }
                 table,Overall-Summary,Transactions-That-Need-Attention{text-align:center;font-weight:bold;vertical-align:top;bgcolor:#90D5F7;padding: 10px 15px;}
                 table td{font-family:Arial, sans-serif;font-size:14px;padding:10px 15px;border-bottom:solid;border-width:1px;overflow:hidden;word-break:normal;border-bottom-color:grey;}
                 th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
                 th { background-color: #007BFF; color: white; }
                 @media screen and (max-width: 767px) {table {width: auto !important;}table col {width: auto !important;}table-wrap {overflow-x: auto;-webkit-overflow-scrolling: touch;}}
                 .Failure  {
                 color: #FF0000;
                 border-bottom: 3px solid #FF0000 !important;
                 background-color: #ffcccc !important; 
                 color: red; 
                 font-weight: bold;
                 }

                 .Success {
                 color: #008000;
                 border-bottom: 3px solid #008000 !important;
                 background-color: #ccffcc !important; 
                 color: green; 
                 font-weight: bold; 
                 }

"""
soup.head.append(new_style)

# Update table headers


# Find the table and update the headers
table = soup.find("h2", string="Pages").find_next_sibling("table")
headers = table.find_all('th')
headers[3].string = 'Error Rate'
headers[4].string = 'Average Time'
headers[5].string = 'Min Time'
sla_th = soup.new_tag("th")
sla_met_th = soup.new_tag("th")

headers[5].insert_before(sla_met_th)
headers[4].insert_after(sla_th)
sla_th.string = 'SLA'
sla_met_th.string = 'SLA Met'
# Process table rows
#cntFailure = 0
cntFailure1 = 0
error_perc = 0.00
samples = 0
failures = 0
transactions_tested = 0
total_samples = 0
total_failures = 0
StrSLAEach = SLA.split(",") if "," in SLA else [SLA]

# Count the rows with valign="top"
transactions_tested = len(table.find_all("tr", attrs={"valign": "top"})) - 1

for idx, tr in enumerate(table.find_all("tr", attrs={"valign": "top"})):

    tds = tr.find_all("td")
    if len(tds) > 6:
        samples_td = tds[1]
        failures_td = tds[2]
        error_rate_td = tds[3]
        avg_time_td = tds[4]
        min_time_td = tds[5]
        # Create new td elements for SLA and SLA Met
        sla_td = soup.new_tag("td")
        sla_met_td = soup.new_tag("td")
        # Insert the new td elements between Average Time and Min Time
        min_time_td.insert_before(sla_met_td)
        avg_time_td.insert_after(sla_td)
        # Update the total counts
        #print(samples_td.text)
        try:
            samples = int(samples_td.text)
            failures = int(failures_td.text)
        except ValueError:
            samples = 0
            failures = 0
        total_samples += samples

        total_failures += failures
        # Extract error rate

        if samples > 0:
            error_perc = (failures/samples)*100
        error_rate_td.string = f"{round(error_perc, 2)}%"
        tds.append(error_rate_td)
        # Compare SLA and update row
        avg_time = int(avg_time_td.text.replace("ms", "").strip())
        SLA_value = int(StrSLAEach[min(idx, len(StrSLAEach) - 1)])
        # Update SLA & SLA MET Values
        sla_td.string = f"{SLA_value} ms"
        tds.append(sla_td)

        # sla_met = "True" if avg_time <= SLA_value else "False"
        if avg_time <= SLA_value:
            sla_met = 'True'
            sla_met_td["class"] = "Success"
            sla_met_td.string = sla_met
            tds.append(sla_met_td)
        else:
            sla_met = 'False'
            sla_met_td["class"] = "Failure"
            sla_met_td.string = sla_met
            tds.append(sla_met_td)
            cntFailure1 += 1


error_percentage = (total_failures / total_samples) * 100
success_percentage = 100 - error_percentage
# Update summary section
# Create the summary table
summary_table = soup.new_tag(
    "table", id="Overall-Summary",
    attrs={
        "width": "auto",
        "cellspacing": "2",
        "cellpadding": "5",
        "border": "0",
        "align": "auto",
    },
)

# Create the rows and cells for the summary table
status = "PASS" if cntFailure1 == 0 and success_percentage >= float(threshold) else "FAIL"
sla_not_met = cntFailure1
summary_rows = [
    ["Test Status", "Success" if status == "PASS" else "Failure", "Transactions Tested", str(transactions_tested)],

    ["SLA not Met", str(sla_not_met), "Error%", f"{error_percentage:.2f}"]

]

for row in summary_rows:
    summary_tr = soup.new_tag("tr", attrs={"valign": "top"})
    summary_tr["class"] = "Success" if status == "PASS" else "Failure"
    for i in range(0, len(row), 2):
        th1 = soup.new_tag("th")
        th1.string = row[i]
        summary_tr.append(th1)
        if i + 1 < len(row):
            td = soup.new_tag("td", attrs={"align": "center"})
            td.string = row[i + 1]
            summary_tr.append(td)
    summary_table.append(summary_tr)
# Insert the summary table after the existing header
existing_header = soup.find("h2", string="Summary").find_next_sibling("table")
existing_header.decompose()
summary_header = soup.find('h2', string='Summary')
summary_header.insert_after(summary_table)
#soup.body.append(summary_table)
#summary_header = soup.find('h2', string='Summary')
summary_header.string = 'Overall Summary'
# Write updated HTML to file


if status == 'FAIL':
    tta_table = soup.find("h2", string="Pages").find_next_sibling("table")
    summary_hr = soup.new_tag('hr', attrs={'size': '1'})
    summary_table.insert_after(summary_hr)
    transactions_header = soup.new_tag('h2', string='Transactions That Need Attention')
    summary_hr.insert_after(transactions_header)
    transactions_table = soup.new_tag('table',  attrs={'width': 'Auto', 'cellspacing': '2', 'cellpadding': '5', 'border': '0', 'align': 'center'})
    transactions_tr = soup.new_tag("tr", attrs={"valign": "top", "class": "failure"})
    # capture all transactions that need attention
    # refactor the tta_table to have transaction headers
    transactions_rows = []
    transactions_header_row = soup.new_tag("tr", attrs={"valign": "top"})
    header_cells = ["Transactions_Name", "Avg ResponseTime", "SLA", "ErrorRate"]
    for header_cell in header_cells:
        th = soup.new_tag("th", attrs={"align": "center"})
        th.string = header_cell
        transactions_header_row.append(th)

    # insert the header row at the beginning of the transactions table
    transactions_table.insert(0, transactions_header_row)

    for idx, t_tr in enumerate(tta_table.find_all("tr", attrs={"valign": "top"})):
        t_tds = t_tr.find_all('td')
        if len(t_tds) > 7:
            transactions_td = t_tds[0]
            errorrate_td = t_tds[3]
            avgtime_td = t_tds[4]
            slatd = t_tds[5]
            slamettd = t_tds[6]
            errorrates = float(errorrate_td.text.replace("%", "").strip())
            sladeviation = slamettd.text.strip()

            if errorrates > 0 or sladeviation == 'False':
                transactions_name = transactions_td.text
                avgtime = avgtime_td.text.strip()
                sla = slatd.text.strip()
                errorrate = errorrate_td.text.strip()

                transactions_tr = soup.new_tag("tr", attrs={"valign": "top", "class": "failure"})
                for value in [transactions_name, avgtime, sla, errorrate]:
                    transactions_td = soup.new_tag("td", attrs={"align": "center"})
                    transactions_td.string = value
                    transactions_tr.append(transactions_td)
                transactions_rows.append(transactions_tr)
    # Pagination setup
    rows_per_page = 5  # Define how many rows you want per page
    total_rows = len(transactions_rows)
    total_pages = math.ceil(total_rows / rows_per_page)

    # Create a container for the entire paginated table
    paginated_table_container = soup.new_tag('div', id="Transactions-That-Need-Attention")

    # Create a dictionary to store the page tables
    page_tables = {}

    for page_num in range(1, total_pages + 1):
        # Create a table for each page
        page_table = soup.new_tag('table',  attrs={'width': '95%', 'cellspacing': '2', 'cellpadding': '5', 'border': '0',
                                                  'align': 'center', 'id': f'page-{page_num}',
                                                  'style': 'display: none;'})
        page_table.append(transactions_header_row.__copy__())  # Add header to each page

        # Calculate start and end indices for rows on this page
        start_index = (page_num - 1) * rows_per_page
        end_index = min(start_index + rows_per_page, total_rows)

        # Add rows to the current page's table
        for row in transactions_rows[start_index:end_index]:
            page_table.append(row)

        # Store the page table in the dictionary
        page_tables[page_num] = page_table

        paginated_table_container.append(page_table)

    # Show Page1 by default
    page_tables[1].attrs.pop('style')

    # Add pagination links below the table
    pagination_links = []
    for page_num in range(1, total_pages + 1):
        page_link = soup.new_tag("a", href=f"#page-{page_num}")
        page_link.string = f" | Page {page_num} |"
        if page_num > 1:
            # Assuming page_link is a BeautifulSoup element
            if page_link.parent:
                page_link.parent.insert_before(soup.new_tag("span", string=" | "))
                page_link.insert_before(soup.new_tag("span", string=" | "))  # Add separators between links
        pagination_links.append(page_link)

    paginated_table_container.append(soup.new_tag('br'))  # Line break for better formatting

    # Add JavaScript code to show and hide the page tables
    pagination_script = soup.new_tag('script')
    pagination_script.string = """
    // Add jQuery to the page if it's not already included
    var script = document.createElement('script');
    script.src = "https://code.jquery.com/jquery-3.6.0.min.js";
    script.type = 'text/javascript';
    document.getElementsByTagName('head')[0].appendChild(script);

    // Wait for jQuery to load before executing the rest of the script
    script.onload = function() {
        // Hide all pages except the first one initially
        $("table[id^='page-']").hide();
        $("#page-1").show();

        // Handle pagination link clicks
        $("a[href^='#page-']").click(function(event) {
        event.preventDefault(); // Prevent default link behavior

        var targetPageId = $(this).attr("href"); // Get the target page id from href
        $("table[id^='page-']").hide(); // Hide all pages
        $(targetPageId).show(); // Show the target page
        });
        };
    """
    for link in pagination_links:
        paginated_table_container.append(link)
    paginated_table_container.append(pagination_script)

    # Insert the paginated table after the transactions header
    transactions_header.insert_after(paginated_table_container)
Tr_summary_header = soup.find("h2", string="Pages")
Tr_summary_header.string = 'Transactions Summary'

# Write updated HTML to file
with open(locFile, "w", encoding="utf-8") as f:
    f.write(str(soup))

# Read HTML file
with open(locFile, 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

# Extract Overall Summary Table
overall_summary_table = str(soup.find('table', {'id': 'Overall-Summary'}))
# CSS for Styling
css_style = '''
<style>
    body {
        font-family: Arial, sans-serif;
        margin: 20px;
        color: #333;
        background-color: #f2f2f2;
    }

    h2 {
        color: #0056b3;
        margin-bottom: 10px;
    }

    table {
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        margin: auto;
        box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.3);
    }

     th, td {
        padding: 10px;
        text-align: auto;
        border-bottom: 1px solid #ddd;
        border-right: 1px solid #ddd;
        border-left: 1px solid #ddd;
    }

     th {
        background-color: #f2f2f2;
        font-weight: bold;
        border-bottom: 1px solid #ddd;
    }

    table tr:nth-child(2n) {
        background-color: #ffffff;
    }

    table tr:hover,
    table tr:hover td {
        background-color: #f5f5f5;
    }

    table td:first-child,
    table th:first-child {
        border-left: none;
    }

    table td:last-child,
    table th:last-child {
        border-right: none;
    }

   .Success {
        background-color: #d9fac8;
        border-bottom: 3px solid #008000 !important;
    }

    .Failure {
        background-color: #fa6969;
        border-bottom: 3px solid #FF0000 !important;
    }

</style>
'''

if status == "PASS":
    # Create Email Content
    email_body = f"""
    <html>
    <head>
    {css_style}
    </head>
    <body>
    <h2>Overall Summary</h2>
    {overall_summary_table}
    </body>
    """

else:
    # Extract Transactions That Need Attention Tables
    attention_section = soup.find('div', {'id': 'Transactions-That-Need-Attention'})
    attention_tables = attention_section.find_all('table')
    #attention_Hidden_tables = attention_section.find_all('table', attrs={"display": "none"})
    # Extract Headers
    headers = ''.join(str(th) for th in attention_tables[0].find_all('th'))
    #Extract Rows
    #hidden_rows = ''.join(''.join(str(tr) for tr in attention_Hidden_tables[0].find_all('tr')[1:]) for table in attention_Hidden_tables)
    all_rows = ''.join(''.join(str(tr) for tr in table.find_all('tr')[1:]) for table in attention_tables)
    #all_rows = hidden_rows + all_rows
    # Create Email Content
    email_body = f"""
    <html>
    <head>
    {css_style}
    </head>
    <body>
    <h2>Overall Summary</h2>
    {overall_summary_table}
    <h2>Transactions That Need Attention</h2>
    <table id="Transactions That Need Attention">
    <tr>{headers}</tr>
    {all_rows}
    </table>
    </body>
    """


# Create the email
msg = MIMEMultipart('related')
msg['Subject'] = 'PT Report for ' + app + '-Test Status:' + status
strFrom = 'PT_sla_reports@companyname.com'
#strTo = ['sample1@email.com', 'sample2@email.com', 'sample3@email.com']
strTo = ['sample1@email.com']

msg['From'] = strFrom
msg['To'] = ", ".join(strTo)


# Add the body


# Send the email
part = MIMEText(email_body, "html")
msg.attach(part)

smtp = smtplib.SMTP("companymtp.Shouldbehere.com", 25, timeout=120)
smtp.sendmail(strFrom, strTo, msg.as_string())
smtp.close()


