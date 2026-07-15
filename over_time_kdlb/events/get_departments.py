import frappe
import json

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_departments(doctype, txt, searchfield, start, page_len, filters):
    selected = filters.get("departments")
    selected = json.loads(selected) if selected else []

    return frappe.db.sql("""
        SELECT name
        FROM `tabDepartment`
        WHERE is_group = 0
          AND (%(txt)s = '' OR name LIKE %(like_txt)s)
          AND name NOT IN %(selected)s
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """, {
        "txt": txt or "",
        "like_txt": f"%{txt}%",
        "selected": tuple(selected) or ("",),
        "start": start,
        "page_len": page_len
    })
