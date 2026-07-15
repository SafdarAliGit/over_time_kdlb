import frappe


def submit(self, method):
    employee = frappe.get_doc("Employee", self.employee)
    employee.custom_over_time_kdlb = self.custom_over_time_kdlb if self.custom_over_time_kdlb else 0
    employee.save()

def cancel(self, method):
    employee = frappe.get_doc("Employee", self.employee)
    employee.custom_over_time_kdlb = 0
    employee.save()