// Copyright (c) 2025, safdar ali and contributors
// For license information, please see license.txt




frappe.ui.form.on('Over Time Settings', {
    refresh(frm) {
        frm.set_query('department', function () {
            return {
                query: "over_time_kdlb.events.get_departments.get_departments",
                filters: {
                    
                }
            };
        });
    }
});
