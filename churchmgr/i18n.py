"""The words on screen in Tiếng Việt and English (the text table), and errors the pastor can read.

- Every key is ``<section>.<name>``. The 16 sections come in the order of ``SECTIONS``, in both
  dicts, each one after a ``# --- <section>`` line. Shared words (menu, buttons, roles, kinds,
  weekdays, months) live in ``core``.
- MERGE RULE: a card adds keys ONLY in its own sections, in BOTH dicts, directly after the
  ``# --- <section>`` line. Never reorder, rename or delete other keys.
- The English text is the text the app showed before it had two languages.
- Data is never translated: names, notes, titles and list items are shown as stored.
- This module imports nothing from ``churchmgr``.
"""

import re
from html.parser import HTMLParser

LANGS = ("vi", "en")
DEFAULT_LANG = "vi"
SECTIONS = ("core", "dashboard", "people", "families", "chi_phai", "calendar", "care", "money", "documents",
            "sent", "lists", "copies", "settings", "setup", "search", "errors")

TEXT = {
    "vi": {
        # --- core
        "core.language": "Ngôn ngữ",
        "core.nav_label": "Menu chính",
        "core.months_one": "{n} tháng",
        "core.months_many": "{n} tháng",
        "core.month_year": "{month}/{year}",
        "core.nav_dashboard": "Trang chủ",
        "core.nav_people": "Mọi người",
        "core.nav_families": "Gia đình",
        "core.nav_chi_phai": "Chi phái",
        "core.nav_calendar": "Lịch",
        "core.nav_care": "Thăm viếng",
        "core.nav_money": "Tài chính",
        "core.nav_documents": "Tài liệu",
        "core.nav_sent": "Văn bản đi",
        "core.nav_lists": "Danh mục",
        "core.nav_copies": "Dữ liệu",
        "core.nav_settings": "Cài đặt",
        "core.nav_search": "Tìm kiếm",
        "core.btn_add": "Thêm",
        "core.btn_save": "Lưu",
        "core.btn_edit": "Chỉnh sửa",
        "core.btn_cancel": "Hủy",
        "core.btn_print": "In",
        "core.btn_back": "Quay lại",
        "core.btn_open": "Mở",
        "core.btn_close": "Kết thúc",
        "core.btn_mark_done": "Hoàn tất",
        "core.btn_search": "Tìm kiếm",
        "core.btn_delete": "Xóa",
        "core.family_role_head": "Chủ gia đình",
        "core.family_role_spouse": "Vợ/Chồng",
        "core.family_role_child": "Con",
        "core.family_role_other": "Người thân khác",
        "core.ministry_role_leader": "Trưởng ban",
        "core.ministry_role_member": "Ban viên",
        "core.kind_service": "Giờ thờ phượng",
        "core.kind_meeting": "Buổi họp",
        "core.kind_visit": "Thăm viếng",
        "core.kind_event": "Chương trình",
        "core.weekday_0": "Thứ Hai",
        "core.weekday_1": "Thứ Ba",
        "core.weekday_2": "Thứ Tư",
        "core.weekday_3": "Thứ Năm",
        "core.weekday_4": "Thứ Sáu",
        "core.weekday_5": "Thứ Bảy",
        "core.weekday_6": "Chúa Nhật",
        "core.month_1": "Tháng 1",
        "core.month_2": "Tháng 2",
        "core.month_3": "Tháng 3",
        "core.month_4": "Tháng 4",
        "core.month_5": "Tháng 5",
        "core.month_6": "Tháng 6",
        "core.month_7": "Tháng 7",
        "core.month_8": "Tháng 8",
        "core.month_9": "Tháng 9",
        "core.month_10": "Tháng 10",
        "core.month_11": "Tháng 11",
        "core.month_12": "Tháng 12",
        # --- dashboard
        "dashboard.title": "Trang chủ",
        "dashboard.open_calendar": "Mở Lịch",
        # --- people
        "people.title": "Mọi người",
        "people.add": "Thêm Người",
        "people.count_one": "{n} người",
        "people.count_many": "{n} người",
        # --- families
        "families.title": "Gia đình",
        "families.add": "Thêm Gia đình",
        # --- chi_phai
        "chi_phai.title": "Chi phái",
        "chi_phai.add": "Thêm Chi phái",
        # --- calendar
        "calendar.title": "Lịch",
        "calendar.add": "Thêm Lịch",
        # --- care
        "care.title": "Thăm viếng",
        "care.needs_visit": "Cần thăm viếng",
        "care.care_log": "Nhật ký thăm viếng",
        # --- money
        "money.offering": "Dâng hiến",
        "money.expense": "Khoản chi",
        "money.person": "Người",
        "money.family": "Gia đình",
        "money.date": "Ngày",
        "money.amount": "Số tiền",
        "money.fund": "Quỹ",
        "money.giver": "Người dâng hiến",
        "money.spending_category": "Hạng mục chi",
        "money.note": "Ghi chú",
        "money.year": "Năm",
        "money.given_by": "Người dâng",
        "money.printed": "Ngày in",
        "money.balance": "Số dư",
        "money.start_date": "Ngày bắt đầu",
        "money.end_date": "Ngày kết thúc",
        "money.no_name": "Ẩn danh",
        "money.no_giver": "— Không có Người dâng hiến (Ẩn danh) —",
        "money.group_people": "Người",
        "money.group_families": "Gia đình",
        "money.giver_hint": "Một Người hoặc một Gia đình. Không có Người dâng hiến thì là Ẩn danh.",
        "money.amount_hint": "Số đồng nguyên, ví dụ 1.250.000 hoặc 1250000.",
        "money.offering_note_hint": "Không bắt buộc. Không bao giờ in trên Tổng kết dâng hiến.",
        "money.expense_note_hint": "Chi cho việc gì. Không bắt buộc.",
        "money.hidden_item": "{name} (đã ẩn)",
        "money.this_month": "Tháng này",
        "money.months_label": "Các tháng Tài chính",
        "money.go_to_month": "Đến tháng",
        "money.show": "Xem",
        "money.totals": "Tổng cộng",
        "money.offering_count_one": "{n} khoản Dâng hiến",
        "money.offering_count_many": "{n} khoản Dâng hiến",
        "money.expense_count_one": "{n} Khoản chi",
        "money.expense_count_many": "{n} Khoản chi",
        "money.balance_sub": "Dâng hiến trừ Khoản chi",
        "money.state_up": "Dâng hiến nhiều hơn Khoản chi",
        "money.state_down": "Khoản chi nhiều hơn Dâng hiến",
        "money.finding": "{month} · Số dư {balance} ({state})",
        "money.count_in": "{count} trong {month}",
        "money.total_offerings": "Tổng Dâng hiến",
        "money.total_expenses": "Tổng Khoản chi",
        "money.no_offering_in": "Chưa ghi khoản Dâng hiến nào trong {month}.",
        "money.no_expense_in": "Chưa ghi Khoản chi nào trong {month}.",
        "money.record_offering": "Ghi Dâng hiến",
        "money.record_expense": "Ghi Khoản chi",
        "money.edit_offering_on": "Chỉnh sửa Dâng hiến ngày {date}, {fund}",
        "money.edit_expense_on": "Chỉnh sửa Khoản chi ngày {date}, {category}",
        "money.choose_person": "— Chọn một Người —",
        "money.or_family": "— hoặc một Gia đình —",
        "money.choose_hint": "Chọn một Người hoặc một Gia đình.",
        "money.open_statement": "Mở Tổng kết dâng hiến",
        "money.statement_meta": "Danh sách Dâng hiến trong một năm của một Người dâng hiến, sẵn sàng để in",
        "money.statement_choose": "Chọn một Người hoặc một Gia đình và một năm.",
        "money.edit_offering": "Chỉnh sửa Dâng hiến",
        "money.edit_expense": "Chỉnh sửa Khoản chi",
        "money.offering_now": "Hiện lưu: {amount} ngày {date} · {fund} · {giver} · Ghi lúc {recorded}",
        "money.expense_now": "Hiện lưu: {amount} ngày {date} · {category} · Ghi lúc {recorded}",
        "money.back_to": "Quay lại {month}",
        "money.delete_offering": "Xóa khoản Dâng hiến này",
        "money.delete_expense": "Xóa Khoản chi này",
        "money.delete_hint": "Bạn sẽ được hỏi lại một lần trước khi xóa. Không thể hoàn tác.",
        "money.confirm_offering": "Xóa khoản Dâng hiến {amount} ngày {date}?",
        "money.confirm_expense": "Xóa Khoản chi {amount} ngày {date}?",
        "money.confirm_offering_title": "Xóa khoản Dâng hiến này?",
        "money.confirm_expense_title": "Xóa Khoản chi này?",
        "money.yes_delete": "Có, xóa",
        "money.confirm_hint": "Tổng của tháng và Tổng kết dâng hiến thay đổi ngay. Không thể hoàn tác.",
        "money.offering_detail": "Quỹ {fund} · Người dâng hiến {giver}",
        "money.expense_detail": "Hạng mục chi {category}",
        "money.not_found_title": "Không tìm thấy {what}",
        "money.not_found_text": "Không có {what} nào với mã số này.",
        "money.go_money": "Về Tài chính",
        "money.offering_recorded": "Đã ghi Dâng hiến {amount} ngày {date} ({name}).",
        "money.offering_saved": "Đã lưu Dâng hiến: {amount} ngày {date} ({name}).",
        "money.offering_deleted": "Đã xóa Dâng hiến {amount} ngày {date}.",
        "money.expense_recorded": "Đã ghi Khoản chi {amount} ngày {date} ({name}).",
        "money.expense_saved": "Đã lưu Khoản chi: {amount} ngày {date} ({name}).",
        "money.expense_deleted": "Đã xóa Khoản chi {amount} ngày {date}.",
        "money.statement_title": "Tổng kết dâng hiến {year}",
        "money.total_count": "Tổng ({count})",
        "money.statement_empty": "Người dâng hiến này không có khoản Dâng hiến nào trong năm {year}. Tổng {total}.",
        "money.family_note": "Tổng kết dâng hiến của một Gia đình cũng gồm Dâng hiến của từng Người vào những ngày "
                             "Người đó ở trong Gia đình này.",
        "money.statement_sub": "{name} · {year} · {count} · tổng {total}",
        "money.err_giver": "Người dâng hiến phải là một Người, một Gia đình, hoặc để trống.",
        "money.err_choose_fund": "Quỹ: hãy chọn một Quỹ.",
        "money.err_choose_category": "Hạng mục chi: hãy chọn một Hạng mục chi.",
        "money.err_after_today": "Ngày không được sau hôm nay ({today}). Hãy dùng hôm nay hoặc một ngày trước đó.",
        "money.amount_help": "Hãy ghi số đồng nguyên lớn hơn 0, ví dụ 1250000 hoặc 1.250.000.",
        "money.err_amount_type": "Không đọc được Số tiền. {help}",
        "money.err_amount_empty": "Chưa nhập Số tiền. {help}",
        "money.err_amount_bad": "Không đọc được Số tiền \"{value}\". Không dùng số lẻ, không dùng dấu trừ. {help}",
        "money.err_amount_large": "Số tiền quá lớn.",
        "money.err_amount_int": "Số tiền phải là số đồng nguyên. {help}",
        "money.err_amount_zero": "Số tiền phải lớn hơn 0. {help}",
        "money.err_show_whole": "Chỉ số đồng nguyên mới hiện được thành số tiền.",
        "money.err_month": "Tháng phải là số nguyên từ 1 đến 12.",
        "money.err_end_before_start": "Ngày kết thúc ở trước ngày bắt đầu.",
        "money.err_no_id": "Không có {what} với mã số {id}.",
        "money.err_two_givers": "Một khoản Dâng hiến chỉ có một Người dâng hiến: một Người hoặc một Gia đình, "
                                "không phải cả hai.",
        "money.err_statement_giver": "Tổng kết dâng hiến là của một Người hoặc một Gia đình: hãy chọn đúng một.",
        "money.title": "Tài chính",
        "money.offerings": "Dâng hiến",
        "money.expenses": "Khoản chi",
        "money.giving_statement": "Tổng kết dâng hiến",
        # --- documents
        "documents.title": "Tài liệu",
        "documents.add": "Thêm Tài liệu",
        # --- sent
        "sent.title": "Văn bản đi",
        "sent.add": "Thêm Công văn đi",
        # --- lists
        "lists.title": "Danh mục",
        "lists.status": "Trạng thái",
        # --- copies
        "copies.title": "Dữ liệu",
        "copies.handover": "Bàn giao",
        # --- settings
        "settings.church_name_hint": "Hiện ở đầu mỗi trang, trên Tổng kết dâng hiến và trong tên tệp Bàn giao.",
        "settings.care_months": "Nhắc thăm viếng (tháng)",
        "settings.care_months_hint": "Một Người cần thăm viếng khi lần Thăm viếng gần nhất đã lâu hơn số tháng "
                                     "này. Từ {min} đến {max} tháng; thường là 3.",
        "settings.months_error": "Nhắc thăm viếng phải là số tháng nguyên từ {min} đến {max}.",
        "settings.door_off": "Tắt",
        "settings.door_on": "Bật",
        "settings.door_state_off": "tắt",
        "settings.door_state_on": "bật",
        "settings.door_hint": "Không bắt buộc. Khi Bật, trợ lý Hermes trên máy tính này được đọc Dữ liệu Hội Thánh "
                              "này và lưu hồ sơ mới sau khi được đồng ý. Trợ lý không bao giờ thấy Ghi chú cá nhân.",
        "settings.language_hint": "Chữ trên màn hình. Tên, ghi chú và các mục trong Danh mục vẫn giữ như đã nhập.",
        "settings.panel_church": "Hội Thánh",
        "settings.needs_today": "Cần thăm viếng hôm nay",
        "settings.no_visit_in": "Không có Thăm viếng trong {months} qua, hoặc chưa bao giờ",
        "settings.links": "Xem những người này trong {care}. Các mục để chọn nằm trong {lists}; nơi lưu Dữ liệu "
                          "Hội Thánh này ghi trong {copies}.",
        "settings.panel_care": "Nhắc thăm viếng",
        "settings.panel_care_meta": "Kết quả của Nhắc thăm viếng hôm nay",
        "settings.sub": "nhắc thăm viếng {months}",
        "settings.saved": "Đã lưu cài đặt: {name}, nhắc thăm viếng {months}, Cổng Hermes {door}.",
        "settings.title": "Cài đặt",
        "settings.church_name": "Tên Hội Thánh",
        "settings.hermes_door": "Cổng Hermes",
        "settings.save": "Lưu cài đặt",
        # --- setup
        "setup.intro": "Chưa mở Dữ liệu Hội Thánh nào. Hãy lập một Dữ liệu Hội Thánh trống. Dữ liệu mới chỉ có các "
                       "danh sách có sẵn (Trạng thái, Quỹ, Hạng mục chi, Nơi nhận, Mục đích, Ban ngành).",
        "setup.name_hint": "Ví dụ: Hội Thánh Tin Lành Bình An",
        "setup.language_hint": "Các danh sách có sẵn được lập bằng ngôn ngữ này. Sau này vẫn đổi được ngôn ngữ "
                               "trên màn hình.",
        "setup.start": "Lập dữ liệu Hội Thánh",
        "setup.saved_in": "Dữ liệu được lưu trong {path}, ngoài OneDrive.",
        "setup.title": "Lập dữ liệu Hội Thánh mới",
        "setup.done": "Đã lập dữ liệu Hội Thánh mới. Đây là Trang chủ.",
        # --- search
        "search.title": "Tìm kiếm",
        "search.find_person": "Tìm Người",
        # --- errors
        "errors.not_done": "Chưa làm được",
        "errors.go_back": "Bấm nút Quay lại của trình duyệt, sửa lại rồi thử lần nữa.",
        "errors.not_allowed": "Không được phép",
        "errors.not_allowed_text": "Không mở được trang này theo cách đó.",
        "errors.not_found": "Không tìm thấy trang",
        "errors.not_found_text": "Không có trang này.",
        "errors.go_dashboard": "Về Trang chủ",
        "errors.went_wrong": "Có lỗi xảy ra",
        "errors.went_wrong_text": "Trang này gặp lỗi.",
        "errors.try_again": "Hãy thử lại. Nếu vẫn lỗi, hãy đóng Church Manager rồi mở lại.",
        "errors.required": "Cần nhập {label}.",
        "errors.name_too_long": "{label}: tối đa {max} ký tự.",
        "errors.date": "{label} phải là một ngày có thật, viết YYYY-MM-DD, ví dụ 2026-05-31.",
        "errors.date_years": "{label}: năm phải từ 1900 đến 9999.",
        "errors.datetime": "{label} phải viết YYYY-MM-DD HH:MM, ví dụ 2026-05-31 09:30.",
        "errors.whole_number": "{label} phải là số nguyên.",
        "errors.above_zero": "{label} phải là số nguyên lớn hơn 0.",
        "errors.no_such_id": "Không có {label} với mã số đó.",
        "errors.hermes_door": "Cổng Hermes phải là Bật hoặc Tắt.",
        "errors.setting_value": "Cài đặt {name} cần có giá trị.",
        "errors.care_reminder_months": "Nhắc thăm viếng phải là số tháng nguyên từ 1 đến 120.",
        "errors.language": "Ngôn ngữ phải là Tiếng Việt hoặc English.",
    },
    "en": {
        # --- core
        "core.language": "Language",
        "core.nav_label": "Main",
        "core.months_one": "{n} month",
        "core.months_many": "{n} months",
        "core.month_year": "{month} {year}",
        "core.nav_dashboard": "Dashboard",
        "core.nav_people": "People",
        "core.nav_families": "Families",
        "core.nav_chi_phai": "Chi phái",
        "core.nav_calendar": "Calendar",
        "core.nav_care": "Care",
        "core.nav_money": "Money",
        "core.nav_documents": "Documents",
        "core.nav_sent": "Sent documents",
        "core.nav_lists": "Lists",
        "core.nav_copies": "Copies",
        "core.nav_settings": "Settings",
        "core.nav_search": "Search",
        "core.btn_add": "Add",
        "core.btn_save": "Save",
        "core.btn_edit": "Edit",
        "core.btn_cancel": "Cancel",
        "core.btn_print": "Print",
        "core.btn_back": "Back",
        "core.btn_open": "Open",
        "core.btn_close": "Close",
        "core.btn_mark_done": "Mark done",
        "core.btn_search": "Search",
        "core.btn_delete": "Delete",
        "core.family_role_head": "Head",
        "core.family_role_spouse": "Spouse",
        "core.family_role_child": "Child",
        "core.family_role_other": "Other",
        "core.ministry_role_leader": "Leader",
        "core.ministry_role_member": "Member",
        "core.kind_service": "Service",
        "core.kind_meeting": "Meeting",
        "core.kind_visit": "Visit",
        "core.kind_event": "Event",
        "core.weekday_0": "Mon",
        "core.weekday_1": "Tue",
        "core.weekday_2": "Wed",
        "core.weekday_3": "Thu",
        "core.weekday_4": "Fri",
        "core.weekday_5": "Sat",
        "core.weekday_6": "Sun",
        "core.month_1": "January",
        "core.month_2": "February",
        "core.month_3": "March",
        "core.month_4": "April",
        "core.month_5": "May",
        "core.month_6": "June",
        "core.month_7": "July",
        "core.month_8": "August",
        "core.month_9": "September",
        "core.month_10": "October",
        "core.month_11": "November",
        "core.month_12": "December",
        # --- dashboard
        "dashboard.title": "Dashboard",
        "dashboard.open_calendar": "Open Calendar",
        # --- people
        "people.title": "People",
        "people.add": "Add a Person",
        "people.count_one": "{n} Person",
        "people.count_many": "{n} People",
        # --- families
        "families.title": "Families",
        "families.add": "Add a Family",
        # --- chi_phai
        "chi_phai.title": "Chi phái",
        "chi_phai.add": "Add a Chi phái",
        # --- calendar
        "calendar.title": "Calendar",
        "calendar.add": "Add a Calendar item",
        # --- care
        "care.title": "Care",
        "care.needs_visit": "Needs a visit",
        "care.care_log": "Care log",
        # --- money
        "money.offering": "Offering",
        "money.expense": "Expense",
        "money.person": "Person",
        "money.family": "Family",
        "money.date": "Date",
        "money.amount": "Amount",
        "money.fund": "Fund",
        "money.giver": "Giver",
        "money.spending_category": "Spending category",
        "money.note": "Note",
        "money.year": "Year",
        "money.given_by": "Given by",
        "money.printed": "Printed",
        "money.balance": "Balance",
        "money.start_date": "Start date",
        "money.end_date": "End date",
        "money.no_name": "no-name offering",
        "money.no_giver": "— No Giver (no-name offering) —",
        "money.group_people": "People",
        "money.group_families": "Families",
        "money.giver_hint": "A Person or a Family. With no Giver it is a no-name offering.",
        "money.amount_hint": "Whole dong, for example 1.250.000 or 1250000.",
        "money.offering_note_hint": "Optional. It is never printed on a Giving statement.",
        "money.expense_note_hint": "What it was for. Optional.",
        "money.hidden_item": "{name} (hidden)",
        "money.this_month": "This month",
        "money.months_label": "Money months",
        "money.go_to_month": "Go to a month",
        "money.show": "Show",
        "money.totals": "Totals",
        "money.offering_count_one": "{n} Offering",
        "money.offering_count_many": "{n} Offerings",
        "money.expense_count_one": "{n} Expense",
        "money.expense_count_many": "{n} Expenses",
        "money.balance_sub": "Offerings minus Expenses",
        "money.state_up": "Offerings above Expenses",
        "money.state_down": "Expenses above Offerings",
        "money.finding": "{month} · Balance {balance} ({state})",
        "money.count_in": "{count} in {month}",
        "money.total_offerings": "Total Offerings",
        "money.total_expenses": "Total Expenses",
        "money.no_offering_in": "No Offering recorded in {month}.",
        "money.no_expense_in": "No Expense recorded in {month}.",
        "money.record_offering": "Record Offering",
        "money.record_expense": "Record Expense",
        "money.edit_offering_on": "Edit Offering on {date}, {fund}",
        "money.edit_expense_on": "Edit Expense on {date}, {category}",
        "money.choose_person": "— Choose a Person —",
        "money.or_family": "— or a Family —",
        "money.choose_hint": "Choose one Person or one Family.",
        "money.open_statement": "Open Giving statement",
        "money.statement_meta": "A yearly list of one Giver's Offerings, ready to print",
        "money.statement_choose": "Choose a Person or a Family and a year.",
        "money.edit_offering": "Edit Offering",
        "money.edit_expense": "Edit Expense",
        "money.offering_now": "Saved now: {amount} on {date} · {fund} · {giver} · Recorded {recorded}",
        "money.expense_now": "Saved now: {amount} on {date} · {category} · Recorded {recorded}",
        "money.back_to": "Back to {month}",
        "money.delete_offering": "Delete this Offering",
        "money.delete_expense": "Delete this Expense",
        "money.delete_hint": "You are asked once more before it goes. It cannot be undone.",
        "money.confirm_offering": "Delete this Offering of {amount} on {date}?",
        "money.confirm_expense": "Delete this Expense of {amount} on {date}?",
        "money.confirm_offering_title": "Delete this Offering?",
        "money.confirm_expense_title": "Delete this Expense?",
        "money.yes_delete": "Yes, delete it",
        "money.confirm_hint": "The month totals and the Giving statement change at once. It cannot be undone.",
        "money.offering_detail": "Fund {fund} · Giver {giver}",
        "money.expense_detail": "Spending category {category}",
        "money.not_found_title": "{what} not found",
        "money.not_found_text": "There is no {what} with this number.",
        "money.go_money": "Go to Money",
        "money.offering_recorded": "Offering of {amount} recorded on {date} ({name}).",
        "money.offering_saved": "Offering saved: {amount} on {date} ({name}).",
        "money.offering_deleted": "Offering of {amount} on {date} deleted.",
        "money.expense_recorded": "Expense of {amount} recorded on {date} ({name}).",
        "money.expense_saved": "Expense saved: {amount} on {date} ({name}).",
        "money.expense_deleted": "Expense of {amount} on {date} deleted.",
        "money.statement_title": "Giving statement {year}",
        "money.total_count": "Total ({count})",
        "money.statement_empty": "No Offering from this Giver in {year}. Total {total}.",
        "money.family_note": "A Family statement also lists the Offerings of each Person on the dates when that "
                             "Person was in this Family.",
        "money.statement_sub": "{name} · {year} · {count} · total {total}",
        "money.err_giver": "Giver must be a Person, a Family, or none.",
        "money.err_choose_fund": "Fund: choose a Fund.",
        "money.err_choose_category": "Spending category: choose a Spending category.",
        "money.err_after_today": "Date cannot be after today ({today}). Use today or an earlier date.",
        "money.amount_help": "Write a whole number of dong above 0, for example 1250000 or 1.250.000.",
        "money.err_amount_type": "Amount not understood. {help}",
        "money.err_amount_empty": "Amount is empty. {help}",
        "money.err_amount_bad": "Amount \"{value}\" not understood. No decimals, no minus sign. {help}",
        "money.err_amount_large": "Amount is too large.",
        "money.err_amount_int": "Amount must be a whole number of dong. {help}",
        "money.err_amount_zero": "Amount must be above 0. {help}",
        "money.err_show_whole": "Only a whole number of dong can be shown as money.",
        "money.err_month": "Month must be a whole number from 1 to 12.",
        "money.err_end_before_start": "The end date is before the start date.",
        "money.err_no_id": "No {what} with id {id}.",
        "money.err_two_givers": "An Offering has one Giver: a Person or a Family, not both.",
        "money.err_statement_giver": "A Giving statement is for one Person or one Family: give exactly one of them.",
        "money.title": "Money",
        "money.offerings": "Offerings",
        "money.expenses": "Expenses",
        "money.giving_statement": "Giving statement",
        # --- documents
        "documents.title": "Documents",
        "documents.add": "Add document",
        # --- sent
        "sent.title": "Sent documents",
        "sent.add": "Record a Sent document",
        # --- lists
        "lists.title": "Lists",
        "lists.status": "Status",
        # --- copies
        "copies.title": "Copies",
        "copies.handover": "Handover",
        # --- settings
        "settings.church_name_hint": "Shown at the top of every page, on the Giving statement and in the Handover "
                                     "file name.",
        "settings.care_months": "Care reminder time (months)",
        "settings.care_months_hint": "A Person needs a visit when their last Visit is older than this. "
                                     "{min} to {max} months; 3 is the usual.",
        "settings.months_error": "Care reminder time must be a whole number of months from {min} to {max}.",
        "settings.door_off": "Off",
        "settings.door_on": "On",
        "settings.door_state_off": "off",
        "settings.door_state_on": "on",
        "settings.door_hint": "Optional. On lets the Hermes helper on this computer read this church copy and save "
                              "new records after you say yes. It never sees Private notes.",
        "settings.language_hint": "The words on the screens. Names, notes and list items stay as they were typed.",
        "settings.panel_church": "Church",
        "settings.needs_today": "Needs a visit today",
        "settings.no_visit_in": "No Visit in the last {months}, or never",
        "settings.links": "See them in {care}. The lists of choices are in {lists}; where this church copy is "
                          "saved is in {copies}.",
        "settings.panel_care": "Care reminder",
        "settings.panel_care_meta": "What the care reminder time gives today",
        "settings.sub": "care reminder time {months}",
        "settings.saved": "Settings saved: {name}, care reminder time {months}, Hermes door {door}.",
        "settings.title": "Settings",
        "settings.church_name": "Church name",
        "settings.hermes_door": "Hermes door",
        "settings.save": "Save settings",
        # --- setup
        "setup.intro": "No church copy is open yet. Start a blank church copy. It keeps only the default lists "
                       "(Status, Fund, Spending category, Recipient, Purpose, Ministry).",
        "setup.name_hint": "For example: Hội Thánh Tin Lành Bình An",
        "setup.language_hint": "The default lists are made in this language. The screens can change language later.",
        "setup.start": "Start the church copy",
        "setup.saved_in": "It is saved in {path}, outside OneDrive.",
        "setup.title": "New church setup",
        "setup.done": "New church setup is done. This is your Dashboard.",
        # --- search
        "search.title": "Search",
        "search.find_person": "Find a Person",
        # --- errors
        "errors.not_done": "Not done",
        "errors.go_back": "Use the Back button of the browser, fix it and try again.",
        "errors.not_allowed": "Not allowed",
        "errors.not_allowed_text": "This page cannot be opened that way.",
        "errors.not_found": "Page not found",
        "errors.not_found_text": "This page does not exist.",
        "errors.go_dashboard": "Go to the Dashboard",
        "errors.went_wrong": "Something went wrong",
        "errors.went_wrong_text": "Something went wrong on this page.",
        "errors.try_again": "Try again. If it happens again, close Church Manager and start it again.",
        "errors.required": "{label} is required.",
        "errors.name_too_long": "{label}: use at most {max} characters.",
        "errors.date": "{label} must be a real date written YYYY-MM-DD, for example 2026-05-31.",
        "errors.date_years": "{label}: use a year from 1900 to 9999.",
        "errors.datetime": "{label} must be written YYYY-MM-DD HH:MM, for example 2026-05-31 09:30.",
        "errors.whole_number": "{label} must be a whole number.",
        "errors.above_zero": "{label} must be a whole number above 0.",
        "errors.no_such_id": "No {label} with that id.",
        "errors.hermes_door": "Hermes door must be On or Off.",
        "errors.setting_value": "Setting {name} needs a value.",
        "errors.care_reminder_months": "Care reminder time must be a whole number of months from 1 to 120.",
        "errors.language": "Language must be Tiếng Việt or English.",
    },
}


def _default_lang():
    return DEFAULT_LANG


_lang_getter = _default_lang


def set_lang_getter(fn):
    """``ui.py`` registers ``fn()``: the language of the current request. ``None`` goes back to
    ``DEFAULT_LANG``."""
    global _lang_getter
    _lang_getter = fn or _default_lang


def _lang(lang):
    if lang is None:
        lang = _lang_getter()
    return lang if lang in LANGS else DEFAULT_LANG


def t(key, lang=None, **params):
    """The text of ``key`` in ``lang`` (``None``: the language of the current request), with
    ``params`` filled in. A missing key gives ``[[key]]``, so it is easy to see on the page."""
    template = TEXT[_lang(lang)].get(key)
    if template is None:
        return f"[[{key}]]"
    return template.format(**params)


def tn(key, n, lang=None, **params):
    """``t(key + "_one")`` when ``n == 1``, else ``t(key + "_many")``; ``{n}`` is ``n``."""
    return t(f"{key}_{'one' if n == 1 else 'many'}", lang, n=n, **params)


class TextError(ValueError):
    """An error the pastor can read: ``TextError("errors.required", label="settings.church_name")``.

    ``str(e)`` is the English text (the agent and the logs read it); pages show ``error_text(e)``.
    """

    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(error_text(self, "en"))


def error_text(exc, lang=None):
    """The text of an error in ``lang``. For a ``TextError`` every param that is a TEXT key (such
    as a field label) is first put in that language too. Any other error: ``str(exc)``."""
    if not isinstance(exc, TextError):
        return str(exc)
    lang = _lang(lang)
    params = {k: t(v, lang) if isinstance(v, str) and v in TEXT[lang] else v for k, v in exc.params.items()}
    return t(exc.key, lang, **params)


# ---------------------------------------------------------------- English left on a page

ALLOW = frozenset({"hermes", "email", "pdf", "ok", "sqlite"})
_WORD = re.compile(r"[^\W\d_]+")
_PARAM = re.compile(r"\{[^{}]*\}")
_MARKER = re.compile(r"\[\[[^\[\]]*\]\]")
_VOID = frozenset({"base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track",
                   "wbr"})  # HTML tags with no end tag


def _ascii_words(values):
    return {w.lower() for v in values for w in _WORD.findall(_PARAM.sub(" ", v)) if w.isascii() and len(w) >= 3}


def english_words():
    """ASCII words (3 or more characters, lower case) of the English text, minus the Vietnamese and ``ALLOW``."""
    return _ascii_words(TEXT["en"].values()) - _ascii_words(TEXT["vi"].values()) - ALLOW


class _Visible(HTMLParser):
    """Collects the visible text: no ``<script>``/``<style>``, no attribute value, nothing inside an
    element with its own ``lang`` (pastor data, the "English" switch button). ``<html lang>`` counts
    as no ``lang``: it is the page language."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.open, self.hidden = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            return
        hide = tag in ("script", "style") or (tag != "html" and any(k == "lang" for k, _v in attrs))
        self.open.append((tag, hide))
        self.hidden += hide

    def handle_endtag(self, tag):
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:  # closes the tags left open inside it too
                self.hidden -= sum(hide for _t, hide in self.open[i:])
                del self.open[i:]
                return

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def english_left(page_html):
    """Problems on a Vietnamese page, sorted: every ``[[key]]`` marker, and every English word in
    the visible text (``<title>`` and body). The phrase "Church Manager" is left out."""
    parser = _Visible()
    parser.feed(page_html)
    parser.close()
    visible = "\n".join(parser.parts).replace("Church Manager", " ")
    english = english_words()
    found = set(_MARKER.findall(page_html))
    found.update(w for w in _WORD.findall(visible) if w.isascii() and w.lower() in english)
    return sorted(found)
