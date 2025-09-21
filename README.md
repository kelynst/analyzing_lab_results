# 🧪 analyzing_lab_results  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool to **clean and analyze lab results** from CSV files, compute summary stats, and **flag out-of-range values** using simple reference ranges. Great for learning data cleaning, validation rules, and reporting in healthcare analytics.

> ⚠️ Uses **synthetic/public-style** data and simple reference ranges for demo purposes only. Not for clinical use.

---

## 📌 Project Overview
- **Goal** → Load lab results, clean/normalize fields, compute stats, and flag high/low values.
- **Approach** → Read a CSV, standardize columns, apply reference ranges (optionally by sex/age), export:
  - `cleaned_<file>.csv`
  - `flags_<file>.csv` (only abnormal rows)
  - `summary_<file>.csv` (counts/means by test, patient, etc.)
  - `outputs/` charts (per-test distribution)

---

## 📂 Repo Structure
analyzing_lab_results/
│── labs_analyzer.py       # Main analysis script  
│── requirements.txt       # Dependencies (pandas, matplotlib, etc.)  
│── sample_labs.csv        # Example dataset (demo lab results)  
│── README.md              # Documentation  
│── .gitignore             # Ignore .venv, caches, large files  
│── outputs/               # Example charts/visualizations, CSV outputs  

---

## ✅ Features
- Cleans blank rows/columns & trims whitespace  
- Parses common date columns to ISO (`YYYY-MM-DD`)  
- Flexible column matching (e.g., `patient_id` vs `PatientID`)  
- Simple **reference range** checks (by test; optional by sex/age)  
- Exports **cleaned**, **flagged**, and **summary** CSVs  
- Saves basic charts (histograms per test) to `outputs/`  

---

# 📄 requirements.txt
```txt
pandas==2.2.2
matplotlib==3.8.4
```
To install manually:
```bash
pip install -r requirements.txt
```

## 🚀 Installation
```bash
git clone https://github.com/kelynst/analyzing_lab_results.git
cd analyzing_lab_results
```
Create a virtual environment:
```bash
python3 -m venv .venv
```
Activate it:
-macOS/Linux
```bash
source .venv/bin/activate
```
-Windows (PowerShell):
```bash
.venv\Scripts\Activate
```
-Install deps:
```bash
pip install -r requirements.txt
```

## ▶️ Usage
Run on the included sample:
```bash
python labs_analyzer.py sample_labs.csv
```
Choose grouping for summary (by test_name and sex):
```bash
python labs_analyzer.py sample_labs.csv --by test_name sex
```
Skip charts:
```bash
python labs_analyzer.py sample_labs.csv --no-charts
```
Custom outputs:
```bash
python labs_analyzer.py sample_labs.csv \
  --out-clean cleaned_demo.csv \
  --out-flags flags_demo.csv \
  --out-summary summary_demo.csv \
  --outputs-dir outputs
  ```

## 📝 Example Output (terminal)
```bash
Loading data
• Rows: 8  Cols: 6
• Columns: ['PatientID', 'Sex', 'Test', 'Value', 'Units', 'Date']

Normalizing schema
• patient_id → 'PatientID'
• sex        → 'Sex'
• test_name  → 'Test'
• value      → 'Value'
• units      → 'Units'
• date       → 'Date'

Flagging out-of-range values
• Reference ranges applied for: HGB, WBC, GLU

Summarizing
• Summary rows: 6

Saving CSVs
• Cleaned CSV : cleaned_sample_labs.csv
• Flags CSV   : flags_sample_labs.csv
• Summary CSV : summary_sample_labs.csv

Plotting
• Charts saved in: outputs

✅ Lab Analysis Complete
• Input         : sample_labs.csv
• Cleaned CSV   : cleaned_sample_labs.csv
• Flags CSV     : flags_sample_labs.csv
• Summary CSV   : summary_sample_labs.csv
• Rows (clean)  : 8
• Charts dir    : outputs
```
---

## 🧪 Reference Ranges Demo  
Example ranges for common lab values (synthetic, not clinical use):  

| Test            | Normal Range        | Units  |
|-----------------|---------------------|--------|
| Hemoglobin      | 12.0 – 16.0         | g/dL   |
| White Blood Cell| 4.0 – 11.0          | K/µL   |
| Glucose (fasting)| 70 – 99            | mg/dL  |
| Platelets       | 150 – 450           | K/µL   |

⚠️ *Values are for demo only — real ranges depend on lab, age, sex, and context.*  

---

## 🔮 Future Improvements  
- Expand support for more lab test types  
- Add trend analysis (patient results over time)  
- Export summaries to Excel or databases  
- Integrate HL7/FHIR formats for EHR compatibility  
- Add interactive charts for better visualization  

---

## 🤝 Contributing  
Contributions are welcome!  
1. Fork the repo  
2. Create a new branch (`git checkout -b feature-xyz`)  
3. Commit your changes (`git commit -m "Add feature xyz"`)  
4. Push to your branch (`git push origin feature-xyz`)  
5. Submit a pull request 🎉  

---

## ⚠️ Notes  
- Dataset is synthetic/demo only — no real patient data included.  
- This tool is for **educational/portfolio purposes only**, not medical advice.  
- Always consult real laboratory reference ranges and clinical guidelines.  

---

## 📜 License
MIT — see LICENSE.
---

# 📄 requirements.txt
```txt
pandas==2.2.2
matplotlib==3.8.4
```

## 🙈 .gitignore
```txt
.venv/
__pycache__/
*.pyc
.DS_Store
outputs/
cleaned_*.csv
flags_*.csv
summary_*.csv
```
## 🧪 sample_labs.csv
```csv
PatientID,Sex,Test,Value,Units,Date
1001,M,HGB,12.8,g/dL,2025-01-02
1002,F,HGB,16.2,g/dL,2025-01-03
1003,M,WBC,5.2,10^9/L,2025-01-05
1004,F,WBC,12.1,10^9/L,2025-01-06
1005,M,GLU,65,mg/dL,2025-01-07
1006,F,GLU,102,mg/dL,2025-01-08
1007,M,HGB,14.9,g/dL,2025-01-09
1008,F,HGB,11.4,g/dL,2025-01-10
```
## 📜 License
MIT — see LICENSE.