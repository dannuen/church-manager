# Church Manager

An offline database that helps one senior pastor run one church: its people, calendar, money, documents and pastoral care. Each church has its own copy.

## People

**Person**:
Anyone the church knows about, whether member, visitor, child, someone who left or someone who passed away.
_Tiếng Việt_: Người
_Tránh (tiếng Việt)_: tín hữu (đó là một Trạng thái), thành viên, người dùng
_Avoid_: Member (that is a status), contact, user

**Status**:
Where a person stands with the church right now, such as Member, Attender, Visitor, Left or Passed away. Each change is kept with its date.
_Tiếng Việt_: Trạng thái
_Tránh (tiếng Việt)_: loại, phân loại
_Avoid_: Type, category

**Family**:
A group of people who share one address. A person is in at most one family at a time; past family links are kept with dates. A person with no family keeps their own address.
_Tiếng Việt_: Gia đình
_Tránh (tiếng Việt)_: hộ, hộ gia đình, hộ khẩu
_Avoid_: Household

**Chi phái**:
A group of families in one area. A family is in at most one chi phái at a time; past links are kept with dates.
_Tiếng Việt_: Chi phái
_Tránh (tiếng Việt)_: khu vực, vùng, nhóm tế bào
_Avoid_: Area, zone, cell group

**Trưởng Chi phái**:
The one person who leads a chi phái. Past leaders are kept with dates.
_Tiếng Việt_: Trưởng Chi phái
_Avoid_: Area leader

**Family role**:
A person's place in their family: Head, Spouse, Child or Other.
_Tiếng Việt_: Vai trò trong gia đình

**Ministry**:
A serving team in the church, such as Worship, Youth or Children.
_Tiếng Việt_: Ban ngành
_Tránh (tiếng Việt)_: nhóm (dễ nhầm với buổi nhóm), phòng, đội
_Avoid_: Department, group, team

**Ministry role**:
How a person is part of a ministry: Leader or Member.
_Tiếng Việt_: Vai trò trong ban

**Private note**:
A note only the pastor sees, such as counseling or prayer. Never part of a handover.
_Tiếng Việt_: Ghi chú cá nhân
_Tránh (tiếng Việt)_: ghi chú mật, ghi chú bí mật
_Avoid_: Secret note

**People file**:
A .xlsx file with one row per new Person, used to add many people at once. Read once, never kept.
_Tiếng Việt_: Tệp danh sách người
_Tránh (tiếng Việt)_: tải lên, tệp đính kèm
_Avoid_: Upload, import file

## Calendar

**Calendar item**:
Anything with a date and time: a service, meeting, visit or event. It can list people who join or serve, and can repeat.
_Tiếng Việt_: Lịch
_Tránh (tiếng Việt)_: lịch trình, lịch hẹn, hoạt động, sự kiện (đó là một loại lịch)
_Avoid_: Schedule, appointment, activity

**Service**:
A worship gathering, such as Sunday service.
_Tiếng Việt_: Giờ thờ phượng
_Tránh (tiếng Việt)_: thánh lễ, buổi họp (đó là một loại lịch khác)
_Avoid_: Mass, meeting

**Head count**:
The number of people at one service, with a note about who was absent.
_Tiếng Việt_: Số người nhóm
_Tránh (tiếng Việt)_: điểm danh, sổ điểm danh
_Avoid_: Attendance record

## Money

**Offering**:
Money given to the church, with an amount, a fund and an optional giver.
_Tiếng Việt_: Dâng hiến
_Tránh (tiếng Việt)_: quyên góp, phần mười, thu nhập

**Giver**:
The person or family an offering is from. An offering with no giver is a no-name offering.
_Tiếng Việt_: Người dâng hiến
_Tránh (tiếng Việt)_: nhà hảo tâm, người quyên góp
_Avoid_: Donation, tithe, income

**Fund**:
Where an offering goes, such as General, Building or Missions.
_Tiếng Việt_: Quỹ

**Expense**:
Money the church spends, with an amount and a spending category.
_Tiếng Việt_: Khoản chi
_Tránh (tiếng Việt)_: chi phí, chi tiêu, thanh toán
_Avoid_: Cost, spending, payment

**Spending category**:
What an expense is for, such as Rent, Utilities or Events.
_Tiếng Việt_: Hạng mục chi

**Giving statement**:
A yearly list of one giver's offerings, for a person or a family.
_Tiếng Việt_: Tổng kết dâng hiến
_Tránh (tiếng Việt)_: biên nhận, biên lai, phiếu thu
_Avoid_: Receipt, tax letter

## Care

**Visit**:
A calendar item where the pastor visits a person or family. Done visits make up the care log.
_Tiếng Việt_: Thăm viếng
_Avoid_: Pastoral call, home visit

**Care log**:
All done visits: who, when and a short note.
_Tiếng Việt_: Nhật ký thăm viếng

**Needs a visit**:
A person whose last pastoral visit is older than the care reminder time (3 months by default).
_Tiếng Việt_: Cần thăm viếng

## Documents

**Document**:
A file kept inside the church copy, linked to a person, family or calendar item.
_Tiếng Việt_: Tài liệu
_Tránh (tiếng Việt)_: tệp đính kèm, tải lên
_Avoid_: Attachment, upload

**Sent document**:
A document the church sends out, with a date, a recipient, a purpose and a number per year (such as 05/2026).
_Tiếng Việt_: Công văn đi
_Tránh (tiếng Việt)_: thư, thư đi
_Avoid_: Letter, outgoing mail

**Recipient**:
The outside body a sent document goes to: Chính quyền (government), Giáo hội (denomination) or Hội Thánh (another church). The list is editable.
_Tiếng Việt_: Nơi nhận
_Tránh (tiếng Việt)_: người nhận (nơi nhận là một cơ quan, không phải một người)

**Purpose**:
Why a sent document is sent, such as Invitation, Notice, Certificate or Report. The list is editable.
_Tiếng Việt_: Mục đích

## Copies

**Church copy**:
One church's whole database in one file plus its documents folder.
_Tiếng Việt_: Dữ liệu Hội Thánh
_Tránh (tiếng Việt)_: bản sao, phiên bản, bản cài đặt
_Avoid_: Instance, install, tenant

**Handover**:
Giving the church copy to the next pastor of the same church, with private notes removed.
_Tiếng Việt_: Bàn giao

**New church setup**:
Starting a blank church copy that keeps only the default lists.
_Tiếng Việt_: Lập dữ liệu Hội Thánh mới
_Tránh (tiếng Việt)_: thành lập Hội Thánh, mở Hội Thánh mới (đó là mở một Hội Thánh thật)

## Words on screen (Vietnamese)

The words the app shows on screen, in Vietnamese. Bold rows name the group.

| English | Tiếng Việt |
|---|---|
| **Status** | **Trạng thái** |
| Member | Tín hữu |
| Attender | Thân hữu |
| Visitor | Khách |
| Left | Nghỉ nhóm |
| Passed away | Về với Chúa |
| **Family role** | **Vai trò trong gia đình** |
| Head | Chủ gia đình |
| Spouse | Vợ/Chồng |
| Child | Con |
| Other | Người thân khác |
| **Ministry role** | **Vai trò trong ban** |
| Leader | Trưởng ban |
| Member | Ban viên |
| **Calendar item kind** | **Loại lịch** |
| Service | Giờ thờ phượng |
| Meeting | Buổi họp |
| Visit | Thăm viếng |
| Event | Chương trình |
| **Ministry (default list)** | **Ban ngành (danh sách có sẵn)** |
| Worship | Ban Âm nhạc |
| Youth | Ban Thanh niên |
| Children | Ban Thiếu nhi |
| **Fund (default list)** | **Quỹ (danh sách có sẵn)** |
| General | Quỹ Hội Thánh |
| Building | Quỹ xây dựng |
| Missions | Quỹ truyền giáo |
| **Spending category (default list)** | **Hạng mục chi (danh sách có sẵn)** |
| Rent | Tiền thuê |
| Utilities | Điện nước |
| Events | Chương trình |
| **Purpose (default list)** | **Mục đích (danh sách có sẵn)** |
| Invitation | Thư mời |
| Notice | Thông báo |
| Certificate | Giấy chứng nhận |
| Report | Báo cáo |
| **Menu** | **Menu** |
| Dashboard | Trang chủ |
| People | Mọi người |
| Families | Gia đình |
| Calendar | Lịch |
| Money | Tài chính |
| Care | Thăm viếng |
| Documents | Tài liệu |
| Sent documents | Văn bản đi |
| Lists | Danh mục |
| Copies | Dữ liệu |
| Settings | Cài đặt |
| Search | Tìm kiếm |
| **Buttons** | **Nút** |
| Add | Thêm |
| Save | Lưu |
| Edit | Chỉnh sửa |
| Cancel | Hủy |
| Print | In |
| Back | Quay lại |
| Open | Mở |
| Close (end a link) | Kết thúc |
| Mark done | Hoàn tất |
| **Other words** | **Từ khác** |
| no-name offering | Ẩn danh |
| care reminder time | Nhắc thăm viếng |
| People file | Tệp danh sách người |
