import csv
import os


class COAPayrollEngine:
    def __init__(self, csv_path):
        self.csv_path = csv_path

    def validate_and_process(self):
        if not os.path.exists(self.csv_path):
            return None, "Error: Master authoritative file directory empty."

        try:
            processed_payroll = []
            required_columns = ['employee_id', 'name', 'daily_rate', 'days_worked', 'tardiness_mins']

            with open(self.csv_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                if not all(col in reader.fieldnames for col in required_columns):
                    return None, "Error: CSV structure validation failure. Matrix columns altered."

                for row in reader:
                    gross_pay = float(row['daily_rate']) * float(row['days_worked'])
                    tardiness_deduction = round((float(row['daily_rate']) / 8) * (float(row['tardiness_mins']) / 60), 2)
                    gsis_deduction = round(gross_pay * 0.09, 2) if gross_pay > 0 else 0
                    philhealth_deduction = round(gross_pay * 0.02, 2) if gross_pay > 0 else 0

                    total_deductions = tardiness_deduction + gsis_deduction + philhealth_deduction
                    net_pay = gross_pay - total_deductions
                    if net_pay < 0:
                        net_pay = 0.00

                    processed_payroll.append({
                        'employee_id': str(row['employee_id']),
                        'name': row['name'],
                        'gross_pay': round(gross_pay, 2),
                        'deductions': round(total_deductions, 2),
                        'net_pay': round(net_pay, 2),
                        'status': 'Pending Approval'
                    })

            return processed_payroll, "Payroll registry generated and sent for Super Admin review."
        except Exception as e:
            return None, f"System Error processing registry: {str(e)}"import csv
import os

class COAPayrollEngine:
    def __init__(self, csv_path):
        self.csv_path = csv_path

    def validate_and_process(self):
        if not os.path.exists(self.csv_path):
            return None, "Error: Master authoritative file directory empty."

        try:
            processed_payroll = []
            required_columns = ['employee_id', 'name', 'daily_rate', 'days_worked', 'tardiness_mins']
            
            with open(self.csv_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if not all(col in reader.fieldnames for col in required_columns):
                    return None, "Error: CSV structure validation failure. Matrix columns altered."
                
                for row in reader:
                    gross_pay = float(row['daily_rate']) * float(row['days_worked'])
                    tardiness_deduction = round((float(row['daily_rate']) / 8) * (float(row['tardiness_mins']) / 60), 2)
                    gsis_deduction = round(gross_pay * 0.09, 2) if gross_pay > 0 else 0
                    philhealth_deduction = round(gross_pay * 0.02, 2) if gross_pay > 0 else 0

                    total_deductions = tardiness_deduction + gsis_deduction + philhealth_deduction
                    net_pay = gross_pay - total_deductions
                    if net_pay < 0:
                        net_pay = 0.00

                    processed_payroll.append({
                        'employee_id': str(row['employee_id']),
                        'name': row['name'],
                        'gross_pay': round(gross_pay, 2),
                        'deductions': round(total_deductions, 2),
                        'net_pay': round(net_pay, 2),
                        'status': 'Pending Approval'
                    })

            return processed_payroll, "Payroll registry generated and sent for Super Admin review."
        except Exception as e:
            return None, f"System Error processing registry: {str(e)}"