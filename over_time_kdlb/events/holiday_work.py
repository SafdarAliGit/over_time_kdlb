import frappe

def get_holiday_work(holiday_list_name,date):
    # Fetch the Holiday List doc
    holiday_list = frappe.get_doc("Holiday List", holiday_list_name)

    # Extract dates from child table
    dates = [holiday.holiday_date for holiday in holiday_list.holidays]
    if date in dates:
        return True
    return False
