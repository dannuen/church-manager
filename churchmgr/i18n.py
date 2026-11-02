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
        "people.person": "Người",
        "people.status": "Trạng thái",
        "people.family": "Gia đình",
        "people.chi_phai": "Chi phái",
        "people.ministry": "Ban ngành",
        "people.ministries": "Ban ngành",
        "people.family_role": "Vai trò trong gia đình",
        "people.ministry_role": "Vai trò trong ban",
        "people.private_note": "Ghi chú cá nhân",
        "people.full_name": "Họ và tên",
        "people.gender": "Giới tính",
        "people.male": "Nam",
        "people.female": "Nữ",
        "people.birth_date": "Ngày sinh",
        "people.phone": "Điện thoại",
        "people.address": "Địa chỉ",
        "people.own_address": "Địa chỉ riêng",
        "people.note": "Ghi chú",
        "people.date": "Ngày",
        "people.start_date": "Ngày bắt đầu",
        "people.from": "Từ",
        "people.to": "Đến",
        "people.since": "Từ ngày",
        "people.now": "hiện nay",
        "people.count_now": "{count} hiện nay",
        "people.not_found_title": "Không tìm thấy {what}",
        "people.not_found_text": "Không có {what} với mã số này.",
        "people.nothing_changed": "{message} Không có gì thay đổi.",
        "people.err_after_today": "{label} không được sau hôm nay ({today}). Hãy dùng hôm nay hoặc một ngày trước đó.",
        "people.err_list_choice": "{label}: hãy chọn một mục trong danh sách.",
        "people.err_no_row": "Không có {what} với mã số {id}.",
        "people.err_history": "Ngày bắt đầu {start} sớm hơn {latest}, ngày của lần thay đổi gần nhất. Những gì đã qua "
                              "không bao giờ bị viết lại; hãy dùng ngày {latest} hoặc sau đó.",
        "people.err_gender": "Giới tính phải là M (Nam) hoặc F (Nữ), hoặc để trống.",
        "people.err_family_role": "Vai trò trong gia đình phải là một trong: Chủ gia đình, Vợ/Chồng, Con, Người thân "
                                  "khác.",
        "people.err_ministry_role": "Vai trò trong ban phải là một trong: Trưởng ban, Ban viên.",
        "people.err_note_empty": "Ghi chú cá nhân cần có nội dung.",
        "people.err_no_note": "Người này không có Ghi chú cá nhân với mã số {id}.",
        "people.all": "Tất cả",
        "people.no_status": "Chưa có Trạng thái",
        "people.filter_status": "Lọc theo Trạng thái",
        "people.find_in_list": "Tìm trong danh sách này",
        "people.search_hint": "Có dấu hoặc không dấu",
        "people.clear": "Bỏ tìm",
        "people.list": "Danh sách Mọi người",
        "people.count_of": "{n} trong số {total}",
        "people.empty": "Chưa có Người nào. Hãy thêm Người đầu tiên.",
        "people.empty_q": "Không có Người nào khớp với “{q}” ở đây.",
        "people.empty_status": "Hiện không có Người nào có Trạng thái này.",
        "people.first_status": "Trạng thái ban đầu",
        "people.birth_hint": "Để trống nếu không biết.",
        "people.address_hint": "Dùng khi Người này không ở trong Gia đình nào.",
        "people.note_hint": "Ghi chú thông thường. Ghi chú cá nhân được thêm trên trang của Người.",
        "people.start_hint": "Ngày bắt đầu Trạng thái này. Không sau hôm nay.",
        "people.add_button": "Thêm Người",
        "people.added": "Đã thêm Người.",
        "people.edit_title": "Chỉnh sửa {name}",
        "people.edit_hint": "Trạng thái, Gia đình và Ban ngành giữ lại những gì đã qua: hãy đổi chúng trên {link}.",
        "people.person_page": "trang của Người",
        "people.details_saved": "Đã lưu thông tin.",
        "people.go_people": "Về trang Mọi người",
        "people.go_person": "Quay lại trang của Người",
        "people.new_status": "Trạng thái mới",
        "people.change_status": "Đổi Trạng thái",
        "people.no_status_yet": "Chưa có Trạng thái.",
        "people.leave_family": "— Rời Gia đình —",
        "people.no_family_option": "— Không ở trong Gia đình nào —",
        "people.move_hint": "Ngày chuyển. Liên kết Gia đình cũ vẫn được giữ.",
        "people.save_family": "Lưu Gia đình",
        "people.not_in_family": "Không ở trong Gia đình nào. Dùng địa chỉ riêng của Người này.",
        "people.set_family": "Vào hoặc rời Gia đình",
        "people.stop_serving": "Thôi phục vụ trong Ban ngành này",
        "people.save_ministry": "Lưu Ban ngành",
        "people.not_serving": "Không phục vụ trong Ban ngành nào.",
        "people.not_serving_now": "Hiện không phục vụ",
        "people.change_ministry": "Thêm, đổi hoặc kết thúc Ban ngành",
        "people.story": "Quá trình",
        "people.what_happened": "Sự việc",
        "people.no_story": "Chưa có sự việc nào.",
        "people.story_lines_one": "{n} dòng, mới nhất trước",
        "people.story_lines_many": "{n} dòng, mới nhất trước",
        "people.details": "Thông tin",
        "people.family_address": "(địa chỉ Gia đình)",
        "people.edit_details": "Chỉnh sửa thông tin",
        "people.private_label": "Ghi chú cá nhân — chỉ mình bạn thấy",
        "people.private_meta": "Không bao giờ được in. Bị xóa khi Bàn giao.",
        "people.change_note": "Sửa Ghi chú cá nhân này",
        "people.save_note": "Lưu Ghi chú cá nhân",
        "people.edit_note_aria": "Chỉnh sửa Ghi chú cá nhân lúc {when}",
        "people.no_note": "Chưa có Ghi chú cá nhân.",
        "people.new_note": "Ghi chú cá nhân mới",
        "people.add_note": "Thêm Ghi chú cá nhân",
        "people.note_added": "Đã thêm Ghi chú cá nhân.",
        "people.note_changed": "Đã sửa Ghi chú cá nhân.",
        "people.no_visit_done": "Chưa có lần Thăm viếng nào.",
        "people.plan_visit": "Lên kế hoạch Thăm viếng",
        "people.care_meta": "Các lần Thăm viếng đã xong, mới nhất trước",
        "people.status_since": "{status} từ {date}",
        "people.last_visit": "Thăm viếng gần nhất {date}",
        "people.no_visit": "Chưa có Thăm viếng",
        "people.status_same": "Trạng thái đã là {name}.",
        "people.status_changed": "Đã đổi Trạng thái thành {name} từ {date}.",
        "people.family_none": "Người này không ở trong Gia đình nào.",
        "people.family_left": "Đã rời {name} ngày {date}. Liên kết Gia đình cũ vẫn được giữ.",
        "people.family_same": "Đã ở trong {name} với vai trò {role}.",
        "people.family_now": "Nay ở trong {name} với vai trò {role} từ {date}.",
        "people.ministry_none": "Người này không phục vụ trong {name}.",
        "people.ministry_stopped": "Đã thôi phục vụ trong {name} ngày {date}.",
        "people.ministry_same": "Đã là {role} trong {name}.",
        "people.ministry_now": "{role} trong {name} từ {date}.",
        "people.story_status": "Trạng thái: {name}",
        "people.story_family": "Gia đình: {name} ({role})",
        "people.story_family_end": "Rời Gia đình: {name}",
        "people.story_chi_phai": "Chi phái: {name} (của {family})",
        "people.story_truong": "Trưởng Chi phái của {name}",
        "people.story_truong_end": "Thôi làm Trưởng Chi phái của {name}",
        "people.story_ministry": "Ban ngành: {name} ({role})",
        "people.story_ministry_end": "Thôi phục vụ trong Ban ngành: {name}",
        "people.story_serves": "Phục vụ tại {kind}: {title}",
        "people.story_joins": "Tham dự {kind}: {title}",
        "people.story_visit_done": "Thăm viếng đã xong: {who}",
        "people.story_visit_planned": "Thăm viếng dự kiến: {who}",
        "people.story_offering": "Dâng hiến {amount} vào {fund}",
        "people.story_document": "Tài liệu: {name}",
        "people.story_private_note": "Ghi chú cá nhân: {body}",
        "people.title": "Mọi người",
        "people.add": "Thêm Người",
        "people.count_one": "{n} người",
        "people.count_many": "{n} người",
        # --- families
        "families.name": "Tên Gia đình",
        "families.count_one": "{n} Gia đình",
        "families.count_many": "{n} Gia đình",
        "families.in_family_now": "{people} đang ở trong một Gia đình",
        "families.list": "Danh sách Gia đình",
        "families.col_people_now": "Số người hiện nay",
        "families.empty": "Chưa có Gia đình nào. Hãy thêm Gia đình đầu tiên.",
        "families.name_hint": "Ví dụ: Gia đình Nguyễn Hải Đăng",
        "families.address_hint": "Mỗi Người trong Gia đình này đều dùng địa chỉ này.",
        "families.add_button": "Thêm Gia đình",
        "families.new_hint": "Sau đó đưa từng người vào Gia đình trên trang của mỗi Người (Gia đình, Vai trò trong "
                             "gia đình và ngày).",
        "families.added": "Đã thêm Gia đình.",
        "families.people_now": "Người hiện nay",
        "families.people_before": "Người trước đây",
        "families.people_before_meta": "Các liên kết Gia đình cũ, giữ cùng ngày tháng",
        "families.no_one_now": "Hiện không có ai trong Gia đình này.",
        "families.no_one_left": "Chưa có ai rời Gia đình này.",
        "families.move_hint": "Để thêm hoặc chuyển một Người, hãy mở trang của Người đó.",
        "families.leave_chi_phai": "— Rời Chi phái —",
        "families.no_chi_phai_option": "— Không có Chi phái —",
        "families.chi_phai_hint": "Liên kết Chi phái cũ được giữ cùng ngày tháng.",
        "families.change_chi_phai": "Đổi Chi phái",
        "families.not_in_chi_phai": "Gia đình này không ở trong Chi phái nào.",
        "families.chi_phai_since": "{name} từ {date}",
        "families.no_chi_phai": "Chưa có Chi phái",
        "families.address_meta": "Mỗi Người trong Gia đình này đều dùng địa chỉ này",
        "families.edit": "Chỉnh sửa Gia đình",
        "families.go": "Về trang Gia đình",
        "families.edit_hint": "Ai ở trong Gia đình này thì đổi trên trang của mỗi Người, còn Chi phái của Gia đình "
                              "thì đổi trên {link}. Cả hai đều giữ lại những gì đã qua.",
        "families.family_page": "trang Gia đình",
        "families.back": "Quay lại Gia đình",
        "families.saved": "Đã lưu Tên Gia đình và Địa chỉ.",
        "families.chi_phai_left": "Đã rời {name} ngày {date}. Liên kết cũ vẫn được giữ.",
        "families.chi_phai_same": "Đã ở trong {name}.",
        "families.chi_phai_now": "Nay ở trong {name} từ {date}.",
        "families.title": "Gia đình",
        "families.add": "Thêm Gia đình",
        # --- chi_phai
        "chi_phai.name": "Tên Chi phái",
        "chi_phai.count_one": "{n} Chi phái",
        "chi_phai.count_many": "{n} Chi phái",
        "chi_phai.list": "Danh sách Chi phái",
        "chi_phai.truong": "Trưởng Chi phái",
        "chi_phai.col_families_now": "Số Gia đình hiện nay",
        "chi_phai.empty": "Chưa có Chi phái nào. Hãy thêm Chi phái đầu tiên.",
        "chi_phai.name_hint": "Ví dụ: Chi phái Hòa Bình",
        "chi_phai.add_button": "Thêm Chi phái",
        "chi_phai.new_hint": "Sau đó đưa các Gia đình vào trên trang của mỗi Gia đình.",
        "chi_phai.added": "Đã thêm Chi phái.",
        "chi_phai.err_exists": "Đã có Chi phái \"{name}\".",
        "chi_phai.families_now": "Gia đình hiện nay",
        "chi_phai.families_before": "Gia đình trước đây",
        "chi_phai.families_before_meta": "Các liên kết Chi phái cũ, giữ cùng ngày tháng",
        "chi_phai.no_family_now": "Hiện không có Gia đình nào trong Chi phái này.",
        "chi_phai.no_family_left": "Chưa có Gia đình nào rời Chi phái này.",
        "chi_phai.move_hint": "Để thêm hoặc chuyển một Gia đình, hãy mở trang của Gia đình đó.",
        "chi_phai.no_truong_option": "— Không có Trưởng Chi phái —",
        "chi_phai.inside": "Trong Chi phái này",
        "chi_phai.others": "Những người khác",
        "chi_phai.truong_hint": "Trưởng Chi phái trước được giữ cùng ngày tháng.",
        "chi_phai.set_truong": "Chọn Trưởng Chi phái",
        "chi_phai.no_truong_yet": "Chưa có Trưởng Chi phái.",
        "chi_phai.truong_since": "Trưởng Chi phái {name} từ {date}",
        "chi_phai.no_truong": "Chưa có Trưởng Chi phái",
        "chi_phai.rename": "Đổi tên Chi phái",
        "chi_phai.go": "Về trang Chi phái",
        "chi_phai.rename_title": "Đổi tên {name}",
        "chi_phai.rename_hint": "Các Gia đình và Trưởng Chi phái của Chi phái này vẫn giữ nguyên, cùng ngày tháng. "
                                "Tên mới hiện ngay trên mọi trang.",
        "chi_phai.back": "Quay lại Chi phái",
        "chi_phai.renamed": "Đã đổi tên thành {name}.",
        "chi_phai.name_same": "Tên đã là {name}.",
        "chi_phai.truong_none": "Chi phái này không có Trưởng Chi phái.",
        "chi_phai.truong_ended": "{name} thôi làm Trưởng Chi phái từ {date}.",
        "chi_phai.truong_same": "{name} đã là Trưởng Chi phái.",
        "chi_phai.truong_now": "{name} làm Trưởng Chi phái từ {date}.",
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
        "people.person": "Person",
        "people.status": "Status",
        "people.family": "Family",
        "people.chi_phai": "Chi phái",
        "people.ministry": "Ministry",
        "people.ministries": "Ministries",
        "people.family_role": "Family role",
        "people.ministry_role": "Ministry role",
        "people.private_note": "Private note",
        "people.full_name": "Full name",
        "people.gender": "Gender",
        "people.male": "Male",
        "people.female": "Female",
        "people.birth_date": "Birth date",
        "people.phone": "Phone",
        "people.address": "Address",
        "people.own_address": "Own address",
        "people.note": "Note",
        "people.date": "Date",
        "people.start_date": "Start date",
        "people.from": "From",
        "people.to": "To",
        "people.since": "Since",
        "people.now": "now",
        "people.count_now": "{count} now",
        "people.not_found_title": "{what} not found",
        "people.not_found_text": "There is no {what} with this number.",
        "people.nothing_changed": "{message} Nothing changed.",
        "people.err_after_today": "{label} cannot be after today ({today}). Use today or an earlier date.",
        "people.err_list_choice": "{label} must be one of the choices in the list.",
        "people.err_no_row": "No {what} with id {id}.",
        "people.err_history": "Start date {start} is before {latest}, the date of the last change. History is never "
                              "rewritten; use a date on or after it.",
        "people.err_gender": "Gender must be M or F, or empty.",
        "people.err_family_role": "Family role must be one of: Head, Spouse, Child, Other.",
        "people.err_ministry_role": "Ministry role must be one of: Leader, Member.",
        "people.err_note_empty": "A private note needs some text.",
        "people.err_no_note": "This Person has no Private note with id {id}.",
        "people.all": "All",
        "people.no_status": "No Status",
        "people.filter_status": "Filter by Status",
        "people.find_in_list": "Find in this list",
        "people.search_hint": "With or without accents",
        "people.clear": "Clear",
        "people.list": "People list",
        "people.count_of": "{n} of {total}",
        "people.empty": "No Person yet. Add the first Person.",
        "people.empty_q": "No Person matches “{q}” here.",
        "people.empty_status": "No Person has this Status now.",
        "people.first_status": "First Status",
        "people.birth_hint": "Leave empty if you do not know it.",
        "people.address_hint": "Used when the Person is not in a Family.",
        "people.note_hint": "A normal note. A Private note is added on the Person page.",
        "people.start_hint": "The day this Status began. Not after today.",
        "people.add_button": "Add Person",
        "people.added": "Person added.",
        "people.edit_title": "Edit {name}",
        "people.edit_hint": "Status, Family and Ministry keep their history: change them on the {link}.",
        "people.person_page": "Person page",
        "people.details_saved": "Details saved.",
        "people.go_people": "Go to People",
        "people.go_person": "Go back to the Person",
        "people.new_status": "New Status",
        "people.change_status": "Change Status",
        "people.no_status_yet": "No Status yet.",
        "people.leave_family": "— Leave the Family —",
        "people.no_family_option": "— Not in a Family —",
        "people.move_hint": "The day of the move. The old Family link is kept.",
        "people.save_family": "Save Family",
        "people.not_in_family": "Not in a Family. The Person's own address is used.",
        "people.set_family": "Set or leave a Family",
        "people.stop_serving": "Stop serving in this Ministry",
        "people.save_ministry": "Save Ministry",
        "people.not_serving": "Not serving in a Ministry.",
        "people.not_serving_now": "Not serving now",
        "people.change_ministry": "Add, change or end a Ministry",
        "people.story": "Story",
        "people.what_happened": "What happened",
        "people.no_story": "No story yet.",
        "people.story_lines_one": "{n} line, newest first",
        "people.story_lines_many": "{n} lines, newest first",
        "people.details": "Details",
        "people.family_address": "(Family address)",
        "people.edit_details": "Edit details",
        "people.private_label": "Private note — only you see this",
        "people.private_meta": "Never printed. Removed at Handover.",
        "people.change_note": "Change this Private note",
        "people.save_note": "Save Private note",
        "people.edit_note_aria": "Edit the Private note of {when}",
        "people.no_note": "No Private note yet.",
        "people.new_note": "New Private note",
        "people.add_note": "Add Private note",
        "people.note_added": "Private note added.",
        "people.note_changed": "Private note changed.",
        "people.no_visit_done": "No Visit done yet.",
        "people.plan_visit": "Plan a Visit",
        "people.care_meta": "Done Visits, newest first",
        "people.status_since": "{status} since {date}",
        "people.last_visit": "Last Visit {date}",
        "people.no_visit": "No Visit yet",
        "people.status_same": "Status is already {name}.",
        "people.status_changed": "Status changed to {name} from {date}.",
        "people.family_none": "The Person is not in a Family.",
        "people.family_left": "Left {name} on {date}. The old Family link is kept.",
        "people.family_same": "Already in {name} as {role}.",
        "people.family_now": "Now in {name} as {role} from {date}.",
        "people.ministry_none": "The Person does not serve in {name}.",
        "people.ministry_stopped": "Stopped serving in {name} on {date}.",
        "people.ministry_same": "Already {role} in {name}.",
        "people.ministry_now": "{role} in {name} from {date}.",
        "people.story_status": "Status: {name}",
        "people.story_family": "Family: {name} ({role})",
        "people.story_family_end": "Left Family {name}",
        "people.story_chi_phai": "Chi phái: {name} (Family {family})",
        "people.story_truong": "Trưởng Chi phái of {name}",
        "people.story_truong_end": "No longer Trưởng Chi phái of {name}",
        "people.story_ministry": "Ministry: {name} ({role})",
        "people.story_ministry_end": "Stopped serving in Ministry {name}",
        "people.story_serves": "Serves at {kind}: {title}",
        "people.story_joins": "Joins {kind}: {title}",
        "people.story_visit_done": "Visit done: {who}",
        "people.story_visit_planned": "Visit planned: {who}",
        "people.story_offering": "Offering {amount} to {fund}",
        "people.story_document": "Document: {name}",
        "people.story_private_note": "Private note: {body}",
        "people.title": "People",
        "people.add": "Add a Person",
        "people.count_one": "{n} Person",
        "people.count_many": "{n} People",
        # --- families
        "families.name": "Family name",
        "families.count_one": "{n} Family",
        "families.count_many": "{n} Families",
        "families.in_family_now": "{people} in a Family now",
        "families.list": "Families list",
        "families.col_people_now": "People now",
        "families.empty": "No Family yet. Add the first Family.",
        "families.name_hint": "For example: Gia đình Nguyễn Hải Đăng",
        "families.address_hint": "Every Person in this Family uses this address.",
        "families.add_button": "Add Family",
        "families.new_hint": "Then put people in it from each Person page (Family, Family role and date).",
        "families.added": "Family added.",
        "families.people_now": "People now",
        "families.people_before": "People before",
        "families.people_before_meta": "Old Family links, kept with their dates",
        "families.no_one_now": "No one is in this Family now.",
        "families.no_one_left": "No one has left this Family.",
        "families.move_hint": "To add or move a Person, open their Person page.",
        "families.leave_chi_phai": "— Leave the Chi phái —",
        "families.no_chi_phai_option": "— No Chi phái —",
        "families.chi_phai_hint": "The old Chi phái link is kept with its dates.",
        "families.change_chi_phai": "Change Chi phái",
        "families.not_in_chi_phai": "This Family is not in a Chi phái.",
        "families.chi_phai_since": "{name} since {date}",
        "families.no_chi_phai": "No Chi phái",
        "families.address_meta": "Every Person in this Family uses it",
        "families.edit": "Edit Family",
        "families.go": "Go to Families",
        "families.edit_hint": "Who is in this Family changes on each Person page, and its Chi phái on the {link}. "
                              "Both keep their history.",
        "families.family_page": "Family page",
        "families.back": "Back to the Family",
        "families.saved": "Family name and Address saved.",
        "families.chi_phai_left": "Left {name} on {date}. The old link is kept.",
        "families.chi_phai_same": "Already in {name}.",
        "families.chi_phai_now": "Now in {name} from {date}.",
        "families.title": "Families",
        "families.add": "Add a Family",
        # --- chi_phai
        "chi_phai.name": "Chi phái name",
        "chi_phai.count_one": "{n} Chi phái",
        "chi_phai.count_many": "{n} Chi phái",
        "chi_phai.list": "Chi phái list",
        "chi_phai.truong": "Trưởng Chi phái",
        "chi_phai.col_families_now": "Families now",
        "chi_phai.empty": "No Chi phái yet. Add the first Chi phái.",
        "chi_phai.name_hint": "For example: Chi phái Hòa Bình",
        "chi_phai.add_button": "Add Chi phái",
        "chi_phai.new_hint": "Then put Families in it from each Family page.",
        "chi_phai.added": "Chi phái added.",
        "chi_phai.err_exists": "Chi phái \"{name}\" already exists.",
        "chi_phai.families_now": "Families now",
        "chi_phai.families_before": "Families before",
        "chi_phai.families_before_meta": "Old Chi phái links, kept with their dates",
        "chi_phai.no_family_now": "No Family is in this Chi phái now.",
        "chi_phai.no_family_left": "No Family has left this Chi phái.",
        "chi_phai.move_hint": "To add or move a Family, open its Family page.",
        "chi_phai.no_truong_option": "— No Trưởng Chi phái —",
        "chi_phai.inside": "In this Chi phái",
        "chi_phai.others": "Everyone else",
        "chi_phai.truong_hint": "The past Trưởng Chi phái is kept with dates.",
        "chi_phai.set_truong": "Set Trưởng Chi phái",
        "chi_phai.no_truong_yet": "No Trưởng Chi phái yet.",
        "chi_phai.truong_since": "Trưởng Chi phái {name} since {date}",
        "chi_phai.no_truong": "No Trưởng Chi phái",
        "chi_phai.rename": "Rename Chi phái",
        "chi_phai.go": "Go to Chi phái",
        "chi_phai.rename_title": "Rename {name}",
        "chi_phai.rename_hint": "Its Families and its Trưởng Chi phái stay as they are, with their dates. The new "
                                "name shows on every page at once.",
        "chi_phai.back": "Back to the Chi phái",
        "chi_phai.renamed": "Renamed to {name}.",
        "chi_phai.name_same": "The name is already {name}.",
        "chi_phai.truong_none": "This Chi phái has no Trưởng Chi phái.",
        "chi_phai.truong_ended": "{name} is no longer Trưởng Chi phái from {date}.",
        "chi_phai.truong_same": "{name} is already Trưởng Chi phái.",
        "chi_phai.truong_now": "{name} is Trưởng Chi phái from {date}.",
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
