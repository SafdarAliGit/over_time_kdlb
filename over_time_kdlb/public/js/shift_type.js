frappe.realtime.on('timesheet_creation_complete', function (data) {
    frappe.show_alert({
        message: data.message,
        indicator: data.success ? 'green' : 'red'
    }, 7);
});

frappe.ui.form.on('Shift Type', {
    refresh: function (frm) {
        // Add custom button
        frm.add_custom_button('Create Timesheet For DOT', function () {
            // Open a dialog to get start_date and end_date
            const currentDate = frappe.datetime.get_today();
            const oneMonthBack = frappe.datetime.add_months(currentDate, -1);

            let dialog = new frappe.ui.Dialog({
                title: 'Enter Date Range',
                fields: [
                    {
                        fieldname: 'start_date',
                        label: 'Start Date',
                        fieldtype: 'Date',
                        default: oneMonthBack,
                        reqd: true
                    },
                    {
                        fieldname: 'end_date',
                        label: 'End Date',
                        fieldtype: 'Date',
                        default: currentDate,
                        reqd: true
                    }
                ],
                primary_action_label: 'Create',
                primary_action(values) {

                    // Call the server-side function
                    frappe.call({
                        method: "over_time_kdlb.events.create_timesheet.create_timesheet",
                        args: {
                            start_date: values.start_date,
                            end_date: values.end_date
                        },
                        callback: function (response) {

                        }
                    });

                    // Close the dialog
                    dialog.hide();
                }
            });

            // Show the dialog
            dialog.show();
        });
    }
});

