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
        "dashboard.this_week": "Tuần này",
        "dashboard.today": "Hôm nay",
        "dashboard.tomorrow": "Ngày mai",
        "dashboard.nothing_week": "Tuần này không có gì trong Lịch.",
        "dashboard.view_all_calendar": "Xem cả {n} trong Lịch",
        "dashboard.needs_visit": "Cần thăm viếng",
        "dashboard.no_visit_in": "Chưa được thăm viếng trong {months} qua",
        "dashboard.persons_one": "{n} người",
        "dashboard.persons_many": "{n} người",
        "dashboard.never": "chưa bao giờ",
        "dashboard.person": "Người",
        "dashboard.status": "Trạng thái",
        "dashboard.last_visit": "Thăm gần nhất",
        "dashboard.no_needs": "Hiện không ai cần thăm viếng.",
        "dashboard.view_all_care": "Xem cả {n} trong Thăm viếng",
        "dashboard.open_care": "Mở Thăm viếng",
        "dashboard.services": "Giờ thờ phượng",
        "dashboard.head_count": "Số người nhóm",
        "dashboard.services_meta_one": "Số người nhóm của {n} Giờ thờ phượng gần nhất",
        "dashboard.services_meta_many": "Số người nhóm của {n} Giờ thờ phượng gần nhất",
        "dashboard.chart_label": "Số người nhóm của {n} Giờ thờ phượng gần nhất: {counts}",
        "dashboard.no_head_count": "Chưa ghi Số người nhóm nào.",
        "dashboard.said": "Số người nhóm {count} ngày {date}",
        "dashboard.trend_later": "{said}. Xu hướng sẽ hiện sau lần ghi Số người nhóm thứ hai.",
        "dashboard.trend_up": "Tăng",
        "dashboard.trend_down": "Giảm",
        "dashboard.trend_same": "Không đổi",
        "dashboard.trend_line_one": "{said}, so với trung bình {average} của {n} Giờ thờ phượng trước đó.",
        "dashboard.trend_line_many": "{said}, so với trung bình {average} của {n} Giờ thờ phượng trước đó.",
        "dashboard.money_month": "Tài chính tháng này",
        "dashboard.offerings": "Dâng hiến",
        "dashboard.expenses": "Khoản chi",
        "dashboard.balance": "Số dư",
        "dashboard.no_money": "Tháng này chưa ghi Dâng hiến hay Khoản chi nào.",
        "dashboard.record_offering": "Ghi Dâng hiến",
        "dashboard.open_money": "Mở Tài chính",
        "dashboard.sent_documents": "Văn bản đi",
        "dashboard.sent_in_year_one": "{n} Công văn đi trong năm {year}",
        "dashboard.sent_in_year_many": "{n} Công văn đi trong năm {year}",
        "dashboard.next_number": "Số tiếp theo",
        "dashboard.no_sent": "Chưa có Công văn đi nào.",
        "dashboard.open_sent": "Mở Văn bản đi",
        "dashboard.failed": "Không tải được {title}.",
        "dashboard.retry": "Thử lại",
        "dashboard.finding_needs_one": "{n} người cần thăm viếng",
        "dashboard.finding_needs_many": "{n} người cần thăm viếng",
        "dashboard.finding_week_one": "{n} Lịch trong tuần này",
        "dashboard.finding_week_many": "{n} Lịch trong tuần này",
        "dashboard.plan_visit": "Lên lịch Thăm viếng",
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
        "documents.document": "Tài liệu",
        "documents.person": "Người",
        "documents.family": "Gia đình",
        "documents.calendar_item": "Lịch",
        "documents.sent_document": "Công văn đi",
        "documents.file": "Tệp",
        "documents.file_hint": "Tệp bất kỳ, tối đa {mb} MB. Tệp được giữ trong Dữ liệu Hội Thánh này.",
        "documents.bytes_one": "{n} byte",
        "documents.bytes_many": "{n} byte",
        "documents.size_added": "{size} · thêm ngày {date}",
        "documents.count_one": "{n} Tài liệu",
        "documents.count_many": "{n} Tài liệu",
        "documents.panel_empty": "Chưa có Tài liệu nào cho {what} này.",
        "documents.panel_meta": "Các tệp được giữ trong Dữ liệu Hội Thánh này",
        "documents.linked_to": "Liên kết với",
        "documents.size": "Dung lượng",
        "documents.added_col": "Ngày thêm",
        "documents.delete_aria": "Xóa Tài liệu {name}",
        "documents.empty": "Chưa có Tài liệu nào.",
        "documents.list_hint": "Để thêm một Tài liệu, hãy mở Người, Gia đình hoặc Lịch của Tài liệu đó rồi bấm Thêm "
                               "Tài liệu ở đó.",
        "documents.list_sub": "{count} · {size} trong Dữ liệu Hội Thánh này · mới nhất trước",
        "documents.list": "Danh sách Tài liệu",
        "documents.back_to": "Quay lại {link}",
        "documents.for_link": "Cho {what} {name}",
        "documents.added": "Đã thêm Tài liệu: {name}.",
        "documents.go_documents": "Về trang Tài liệu",
        "documents.file_missing": "Không thấy tệp",
        "documents.file_missing_text": "Tệp của {name} không còn trong nơi chứa tài liệu của Dữ liệu Hội Thánh này.",
        "documents.keeps_one": "Công văn đi {numbers} vẫn được giữ, cùng số, ngày, Nơi nhận và Mục đích, nhưng không "
                               "còn tệp.",
        "documents.keeps_many": "Các Công văn đi {numbers} vẫn được giữ, cùng số, ngày, Nơi nhận và Mục đích, nhưng "
                                "không còn tệp.",
        "documents.yes_delete": "Có, xóa Tài liệu này",
        "documents.delete_question": "Xóa Tài liệu {name}?",
        "documents.delete_hint": "Tệp sẽ bị xóa khỏi Dữ liệu Hội Thánh này. Không thể hoàn tác.",
        "documents.delete_title": "Xóa Tài liệu này?",
        "documents.deleted": "Đã xóa Tài liệu: {name}.",
        "documents.file_left": "Không xóa được tệp {file} trong nơi chứa tài liệu. Hãy đóng chương trình đang mở tệp "
                               "đó, rồi xóa tệp đó bằng Trình khám phá tệp.",
        "documents.err_one_link": "Mỗi Tài liệu được thêm cho một Người, một Gia đình hoặc một Lịch.",
        "documents.err_links": "Mỗi Tài liệu chỉ liên kết với một Người, một Gia đình hoặc một Lịch, không hơn.",
        "documents.err_no_row": "Không có {what} với mã số {id}.",
        "documents.err_choose_file": "Hãy chọn một tệp trước.",
        "documents.err_empty_file": "Tệp này trống (0 byte). Hãy chọn tệp khác.",
        "documents.err_no_name": "Tài liệu cần có tên tệp.",
        "documents.err_bytes": "Nội dung tệp phải ở dạng byte.",
        "documents.err_too_large": "Tệp quá lớn. Giới hạn là {mb} MB.",
        "documents.err_bad_name": "Tài liệu {id} có tên lưu không hợp lệ nên không được mở.",
        "documents.err_outside": "Tài liệu {id} trỏ ra ngoài nơi chứa tài liệu nên không được mở.",
        "documents.title": "Tài liệu",
        "documents.add": "Thêm Tài liệu",
        # --- sent
        "sent.date": "Ngày",
        "sent.recipient": "Nơi nhận",
        "sent.purpose": "Mục đích",
        "sent.subject": "Trích yếu",
        "sent.file": "Tệp",
        "sent.number": "Số",
        "sent.this_year": "Năm nay",
        "sent.years": "Các năm",
        "sent.file_link": "Tệp: {link}",
        "sent.next_number": "Số tiếp theo",
        "sent.next_hint": "Số được cấp khi bạn lưu. Mỗi số chỉ dùng một lần.",
        "sent.by_recipient": "Năm {year} theo Nơi nhận",
        "sent.empty": "Chưa có Công văn đi nào trong năm {year}.",
        "sent.list": "Công văn đi năm {year}",
        "sent.count_one": "{n} Công văn đi",
        "sent.count_many": "{n} Công văn đi",
        "sent.sub": "{year} · {count} · mới nhất trước · Số tiếp theo {next}",
        "sent.choose": "— Chọn —",
        "sent.date_hint": "Ngày ghi trên Công văn đi. Năm của ngày này cho ra số.",
        "sent.subject_hint": "Ví dụ: Mời dự Lễ Cung Hiến",
        "sent.file_hint": "Không bắt buộc. Tệp của Công văn đi, tối đa {mb} MB.",
        "sent.number_hint": "Nếu ghi ngày trong năm nay, Công văn đi này nhận số {number}. Các mục Nơi nhận và Mục "
                            "đích được sửa trong {lists}.",
        "sent.save": "Lưu Công văn đi",
        "sent.saved": "Đã lưu với số {number}. Hãy ghi số này lên Công văn đi.",
        "sent.err_after_today": "Ngày không được sau hôm nay ({today}). Hãy dùng hôm nay hoặc một ngày trước đó.",
        "sent.err_hidden": "{label}: {name} đang ẩn trong Danh mục. Hãy chọn mục khác, hoặc hiện lại mục đó trong "
                           "Danh mục.",
        "sent.err_empty_file": "Tệp: tệp này trống (0 byte). Hãy chọn tệp khác, hoặc không chọn tệp nào.",
        "sent.err_too_large": "Tệp: Tệp quá lớn. Giới hạn là {mb} MB.",
        "sent.title": "Văn bản đi",
        "sent.add": "Thêm Công văn đi",
        # --- lists
        "lists.recipient": "Nơi nhận",
        "lists.purpose": "Mục đích",
        "lists.fund": "Quỹ",
        "lists.spending_category": "Hạng mục chi",
        "lists.ministry": "Ban ngành",
        "lists.recipient_line": "Cơ quan bên ngoài nhận Công văn đi",
        "lists.purpose_line": "Lý do gửi Công văn đi",
        "lists.fund_line": "Nơi khoản Dâng hiến được đưa vào",
        "lists.spending_category_line": "Khoản chi dùng vào việc gì",
        "lists.ministry_line": "Nơi một Người phục vụ trong Hội Thánh",
        "lists.status_line": "Mối liên hệ hiện nay của một Người với Hội Thánh",
        "lists.uses_sent_one": "{n} Công văn đi",
        "lists.uses_sent_many": "{n} Công văn đi",
        "lists.uses_offering_one": "{n} khoản Dâng hiến",
        "lists.uses_offering_many": "{n} khoản Dâng hiến",
        "lists.uses_expense_one": "{n} Khoản chi",
        "lists.uses_expense_many": "{n} Khoản chi",
        "lists.uses_serving_one": "{n} người đang phục vụ",
        "lists.uses_serving_many": "{n} người đang phục vụ",
        "lists.uses_now_one": "{n} người hiện nay",
        "lists.uses_now_many": "{n} người hiện nay",
        "lists.hidden_tag": "Đang ẩn",
        "lists.show": "Hiện",
        "lists.hide": "Ẩn",
        "lists.show_aria": "Hiện {name}",
        "lists.hide_aria": "Ẩn {name}",
        "lists.rename": "Đổi tên",
        "lists.new_name": "Tên mới",
        "lists.new_item": "{title} mới",
        "lists.empty": "Chưa có {title} nào.",
        "lists.meta": "{line} · {shown} đang hiện",
        "lists.meta_hidden": "{line} · {shown} đang hiện, {hidden} đang ẩn",
        "lists.sub": "Đổi tên, ẩn hoặc hiện một mục, hoặc thêm mục mới. Không mục nào bị xóa: mục đang ẩn không được "
                     "đưa ra để chọn khi nhập mới, còn những gì đã dùng mục đó vẫn giữ tên của nó.",
        "lists.added": "Đã thêm {name} vào {title}.",
        "lists.rename_same": "{name} vẫn giữ tên cũ. Không có gì thay đổi.",
        "lists.renamed": "{old} nay có tên mới là {new}. Mọi nơi dùng mục này đều hiện tên mới.",
        "lists.hidden_flash": "Đã ẩn {name}. Mục này không được đưa ra để chọn khi nhập mới; những gì đã dùng mục này "
                              "vẫn giữ tên.",
        "lists.shown_flash": "Đã hiện lại {name}.",
        "lists.name": "Tên",
        "lists.list_item": "Mục danh mục",
        "lists.err_keep_one": "Hãy để ít nhất một {title} đang hiện: khi nhập mới cần có một mục để chọn.",
        "lists.err_no_list": "Không có danh mục nào tên là {name}.",
        "lists.err_no_item": "Không có mục danh mục với mã số {id}.",
        "lists.err_unknown": "Không có danh mục {name}. Các danh mục là: {names}.",
        "lists.err_find": "Hãy cho mã hoặc tên để tìm một mục danh mục.",
        "lists.err_choose": "{label}: hãy chọn một mục trong danh sách.",
        "lists.err_code": "Mã chỉ dùng a-z, 0-9 và _.",
        "lists.err_taken": "{name} đã có trong danh mục {list}.",
        "lists.err_cannot_add": "Không thêm được {name} vào danh mục {list}: {detail}.",
        "lists.err_active": "Chỉ có thể hiện hoặc ẩn một mục.",
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
        "search.placeholder": "Có dấu hoặc không dấu",
        "search.hint": "Gõ một phần của tên, có dấu hoặc không dấu.",
        "search.none": "Không tìm thấy Người nào cho “{q}”.",
        "search.first_n": "Đang hiện {n} người đầu tiên. Gõ thêm tên để thu hẹp kết quả.",
        "search.results": "Kết quả",
        "search.found_one": "Tìm thấy {n} người",
        "search.found_many": "Tìm thấy {n} người",
        "search.live_none": "Không tìm thấy Người nào. Bấm Tìm kiếm để xem trang kết quả.",
        "search.live_failed": "Lúc này chưa tìm được. Bấm Tìm kiếm để thử lại.",
        "search.err_limit": "Số kết quả tối đa phải là số nguyên lớn hơn 0.",
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
        "dashboard.this_week": "This week",
        "dashboard.today": "Today",
        "dashboard.tomorrow": "Tomorrow",
        "dashboard.nothing_week": "Nothing this week.",
        "dashboard.view_all_calendar": "View all {n} in Calendar",
        "dashboard.needs_visit": "Needs a visit",
        "dashboard.no_visit_in": "No Visit in the last {months}, or never",
        "dashboard.persons_one": "{n} Person",
        "dashboard.persons_many": "{n} People",
        "dashboard.never": "never",
        "dashboard.person": "Person",
        "dashboard.status": "Status",
        "dashboard.last_visit": "Last Visit",
        "dashboard.no_needs": "No one needs a visit now.",
        "dashboard.view_all_care": "View all {n} in Care",
        "dashboard.open_care": "Open Care",
        "dashboard.services": "Services",
        "dashboard.head_count": "Head count",
        "dashboard.services_meta_one": "Head count of the last {n} Service",
        "dashboard.services_meta_many": "Head count of the last {n} Services",
        "dashboard.chart_label": "Head count of the last {n} Services: {counts}",
        "dashboard.no_head_count": "No Head count recorded yet.",
        "dashboard.said": "Head count {count} on {date}",
        "dashboard.trend_later": "{said}. A trend shows after the second Head count.",
        "dashboard.trend_up": "Up",
        "dashboard.trend_down": "Down",
        "dashboard.trend_same": "Same",
        "dashboard.trend_line_one": "{said}, against an average of {average} for the {n} Service before.",
        "dashboard.trend_line_many": "{said}, against an average of {average} for the {n} Services before.",
        "dashboard.money_month": "Money this month",
        "dashboard.offerings": "Offerings",
        "dashboard.expenses": "Expenses",
        "dashboard.balance": "Balance",
        "dashboard.no_money": "No Offering or Expense recorded this month.",
        "dashboard.record_offering": "Record Offering",
        "dashboard.open_money": "Open Money",
        "dashboard.sent_documents": "Sent documents",
        "dashboard.sent_in_year_one": "{n} Sent document in {year}",
        "dashboard.sent_in_year_many": "{n} Sent documents in {year}",
        "dashboard.next_number": "Next number",
        "dashboard.no_sent": "No Sent document yet.",
        "dashboard.open_sent": "Open Sent documents",
        "dashboard.failed": "Could not load {title}.",
        "dashboard.retry": "Retry",
        "dashboard.finding_needs_one": "{n} Person needs a visit",
        "dashboard.finding_needs_many": "{n} People need a visit",
        "dashboard.finding_week_one": "{n} Calendar item this week",
        "dashboard.finding_week_many": "{n} Calendar items this week",
        "dashboard.plan_visit": "Plan a Visit",
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
        "documents.document": "Document",
        "documents.person": "Person",
        "documents.family": "Family",
        "documents.calendar_item": "Calendar item",
        "documents.sent_document": "Sent document",
        "documents.file": "File",
        "documents.file_hint": "Any file up to {mb} MB. It is kept inside this church copy.",
        "documents.bytes_one": "{n} byte",
        "documents.bytes_many": "{n} bytes",
        "documents.size_added": "{size} · added {date}",
        "documents.count_one": "{n} Document",
        "documents.count_many": "{n} Documents",
        "documents.panel_empty": "No Document for this {what} yet.",
        "documents.panel_meta": "Files kept in this church copy",
        "documents.linked_to": "Linked to",
        "documents.size": "Size",
        "documents.added_col": "Added",
        "documents.delete_aria": "Delete the Document {name}",
        "documents.empty": "No Document yet.",
        "documents.list_hint": "To add a Document, open its Person, Family or Calendar item and press Add document "
                               "there.",
        "documents.list_sub": "{count} · {size} in this church copy · newest first",
        "documents.list": "Documents list",
        "documents.back_to": "Back to {link}",
        "documents.for_link": "For the {what} {name}",
        "documents.added": "Document added: {name}.",
        "documents.go_documents": "Go to Documents",
        "documents.file_missing": "File missing",
        "documents.file_missing_text": "The file of {name} is missing from the documents folder of this church copy.",
        "documents.keeps_one": "The Sent document {numbers} stays, with its number, date, Recipient and Purpose, but "
                               "no file.",
        "documents.keeps_many": "The Sent documents {numbers} stay, with their numbers, dates, Recipients and "
                                "Purposes, but no file.",
        "documents.yes_delete": "Yes, delete it",
        "documents.delete_question": "Delete the Document {name}?",
        "documents.delete_hint": "The file is removed from this church copy. This cannot be undone.",
        "documents.delete_title": "Delete this Document?",
        "documents.deleted": "Document deleted: {name}.",
        "documents.file_left": "Its file {file} could not be removed from the documents folder. Close any program "
                               "that has it open, then remove that file in File Explorer.",
        "documents.err_one_link": "A Document is added to one Person, one Family or one Calendar item.",
        "documents.err_links": "A Document is linked to one Person, one Family or one Calendar item, not more.",
        "documents.err_no_row": "No {what} with id {id}.",
        "documents.err_choose_file": "Choose a file first.",
        "documents.err_empty_file": "The file is empty (0 bytes). Choose another file.",
        "documents.err_no_name": "A Document needs a file name.",
        "documents.err_bytes": "The file content must be bytes.",
        "documents.err_too_large": "The file is too large. The limit is {mb} MB.",
        "documents.err_bad_name": "Document {id} has a bad stored name and is not opened.",
        "documents.err_outside": "Document {id} points outside the documents folder and is not opened.",
        "documents.title": "Documents",
        "documents.add": "Add document",
        # --- sent
        "sent.date": "Date",
        "sent.recipient": "Recipient",
        "sent.purpose": "Purpose",
        "sent.subject": "Subject",
        "sent.file": "File",
        "sent.number": "Number",
        "sent.this_year": "This year",
        "sent.years": "Years",
        "sent.file_link": "File: {link}",
        "sent.next_number": "Next number",
        "sent.next_hint": "Given when you save. A number is never used twice.",
        "sent.by_recipient": "{year} by Recipient",
        "sent.empty": "No Sent document in {year} yet.",
        "sent.list": "Sent documents of {year}",
        "sent.count_one": "{n} Sent document",
        "sent.count_many": "{n} Sent documents",
        "sent.sub": "{year} · {count} · newest first · Next number {next}",
        "sent.choose": "— Choose —",
        "sent.date_hint": "The date written on the Sent document. Its year gives the number.",
        "sent.subject_hint": "For example: Mời dự Lễ Cung Hiến",
        "sent.file_hint": "Optional. A copy of the Sent document, up to {mb} MB.",
        "sent.number_hint": "Dated this year, it gets number {number}. Recipient and Purpose choices are edited in "
                            "{lists}.",
        "sent.save": "Save Sent document",
        "sent.saved": "Saved as {number}. Write this number on the Sent document.",
        "sent.err_after_today": "Date cannot be after today ({today}). Use today or an earlier date.",
        "sent.err_hidden": "{label}: {name} is hidden in Lists. Choose another one, or show it again in Lists.",
        "sent.err_empty_file": "File: the file is empty (0 bytes). Choose another file, or none.",
        "sent.err_too_large": "File: The file is too large. The limit is {mb} MB.",
        "sent.title": "Sent documents",
        "sent.add": "Record a Sent document",
        # --- lists
        "lists.recipient": "Recipient",
        "lists.purpose": "Purpose",
        "lists.fund": "Fund",
        "lists.spending_category": "Spending category",
        "lists.ministry": "Ministry",
        "lists.recipient_line": "The outside body a Sent document goes to",
        "lists.purpose_line": "Why a Sent document is sent",
        "lists.fund_line": "Where an Offering goes",
        "lists.spending_category_line": "What an Expense is for",
        "lists.ministry_line": "Where a Person serves in the church",
        "lists.status_line": "Where a Person stands with the church now",
        "lists.uses_sent_one": "{n} Sent document",
        "lists.uses_sent_many": "{n} Sent documents",
        "lists.uses_offering_one": "{n} Offering",
        "lists.uses_offering_many": "{n} Offerings",
        "lists.uses_expense_one": "{n} Expense",
        "lists.uses_expense_many": "{n} Expenses",
        "lists.uses_serving_one": "{n} Person serving now",
        "lists.uses_serving_many": "{n} People serving now",
        "lists.uses_now_one": "{n} Person now",
        "lists.uses_now_many": "{n} People now",
        "lists.hidden_tag": "Hidden",
        "lists.show": "Show",
        "lists.hide": "Hide",
        "lists.show_aria": "Show {name}",
        "lists.hide_aria": "Hide {name}",
        "lists.rename": "Rename",
        "lists.new_name": "New name",
        "lists.new_item": "New {title}",
        "lists.empty": "No {title} yet.",
        "lists.meta": "{line} · {shown} shown",
        "lists.meta_hidden": "{line} · {shown} shown, {hidden} hidden",
        "lists.sub": "Rename, hide or show an item, or add a new one. Nothing is ever deleted: a hidden item is not "
                     "offered for new entries, and what already uses it keeps its name.",
        "lists.added": "{name} added to {title}.",
        "lists.rename_same": "{name} kept its name. Nothing changed.",
        "lists.renamed": "{old} is now called {new}. Everything that uses it shows the new name.",
        "lists.hidden_flash": "{name} is hidden. It is not offered for new entries; what already uses it keeps its "
                              "name.",
        "lists.shown_flash": "{name} is shown again.",
        "lists.name": "Name",
        "lists.list_item": "List item",
        "lists.err_keep_one": "Keep at least one {title} shown: new entries need one to choose.",
        "lists.err_no_list": "There is no list called {name}.",
        "lists.err_no_item": "No list item with id {id}.",
        "lists.err_unknown": "Unknown list {name}. Lists are: {names}.",
        "lists.err_find": "Give a code or a name to find a list item.",
        "lists.err_choose": "{label}: choose one from the list.",
        "lists.err_code": "A code uses only a-z, 0-9 and _.",
        "lists.err_taken": "{name} is already in the {list} list.",
        "lists.err_cannot_add": "{name} cannot be added to the {list} list: {detail}.",
        "lists.err_active": "active must be True or False.",
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
        "search.placeholder": "With or without accents",
        "search.hint": "Type part of a name, with or without accents.",
        "search.none": "No Person found for “{q}”.",
        "search.first_n": "Showing the first {n}. Type more of the name to narrow it.",
        "search.results": "Results",
        "search.found_one": "{n} Person found",
        "search.found_many": "{n} People found",
        "search.live_none": "No Person found. Press Search to see the page.",
        "search.live_failed": "Could not search right now. Press Search to try again.",
        "search.err_limit": "limit must be a whole number above 0.",
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
