import os
from werkzeug.security import generate_password_hash, check_password_hash

class User:
    def __init__(self, user_id, name, raw_password, role):
        self.user_id = str(user_id)
        self.name = name
        self.password_hash = generate_password_hash(raw_password)
        self.role = role

    def verify_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

class PayrollRecord:
    def __init__(self, employee_id, name, gross_pay, deductions, net_pay, status="Pending Approval"):
        self.employee_id = str(employee_id)
        self.name = name
        self.gross_pay = float(gross_pay)
        self.deductions = float(deductions)
        self.net_pay = float(net_pay)
        self.status = status

    def to_dict(self):
        return {
            'employee_id': self.employee_id,
            'name': self.name,
            'gross_pay': self.gross_pay,
            'deductions': self.deductions,
            'net_pay': self.net_pay,
            'status': self.status
        }

class MockDatabase:
    def __init__(self):
        self.users = {}
        self.payroll_registry = {}
        self._initialize_default_accounts()

    def _initialize_default_accounts(self):
        self.add_user(User("super_admin", "Super Admin", "admin123", "Super Admin"))
        self.add_user(User("hr_clerk", "HR Clerk", "clerk123", "HR Clerk"))

    def add_user(self, user_obj):
        if user_obj.user_id not in self.users:
            self.users[user_obj.user_id] = user_obj
            return True
        return False

    def get_user(self, user_id):
        return self.users.get(str(user_id))

    def update_payroll(self, records_list):
        self.payroll_registry.clear()
        for rec in records_list:
            self.payroll_registry[rec['employee_id']] = PayrollRecord(
                employee_id=rec['employee_id'],
                name=rec['name'],
                gross_pay=rec['gross_pay'],
                deductions=rec['deductions'],
                net_pay=rec['net_pay'],
                status=rec.get('status', 'Pending Approval')
            )

    def approve_all_payroll(self):
        for record in self.payroll_registry.values():
            if record.status == "Pending Approval":
                record.status = "Approved"

    def get_payroll_by_employee(self, employee_id):
        record = self.payroll_registry.get(str(employee_id))
        return record.to_dict() if record else None

    def get_all_payroll(self):
        return [record.to_dict() for record in self.payroll_registry.values()]