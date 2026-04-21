# 🌌 Performance Test Report Automation Suite

<p align="center">
<img src="https://img.shields.io/badge/Performance-Automation-blue?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/JMeter-HTML%20Reports-red?style=for-the-badge&logo=apache&logoColor=white" />
<img src="https://img.shields.io/badge/SLA-Validation-success?style=for-the-badge" />
<img src="https://img.shields.io/badge/PostgreSQL-Dynamic%20SLA-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/GitHub-Actions-black?style=for-the-badge&logo=githubactions" />
<img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=for-the-badge" />
</p>

<p align="center">
<b>Transform Raw Apache JMeter Reports into Executive Dashboards, SLA Decisions & Automated Stakeholder Notifications</b>
</p>

---

# 🚀 Overview

Performance Test Report Automation Suite is an enterprise-grade Python framework that transforms raw Apache JMeter HTML reports into executive dashboards with:

* ✅ Common SLA Validation
* ✅ Dynamic SLA Validation from PostgreSQL
* ✅ PASS / FAIL Decision Engine
* ✅ Error % Analysis
* ✅ Transactions Need Attention Section
* ✅ Auto Email Notifications
* ✅ GitHub Actions / Jenkins Ready
* ✅ Stakeholder Friendly Executive Reports

---

# 🌑 Hero Banner

```text
██████╗ ███████╗██████╗ ███████╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔════╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗████╗ ████║
██████╔╝█████╗  ██████╔╝█████╗  ██║   ██║██████╔╝██╔████╔██║
██╔═══╝ ██╔══╝  ██╔══██╗██╔══╝  ██║   ██║██╔══██╗██║╚██╔╝██║
██║     ███████╗██║  ██║██║     ╚██████╔╝██║  ██║██║ ╚═╝ ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝
```

---

# 🎯 Business Value

This automation removes manual effort after every load test.

| Traditional Process   | Automated Here |
| --------------------- | -------------- |
| Manually check APIs   | ✅              |
| Verify SLA row by row | ✅              |
| Build Summary         | ✅              |
| Email stakeholders    | ✅              |
| Decide Go / No-Go     | ✅              |

---

# 📁 Project Structure

```bash
PerformanceTestAutomations/
├── NewGenaratePTReportCommonSLA.py
├── NewGeneratePTReport_DynamicSLA.py
├── requirements.txt
├── .github/
│   └── workflows/
│       └── performance-report.yml
├── screenshots/
└── README.md
```

---

# ⚡ Core Modules

## 1️⃣ Common SLA Script

```bash
NewGenaratePTReportCommonSLA.py
```

Use one SLA for all transactions or row-wise SLA list.

Examples:

```bash
2000
2000,3000,5000
```

---

## 2️⃣ Dynamic SLA Script

```bash
NewGeneratePTReport_DynamicSLA.py
```

Fetches SLA from PostgreSQL table:

```sql
autodefect.perf_sla
```

Sample:

| app     | transaction | sla    |
| ------- | ----------- | ------ |
| Billing | Login API   | 3000ms |
| Billing | Search API  | 5000ms |

---

# 🏗 Architecture

```text
Apache JMeter Execution
        │
        ▼
Raw HTML Report Generated
        │
        ▼
Python Automation Engine
        │
 ┌──────┴───────────┐
 ▼                  ▼
Common SLA      Dynamic SLA
Engine          Engine
                    │
                    ▼
              PostgreSQL DB
        │
        ▼
Executive Dashboard
        │
        ▼
SMTP Email Alerts
        │
        ▼
Stakeholders
```

---

# 📊 Dashboard Preview

## Executive Summary

```text
┌──────────────────────────────────────┐
│ Application : Billing Platform      │
│ Environment : SIT                   │
│ Users       : 500                   │
│ Duration    : 60 Min                │
│ Status      : PASS / GO ✅          │
│ Error %     : 0.01                  │
│ SLA Failed  : 0                     │
└──────────────────────────────────────┘
```

## Transactions Need Attention

```text
┌────────────────────────────────────────────┐
│ Transaction   Avg Time   SLA   Result     │
├────────────────────────────────────────────┤
│ Login API     4.5 sec    3s    ❌ Missed  │
│ Search API    6.0 sec    5s    ❌ Missed  │
│ Payment API   2.0 sec    2s    ✅ Met     │
└────────────────────────────────────────────┘
```

---

# 🔥 PASS / FAIL Logic

Run marked FAIL if:

* ❌ Success Rate < 99%
* ❌ Any SLA Breach
* ❌ Any Transaction Error > 3%

Else:

```text
PASS / GO ✅
```

---

# ⚙ Installation

```bash
git clone https://github.com/yourusername/PerformanceTestAutomations.git
cd PerformanceTestAutomations
pip install -r requirements.txt
```

---

# ▶ Usage

## Common SLA Mode

```bash
python NewGenaratePTReportCommonSLA.py 2000 Billing SIT APP123 UI_API 500 3600 CHG123 10AM 11AM Login team@company.com report.html
```

## Dynamic SLA Mode

```bash
python NewGeneratePTReport_DynamicSLA.py Billing SIT APP123 UI_API 500 3600 CHG123 10AM 11AM Login team@company.com report.html
```

---

# 🤖 GitHub Actions CI/CD

Create file:

```bash
.github/workflows/performance-report.yml
```

```yaml
name: Performance Report Automation

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: 3.11

      - name: Install Dependencies
        run: pip install beautifulsoup4 psycopg2

      - name: Run Script
        run: |
          python NewGeneratePTReport_DynamicSLA.py \
          Billing SIT APP123 UI_API 500 3600 CHG123 \
          10AM 11AM Login team@company.com report.html
```

---

# 🔐 Security Recommendations

Move credentials to:

```text
.env
GitHub Secrets
AWS Secrets Manager
Azure Key Vault
Hashicorp Vault
```

---

# 📈 Future Roadmap

* ✅ Historical Trend Charts
* ✅ PDF Export
* ✅ Slack / Teams Notifications
* ✅ AI Root Cause Summary
* ✅ Grafana Integration
* ✅ Docker Support
* ✅ REST API Trigger

---

# 👨‍💻 Author

## Sreenivasula Reddy Mukkamalla

Lead Performance Test Engineer

Specialized in:

* Performance Engineering
* JMeter
* LoadRunner
* Chaos Testing
* Python Automation
* DevOps CI/CD
* Executive Reporting

---

# 🌟 Why Recruiters Like This Project

This repository demonstrates:

* ✅ Real Enterprise Automation
* ✅ Python Development Skills
* ✅ CI/CD Integration
* ✅ Reporting Engineering
* ✅ Database Connectivity
* ✅ Performance Testing Expertise

---

# ⭐ Support

If you like this project:

* ⭐ Star the repo
* 🍴 Fork it
* 📩 Connect for collaboration

---

# 🎯 Suggested Repository Name

```text
enterprise-performance-report-automation
```

---

# 🌌 Final Tagline

```text
Turning Raw Load Test Data into Executive Decisions.
```
