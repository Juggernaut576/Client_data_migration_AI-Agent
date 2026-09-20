import os
import pandas as pd

os.makedirs("data/sample_sources", exist_ok=True)

# 1. Source A: Legacy HRIS Export (CSV)
data_a = [
    {
        "emp_no": "EMP-1001",
        "first_name": "  Alice  ",
        "last_name": "Smith",
        "work_email": "alice.smith@acme-corp.com",
        "dept": "engineering",
        "designation": "Senior Staff Engineer",
        "DOJ": "15/01/2021",
        "Annual_Salary": "145000",
        "emp_status": "Active",
        "mobile": "+1 (555) 234-5678"
    },
    {
        "emp_no": "EMP-1002",
        "first_name": "Bob",
        "last_name": "Johnson",
        "work_email": "bob.johnson@acme-corp.com",
        "dept": "Product",
        "designation": "Lead Product Manager",
        "DOJ": "2020-06-01",
        "Annual_Salary": "138000",
        "emp_status": "ACTIVE",
        "mobile": "555-876-5432"
    },
    {
        "emp_no": "EMP-1003",
        "first_name": "Carlos",
        "last_name": "Mendez",
        "work_email": "carlos.m@acme-corp.com",
        "dept": "Sales",
        "designation": "Account Executive",
        "DOJ": "12-Nov-2019",
        "Annual_Salary": "-50000",  # INTENTIONAL ESCALATION: Negative salary
        "emp_status": "Active",
        "mobile": "+1 555 456 7890"
    },
    {
        "emp_no": "EMP-1004",
        "first_name": "Diana",
        "last_name": "Prince",
        "work_email": "diana.prince@acme-corp.com",
        "dept": "Human Resources",
        "designation": "HR Generalist",
        "DOJ": "2022/03/15",
        "Annual_Salary": "88000",
        "emp_status": "On_Leave",
        "mobile": "(555) 789-0123"
    }
]
df_a = pd.DataFrame(data_a)
df_a.to_csv("data/sample_sources/source_a_hris.csv", index=False)
print("Created source_a_hris.csv")

# 2. Source B: Payroll System Export (XLSX)
data_b = [
    {
        "Worker_ID": "EMP-1001",  # OBVIOUS DUPLICATE of Alice Smith: should auto-merge safely
        "fname": "Alice",
        "lname": "Smith",
        "mail": "alice.smith@acme-corp.com",
        "division": "Engineering",
        "role": "Senior Staff Engineer",
        "start_date": "2021-01-15",
        "ctc": 145000,
        "state": "ACTIVE",
        "cell": "+1 555-234-5678"
    },
    {
        "Worker_ID": "EMP-1005",
        "fname": "Evan",
        "lname": "Wright",
        "mail": "evan.w@acme-corp.com",
        "division": "Finance",
        "role": "Financial Analyst",
        "start_date": "05/18/2023",
        "ctc": 95000,
        "state": "ACTIVE",
        "cell": "+1 555-321-6549"
    },
    {
        "Worker_ID": "EMP-1006",  # CONFLICTING RECORD with Source C below (same email, contradictory department)
        "fname": "Fiona",
        "lname": "Gallagher",
        "mail": "fiona.g@acme-corp.com",
        "division": "Operations",
        "role": "Operations Manager",
        "start_date": "2021-08-10",
        "ctc": 105000,
        "state": "ACTIVE",
        "cell": "+1 555-987-6543"
    }
]
df_b = pd.DataFrame(data_b)
df_b.to_excel("data/sample_sources/source_b_payroll.xlsx", index=False)
print("Created source_b_payroll.xlsx")

# 3. Source C: CRM & Contractors Export (CSV)
data_c = [
    {
        "Staff_ID": "EMP-1006",  # CONFLICT: Source B says Fiona is in Operations, Source C says Sales!
        "given_name": "Fiona",
        "family_name": "Gallagher",
        "contact_email": "fiona.g@acme-corp.com",
        "team": "Sales",  # Conflicting Department
        "position": "Sales Lead",  # Conflicting Role
        "date_of_joining": "2021-08-10",
        "compensation": "115000",  # Conflicting Salary
        "work_status": "ACTIVE",
        "phone": "+1 555-987-6543"
    },
    {
        "Staff_ID": "EMP-1007",
        "given_name": "George",
        "family_name": "Miller",
        "contact_email": "george.miller@acme-corp.com",
        "team": "Customer Success",
        "position": "CS Representative",
        "date_of_joining": "2023-11-01",
        "compensation": "72000",
        "work_status": "ACTIVE",
        "phone": "+1 555-111-2233"
    },
    {
        "Staff_ID": "EMP-1008",
        "given_name": "Hannah",
        "family_name": "Abbott",
        "contact_email": "hannah.a@acme-corp.com",
        "team": "Engineering",
        "position": "Frontend Developer",
        "date_of_joining": "invalid-date-format-32/99",  # INTENTIONAL ESCALATION: Unparseable date
        "compensation": "92000",
        "work_status": "Active",
        "phone": "+1 555-444-5566"
    }
]
df_c = pd.DataFrame(data_c)
df_c.to_csv("data/sample_sources/source_c_crm_staff.csv", index=False)
print("Created source_c_crm_staff.csv")
