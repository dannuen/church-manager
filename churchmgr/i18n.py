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
        "copies.this_copy": "Dữ liệu Hội Thánh này",
        "copies.church": "Hội Thánh",
        "copies.saved_in_row": "Lưu tại",
        "copies.copies_folder": "Nơi chứa dữ liệu",
        "copies.inside_row": "Bên trong",
        "copies.inside": "{db} ({people}) và nơi lưu tài liệu ({documents}, {size})",
        "copies.documents_one": "{n} Tài liệu",
        "copies.documents_many": "{n} Tài liệu",
        "copies.bytes_one": "{n} byte",
        "copies.bytes_many": "{n} byte",
        "copies.opens_at_start": "Mở khi khởi động",
        "copies.start_this": "Dữ liệu Hội Thánh này (ghi trong {file})",
        "copies.start_other": "{path} (ghi trong {file})",
        "copies.set_folder": "Church Manager được mở với một nơi lưu cố định ({flag}), nên khi mở một Dữ liệu Hội Thánh "
                             "khác, {file} không thay đổi.",
        "copies.keep_outside": "Dữ liệu Hội Thánh được giữ ngoài OneDrive. Muốn cất thêm một bản, hãy chép nguyên nơi "
                               "lưu ở trên sang chỗ khác.",
        "copies.list_title": "Các Dữ liệu Hội Thánh",
        "copies.list_meta": "Các nơi lưu có tệp {db} trong nơi chứa dữ liệu",
        "copies.folder": "Nơi lưu",
        "copies.people": "Số người",
        "copies.cannot_read": "Không đọc được",
        "copies.open_now": "Đang mở",
        "copies.in_onedrive": "Nằm trong OneDrive: không mở",
        "copies.open_label": "Mở {name}",
        "copies.no_copies": "Không có Dữ liệu Hội Thánh nào trong nơi chứa dữ liệu.",
        "copies.sub": "{church} đang mở · {copies} trong nơi chứa dữ liệu",
        "copies.copies_one": "{n} Dữ liệu Hội Thánh",
        "copies.copies_many": "{n} Dữ liệu Hội Thánh",
        "copies.handover_intro": "Bàn giao là một tệp ZIP cho mục sư kế nhiệm của Hội Thánh này: gồm cơ sở dữ liệu và "
                                 "mọi Tài liệu. Các Ghi chú cá nhân được bỏ ra khỏi tệp này. Dữ liệu Hội Thánh này "
                                 "không bị thay đổi.",
        "copies.make": "Tạo Bàn giao",
        "copies.saved_in": "Lưu trong {path}",
        "copies.made_list": "Các Bàn giao đã tạo",
        "copies.made": "Đã tạo Bàn giao.",
        "copies.notes_removed": "Các Ghi chú cá nhân đã được bỏ ra.",
        "copies.saved_as": "Đã lưu thành {path} ({size})",
        "copies.download": "Tải về tệp ZIP Bàn giao",
        "copies.not_made": "Chưa tạo Bàn giao.",
        "copies.nothing_changed": "Không có gì bị thay đổi. Hãy sửa lỗi này, rồi bấm Tạo Bàn giao lần nữa.",
        "copies.found_elsewhere": "Chữ của một Ghi chú cá nhân cũng được ghi ở chỗ khác trong Dữ liệu Hội Thánh này, "
                                  "nên sẽ đến tay mục sư kế nhiệm.",
        "copies.fix_places": "Để sửa, hãy bỏ những chữ riêng tư đó khỏi từng chỗ ở trên. Với một Tài liệu, hãy bấm "
                             "Xóa: sửa Ghi chú cá nhân không làm thay đổi tệp Tài liệu, và tệp đó vẫn đến tay mục sư "
                             "kế nhiệm. Với chữ ở chỗ khác, hãy mở ra và sửa lại. Sau đó bấm Tạo Bàn giao lần nữa. "
                             "Không có gì bị thay đổi và không có tệp ZIP nào được lưu.",
        "copies.place_line": "Ghi chú cá nhân của {owner} cũng có ở {where}",
        "copies.place_field_of": "{field} của {word} {link}.",
        "copies.place_field_in": "{field} trong {link}.",
        "copies.place_file": "tệp {path}",
        "copies.place_a_file": "một tệp",
        "copies.place_stray": "{file} trong nơi lưu tài liệu. Không có Tài liệu nào trong ứng dụng giữ tệp này: hãy mở "
                              "{folder} trên máy tính rồi xóa tệp đó.",
        "copies.place_doc": "Tài liệu {name}",
        "copies.place_doc_of": "Tài liệu {name} của {link}",
        "copies.delete_doc": "Xóa Tài liệu {name}",
        "copies.more_places": "Và {n} chỗ khác nữa.",
        "copies.word_person": "Người",
        "copies.word_family": "Gia đình",
        "copies.word_chi_phai": "Chi phái",
        "copies.word_calendar_item": "Lịch",
        "copies.word_head_count": "Số người nhóm",
        "copies.word_offering": "Dâng hiến",
        "copies.word_expense": "Khoản chi",
        "copies.word_document": "Tài liệu",
        "copies.word_sent_document": "Công văn đi",
        "copies.word_other": "bảng {table}",
        "copies.field_name": "tên",
        "copies.field_file_name": "tên tệp",
        "copies.field_care_note": "ghi chú thăm viếng",
        "copies.field_absent_note": "ghi chú người vắng",
        "copies.field_note": "ghi chú",
        "copies.field_address": "địa chỉ",
        "copies.field_phone": "số điện thoại",
        "copies.field_title": "tiêu đề",
        "copies.field_place": "địa điểm",
        "copies.field_subject": "trích yếu",
        "copies.field_value": "giá trị",
        "copies.field_other": "ô {col}",
        "copies.setup_intro": "Lập một Dữ liệu Hội Thánh trống, chỉ có các danh sách có sẵn, ở một nơi lưu mới trong "
                              "nơi chứa dữ liệu. Sau đó Church Manager mở dữ liệu mới này. Dữ liệu Hội Thánh này vẫn "
                              "được giữ; có thể mở lại trong Các Dữ liệu Hội Thánh.",
        "copies.setup_start": "Lập dữ liệu Hội Thánh mới",
        "copies.setup_done": "Đã lập dữ liệu Hội Thánh mới: {church}. Đây là Trang chủ của dữ liệu đó. Các Dữ liệu Hội "
                             "Thánh khác vẫn được giữ trong Dữ liệu.",
        "copies.already_open": "Dữ liệu Hội Thánh này đang mở.",
        "copies.opened": "Đã mở {name}.",
        "copies.zip_not_found": "Không tìm thấy Bàn giao",
        "copies.no_zip": "Không có tệp ZIP Bàn giao nào có tên này.",
        "copies.go_copies": "Về Dữ liệu",
        "copies.date": "Ngày",
        "copies.err_no_such_copy": "Không có Dữ liệu Hội Thánh nào có nơi lưu tên này trong nơi chứa dữ liệu.",
        "copies.err_copy_in_onedrive": "Dữ liệu Hội Thánh này nằm trong OneDrive nên không được mở. Hãy chuyển nó ra "
                                       "ngoài OneDrive trước.",
        "copies.err_folder_required": "Cần chọn nơi lưu cho Dữ liệu Hội Thánh.",
        "copies.err_onedrive": "Dữ liệu Hội Thánh không được nằm trong OneDrive: {path}. Hãy chọn một nơi lưu ngoài "
                               "OneDrive, ví dụ trong {example}.",
        "copies.err_db_version": "{path} không phải là cơ sở dữ liệu Church Manager (bản {version}).",
        "copies.err_no_copy": "Không có Dữ liệu Hội Thánh trong {folder}: thiếu {db}.",
        "copies.err_out_in_documents": "Hãy lưu Bàn giao ở ngoài nơi lưu tài liệu của Dữ liệu Hội Thánh.",
        "copies.err_notes_left": "Vẫn còn {n} Ghi chú cá nhân trong cơ sở dữ liệu Bàn giao. Chưa tạo Bàn giao.",
        "copies.err_db_check": "Cơ sở dữ liệu Bàn giao không qua được bước kiểm tra ({detail}). Chưa tạo Bàn giao.",
        "copies.err_text_in_db": "Vẫn thấy chữ của Ghi chú cá nhân số {note_id} trong cơ sở dữ liệu Bàn giao (có thể "
                                 "cùng chữ đó cũng được dùng ở chỗ khác). Chưa tạo Bàn giao.",
        "copies.err_door": "Cổng Hermes chưa tắt trong cơ sở dữ liệu Bàn giao. Chưa tạo Bàn giao.",
        "copies.err_text_in_document": "Chữ của một Ghi chú cá nhân cũng được ghi trong một tệp Tài liệu, nên sẽ đến "
                                       "tay mục sư kế nhiệm. Chưa tạo Bàn giao.",
        "copies.err_zip_damaged": "Tệp ZIP Bàn giao bị hỏng ({detail}). Chưa tạo Bàn giao.",
        "copies.err_zip_no_db": "Tệp ZIP Bàn giao không có {db}. Chưa tạo Bàn giao.",
        "copies.err_zip_missing_file": "Thiếu một tệp Tài liệu trong tệp ZIP Bàn giao. Chưa tạo Bàn giao.",
        "copies.err_failed": "Không tạo được Bàn giao: {detail}",
        "copies.err_plain": "{message}",
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
        "copies.this_copy": "This church copy",
        "copies.church": "Church",
        "copies.saved_in_row": "Saved in",
        "copies.copies_folder": "Copies folder",
        "copies.inside_row": "Inside",
        "copies.inside": "{db} ({people}) and the documents folder ({documents}, {size})",
        "copies.documents_one": "{n} Document",
        "copies.documents_many": "{n} Documents",
        "copies.bytes_one": "{n} byte",
        "copies.bytes_many": "{n} bytes",
        "copies.opens_at_start": "Opens at start",
        "copies.start_this": "This church copy (named in {file})",
        "copies.start_other": "{path} (named in {file})",
        "copies.set_folder": "Church Manager was started with a set folder ({flag}), so opening another copy does not "
                             "change {file}.",
        "copies.keep_outside": "A church copy is kept outside OneDrive. Copy the whole folder to keep a spare.",
        "copies.list_title": "Church copies",
        "copies.list_meta": "Folders of the copies folder that hold a {db}",
        "copies.folder": "Folder",
        "copies.people": "People",
        "copies.cannot_read": "Cannot be read",
        "copies.open_now": "Open now",
        "copies.in_onedrive": "Inside OneDrive: not opened",
        "copies.open_label": "Open {name}",
        "copies.no_copies": "No church copy in the copies folder.",
        "copies.sub": "{church} is open · {copies} in the copies folder",
        "copies.copies_one": "{n} church copy",
        "copies.copies_many": "{n} church copies",
        "copies.handover_intro": "A Handover is one zip file for the next pastor of this church: the database and "
                                 "every Document. Private notes are removed from it. This church copy is not changed.",
        "copies.make": "Make Handover",
        "copies.saved_in": "Saved in {path}",
        "copies.made_list": "Handovers made",
        "copies.made": "Handover made.",
        "copies.notes_removed": "Private notes were removed.",
        "copies.saved_as": "Saved as {path} ({size})",
        "copies.download": "Download the Handover zip",
        "copies.not_made": "Handover not made.",
        "copies.nothing_changed": "Nothing was changed. Fix this, then press Make Handover again.",
        "copies.found_elsewhere": "The words of a Private note are also written somewhere else in this church copy, "
                                  "so they would go to the next pastor.",
        "copies.fix_places": "To fix it, take the private words out of each place above. For a Document, press "
                             "Delete: changing the Private note does not change a Document file, and the file still "
                             "goes to the next pastor. For other text, open it and change it. Then press Make "
                             "Handover again. Nothing was changed and no zip was saved.",
        "copies.place_line": "The Private note of {owner} is also written in {where}",
        "copies.place_field_of": "the {field} of the {word} {link}.",
        "copies.place_field_in": "a {field} in {link}.",
        "copies.place_file": "the file {path}",
        "copies.place_a_file": "a file",
        "copies.place_stray": "{file} of the documents folder. No Document in the app has this file: remove it from "
                              "the folder {folder} in File Explorer.",
        "copies.place_doc": "the Document {name}",
        "copies.place_doc_of": "the Document {name} of {link}",
        "copies.delete_doc": "Delete the Document {name}",
        "copies.more_places": "And {n} more places.",
        "copies.word_person": "Person",
        "copies.word_family": "Family",
        "copies.word_chi_phai": "Chi phái",
        "copies.word_calendar_item": "Calendar item",
        "copies.word_head_count": "Head count",
        "copies.word_offering": "Offering",
        "copies.word_expense": "Expense",
        "copies.word_document": "Document",
        "copies.word_sent_document": "Sent document",
        "copies.word_other": "{table}",
        "copies.field_name": "name",
        "copies.field_file_name": "file name",
        "copies.field_care_note": "Care note",
        "copies.field_absent_note": "absent note",
        "copies.field_note": "note",
        "copies.field_address": "address",
        "copies.field_phone": "phone",
        "copies.field_title": "title",
        "copies.field_place": "place",
        "copies.field_subject": "subject",
        "copies.field_value": "value",
        "copies.field_other": "{col}",
        "copies.setup_intro": "Starts a blank church copy that keeps only the default lists, in a new folder of the "
                              "copies folder. Church Manager then opens it. This church copy is kept; open it again "
                              "from Church copies.",
        "copies.setup_start": "Start New church setup",
        "copies.setup_done": "New church setup is done: {church}. This is its Dashboard. The other church copies are "
                             "kept in Copies.",
        "copies.already_open": "This church copy is already open.",
        "copies.opened": "Opened {name}.",
        "copies.zip_not_found": "Handover not found",
        "copies.no_zip": "There is no Handover zip with this name.",
        "copies.go_copies": "Go to Copies",
        "copies.date": "Date",
        "copies.err_no_such_copy": "There is no church copy with this folder name in the copies folder.",
        "copies.err_copy_in_onedrive": "This church copy is inside OneDrive, so it is not opened. Move it outside "
                                       "OneDrive first.",
        "copies.err_folder_required": "A folder is required for the church copy.",
        "copies.err_onedrive": "The church copy must not be inside OneDrive: {path}. Choose a folder outside OneDrive, "
                               "for example under {example}.",
        "copies.err_db_version": "{path} is not a Church Manager database of version {version}.",
        "copies.err_no_copy": "No church copy in {folder}: {db} is missing.",
        "copies.err_out_in_documents": "Save the handover outside the documents folder of the church copy.",
        "copies.err_notes_left": "{n} Private note(s) were still in the handover database. No handover was made.",
        "copies.err_db_check": "The handover database failed its check ({detail}). No handover was made.",
        "copies.err_text_in_db": "The text of Private note {note_id} was still found in the handover database (maybe "
                                 "the same text is also used somewhere else). No handover was made.",
        "copies.err_door": "The Hermes door was not off in the handover database. No handover was made.",
        "copies.err_text_in_document": "The text of a Private note is also written in a Document file, so it would go "
                                       "to the next pastor. No handover was made.",
        "copies.err_zip_damaged": "The handover zip is damaged ({detail}). No handover was made.",
        "copies.err_zip_no_db": "The handover zip has no {db}. No handover was made.",
        "copies.err_zip_missing_file": "A Document file is missing from the handover zip. No handover was made.",
        "copies.err_failed": "The handover could not be made: {detail}",
        "copies.err_plain": "{message}",
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
