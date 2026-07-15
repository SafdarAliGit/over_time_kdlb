import frappe
from frappe import print_sql
from frappe.query_builder import DocType
from datetime import date, datetime, timedelta, time
from frappe.utils import time_diff_in_hours
from frappe.query_builder import DocType
from .holiday_work import get_holiday_work

today = date.today()


@frappe.whitelist()
def create_timesheet(**args):
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    frappe.enqueue(
        _create_timesheets_job,
        queue="long",
        timeout=1500,
        job_name=f"create_timesheets_{start_date}_{end_date}",
        start_date=start_date,
        end_date=end_date,
        user=frappe.session.user,
    )
    return frappe.msgprint(
        f"Timesheet creation for {start_date} to {end_date} has been queued and will run in the background. "
        "You will be notified once it completes."
    )


def _create_timesheets_job(start_date, end_date, user):
    try:
        create_timesheets_for_employees(start_date, end_date)
        frappe.publish_realtime(
            "timesheet_creation_complete",
            {
                "success": True,
                "message": f"Timesheets created successfully for {start_date} to {end_date}.",
            },
            user=user,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Timesheet Background Job Failed")
        frappe.publish_realtime(
            "timesheet_creation_complete",
            {
                "success": False,
                "message": f"Timesheet creation failed for {start_date} to {end_date}. Check Error Log for details.",
            },
            user=user,
        )


# def over_time(shift, in_time, out_time):
#     default_shift_type = frappe.get_doc("Shift Type", shift)
#     today = date.today()
#     first_in_datetime = datetime.combine(today, (in_time).time())
#     last_out_datetime = datetime.combine(today, (out_time).time())
#     shift_start_datetime = datetime.combine(today, (datetime.min + default_shift_type.start_time).time())
#     # shift_end_datetime = datetime.combine(today, (datetime.min + default_shift_type.end_time).time())
#     # Adjust first_in_datetime if it's earlier than shift start
#     if first_in_datetime < shift_start_datetime:
#         first_in_datetime = shift_start_datetime

#     over_time = (last_out_datetime - first_in_datetime).total_seconds() / 3600
#     if over_time > 9:
#         over_time = over_time - 9
#     else:
#         over_time = 0
#     return over_time

def over_time(shift, in_time, out_time):
    default_shift_type = frappe.get_doc("Shift Type", shift)
    today = date.today()
    first_in_datetime = datetime.combine(today, (in_time).time())
    last_out_datetime = datetime.combine(today, (out_time).time())
    shift_start_datetime = datetime.combine(today, (datetime.min + default_shift_type.start_time).time())
    shift_end_datetime = datetime.combine(today, (datetime.min + default_shift_type.end_time).time())
    # Adjust first_in_datetime if it's earlier than shift start
    if first_in_datetime < shift_start_datetime:
        first_in_datetime = shift_start_datetime

    over_time = (last_out_datetime - shift_end_datetime).total_seconds() / 3600
    return over_time


def create_timesheets_for_employees(start_date, end_date):
    consider_over_time = 0
    department = []
    settings = get_over_time_settings()
    if "error" in settings:
        print(settings["error"])
    else:
        consider_over_time =  settings["consider_over_time"]
        department = [item.department for item in settings["department"]]

    Attendance = DocType("Attendance")
    # Build the query
    query = (
        frappe.qb.from_(Attendance)
        .select(
            Attendance.in_time,
            Attendance.out_time,
            Attendance.department,
            Attendance.name,
            Attendance.employee,
            Attendance.shift,
            Attendance.working_hours,
            Attendance.attendance_date
        )
        .where(
            (Attendance.attendance_date >= start_date)
            & (Attendance.attendance_date <= end_date)
            & (Attendance.department.isin(department))
            & Attendance.in_time.isnotnull()
            & Attendance.out_time.isnotnull()
            & (Attendance.docstatus == 1)
        )
    )

    attendance_data = query.run(as_dict=True)

    # Group attendances by employee
    employee_attendances = {}
    for record in attendance_data:
        ts_not_present = timesheet_not_present(record.employee, start_date, end_date)

        overtime = 0
        overtime = over_time(record.shift, record.in_time, record.out_time)
        
        working_hours = record["working_hours"]
        holiday_work = get_holiday_work(settings["holiday_list"],record["attendance_date"])
        award_on_over_time = settings["award_on_over_time"]
        award_hours = settings["award_hours"]
        on_over_time_hours = settings["on_over_time_hours"]
        if holiday_work:
            overtime = working_hours
        # else:
        #     if working_hours > 9:
        #         overtime = working_hours - 9
        #     else:
        #         overtime = 0
        if overtime > consider_over_time and record.department in department and ts_not_present:
            employee = record["employee"]
            if employee not in employee_attendances:
                employee_attendances[employee] = []
            if overtime >= on_over_time_hours and award_on_over_time:
                overtime += award_hours
            record["over_time"] = overtime
            employee_attendances[employee].append(record)

    # Create a Timesheet for each employee
    for employee, attendances in employee_attendances.items():
        # Create a new Timesheet
        sum_over_time = 0
        timesheet_doc = frappe.new_doc("Timesheet")
        timesheet_doc.employee = employee

        # Add attendance entries to the child table
        for attendance in attendances:
            # early_in_over_time = 0
            timesheet_detail = timesheet_doc.append("time_logs", {})
            timesheet_detail.activity_type = "Execution"
            timesheet_detail.from_time = attendance["in_time"]
            timesheet_detail.to_time = attendance["out_time"]
            timesheet_detail.custom_checkin_time = attendance["in_time"]
            timesheet_detail.checkout_time = attendance["out_time"]
            # early_in_over_time = calculate_over_time(attendance["in_time"]) 
            timesheet_detail.custom_modified_checkin_time = 0 # normalize_in_time(attendance["in_time"])
            timesheet_detail.over_time_kdlb = float(attendance["over_time"]) # + early_in_over_time
            timesheet_detail.custom_attendance = attendance["name"]
            sum_over_time += timesheet_detail.over_time_kdlb

        # Save the Timesheet
        timesheet_doc.custom_over_time_kdlb = sum_over_time
        timesheet_doc.save()
        frappe.db.commit()  # Commit to save changes to the database


def timesheet_not_present(employee, start_date, end_date):
    """
    Check if a Timesheet record exists for the given employee, start_date, and end_date.
    Returns True if no record is found, False otherwise.
    """
    Timesheet = DocType("Timesheet")

    # Build the query
    query = (
        frappe.qb.from_(Timesheet)
        .select(Timesheet.name)
        .where(
            (Timesheet.employee == employee)
            & (Timesheet.start_date >= start_date)
            & (Timesheet.end_date <= end_date)
        )
    )

    # Execute the query and fetch results
    result = query.run(as_dict=True)

    # Return True if no record is found, False otherwise
    return len(result) == 0


def get_over_time_settings():
    """
    Fetch and return the data from the Over Time Settings single doctype,
    specifically the `consider_over_time` and `department` fields.
    """
    try:
        # Fetch single doctype data
        settings = frappe.get_single("Over Time Settings")

        # Extract relevant fields
        data = {
            "consider_over_time": settings.consider_over_time,
            "department": settings.department if settings.department else [],
            "holiday_list": settings.holiday_list,
            "award_on_over_time": settings.award_on_over_time,
            "award_hours": settings.award_hours,
            "on_over_time_hours": settings.on_over_time_hours or 0
        }
        return data

    except frappe.DoesNotExistError:
        # Handle the case where the single doctype is not configured
        return {"error": "Over Time Settings single doctype is not configured."}



def calculate_over_time(in_time):
    """
    Calculate overtime: 0.5 if in_time <= 09:30 else 0.
    Accepts string "dd/mm/yyyy HH:MM" or datetime object.
    """
    try:
        # Convert string to datetime if needed
        if isinstance(in_time, str):
            in_time_obj = datetime.strptime(in_time, "%d/%m/%Y %H:%M")
        elif isinstance(in_time, datetime):
            in_time_obj = in_time
        else:
            return 0.0  # Unknown type, safe fallback

        # Create 09:30 datetime on same day
        check_time = datetime.combine(in_time_obj.date(), time(9, 30))

        return 0.5 if in_time_obj <= check_time else 0.0

    except Exception as e:
        return 0.0


def normalize_in_time(in_time):
    """
    If in_time <= 09:30, return datetime set to 09:00 of the same day.
    Otherwise, return in_time unchanged.

    :param in_time: datetime
    :return: datetime
    """

    # Safety check (ERPNext sometimes passes None)
    if not isinstance(in_time, datetime):
        return in_time

    check_time = datetime.combine(in_time.date(), time(9, 30))
    normalized_time = datetime.combine(in_time.date(), time(9, 0))

    if in_time <= check_time:
        return normalized_time

    return in_time
