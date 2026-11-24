# Church Manager

Church Manager giúp một mục sư quản nhiệm điều hành một Hội Thánh: mọi người, gia đình, chi phái,
lịch, tài chính, thăm viếng, tài liệu và công văn đi. Phần mềm chạy trên máy của bạn, mở trong
trình duyệt web. **Không cần Internet. Dữ liệu không gửi lên mạng.**

Bạn chỉ cần làm phần **Cài đặt** một lần. Những lần sau, chỉ cần làm phần **Mở phần mềm**.

---

## Cài đặt (làm một lần, khoảng 10 phút)

### Bước 1: Cài Python

Python là phần mềm miễn phí. Church Manager cần nó để chạy.

1. Mở trình duyệt (Chrome, Edge, Cốc Cốc...). Vào trang **https://www.python.org/downloads/**
2. Bấm nút vàng **Download Python 3.14** (hoặc số lớn hơn).
3. Mở tệp vừa tải về (thường nằm trong thư mục **Downloads / Tải xuống**).
4. Nếu thấy ô **Add python.exe to PATH**, hãy **đánh dấu ô này**.
5. Bấm **Install Now** (Cài ngay). Chờ đến khi thấy **Setup was successful**. Bấm **Close**.

> Nếu máy hỏi "Bạn có cho phép ứng dụng này thay đổi thiết bị không?", bấm **Có / Yes**.

### Bước 2: Tải Church Manager về máy

1. Vào trang **https://github.com/dannuen/church-manager**
2. Bấm nút xanh **Code**, rồi bấm **Download ZIP**.
3. Mở thư mục **Downloads / Tải xuống**. Bấm chuột phải vào tệp `church-manager-main.zip`,
   chọn **Extract All... / Giải nén tất cả...**, rồi bấm **Extract / Giải nén**.
4. Bạn sẽ có thư mục `church-manager-main`. Có thể kéo thư mục này ra **Desktop** cho dễ tìm.

> Quan trọng: phải giải nén. Đừng mở phần mềm từ bên trong tệp ZIP.

Xong. Bạn đã cài đặt xong.

---

## Mở phần mềm (mỗi lần dùng)

1. Mở thư mục `church-manager-main`.
2. Bấm đúp (nhấp nhanh 2 lần) vào tệp **`Mo Church Manager.bat`**.
3. Một cửa sổ đen hiện ra. Sau vài giây, trình duyệt tự mở Church Manager.
4. **Đừng đóng cửa sổ đen** khi đang làm việc. Nó là "máy chạy" của phần mềm.

Nếu trình duyệt không tự mở: mở trình duyệt và gõ địa chỉ **http://127.0.0.1:8765**

> Nếu Windows hiện khung xanh "Windows protected your PC": bấm **More info / Thông tin thêm**,
> rồi bấm **Run anyway / Vẫn chạy**.

**Lần đầu tiên**, phần mềm hỏi tên Hội Thánh. Gõ tên Hội Thánh, rồi bấm nút **Lập dữ liệu Hội Thánh**.
Phần mềm tạo **dữ liệu Hội Thánh** mới, trống, với các danh sách có sẵn.

### Tắt phần mềm

1. Đóng trang Church Manager trong trình duyệt.
2. Bấm vào cửa sổ đen, rồi bấm **Ctrl + C** (giữ phím Ctrl, bấm phím C).
3. Nếu cửa sổ hỏi `Terminate batch job (Y/N)?`, gõ **Y** rồi bấm **Enter**.

---

## Đổi ngôn ngữ

Phần mềm hiện chữ bằng **Tiếng Việt** hoặc **English** (tiếng Anh). Bạn chọn.

1. Nhìn lên góc trên bên phải của trang. Có hai nút: **Tiếng Việt** và **English**. Nút của ngôn ngữ
   đang dùng có khung viền và chữ đậm.
2. Bấm một lần vào ngôn ngữ bạn muốn. Trang hiện lại ngay bằng ngôn ngữ đó, và bạn vẫn ở đúng trang
   đang xem.
3. Xong. Sau khi đã có dữ liệu Hội Thánh, phần mềm nhớ lựa chọn này. Lần sau mở phần mềm, chữ vẫn hiện
   bằng ngôn ngữ bạn đã chọn. Mỗi dữ liệu Hội Thánh nhớ ngôn ngữ riêng của nó.

Hai nút này có ở mọi trang. Bạn cũng có thể đổi ngôn ngữ trong trang **Cài đặt** (ở thanh menu): chọn
ô **Ngôn ngữ**, rồi bấm **Lưu cài đặt**.

- Một Hội Thánh mới (**Lập dữ liệu Hội Thánh mới**) bắt đầu bằng **Tiếng Việt**. Lúc lập, bạn cũng có thể
  chọn **English** ở ô **Ngôn ngữ**.
- Phần mềm chỉ đổi chữ của phần mềm. Tên người, ghi chú và các mục trong **Danh mục** giữ y như lúc
  được nhập. Phần mềm **không bao giờ dịch** chúng.

---

## Thêm nhiều người cùng lúc từ tệp .xlsx

Bạn có danh sách người trong một bảng tính? Bạn có thể thêm tất cả cùng lúc, không cần điền từng người.

1. Bấm **Mọi người** ở thanh menu, rồi bấm **Thêm từ tệp .xlsx**.
2. Bấm **Lấy tệp mẫu trống**. Trình duyệt lưu tệp `Tep danh sach nguoi.xlsx`.
3. Mở tệp đó bằng chương trình bảng tính. Trang tính **Mọi người** có dòng tiêu đề các cột. Trang tính
   **Hướng dẫn** nói cách điền từng cột và có một dòng ví dụ (dòng ví dụ không bao giờ được thêm).
4. Trên trang tính **Mọi người**, viết mỗi Người trên một dòng, dưới dòng tiêu đề. Chỉ cột **Họ và tên**
   là bắt buộc. Ngày viết như `31/12/1980`. Ngày sinh có thể chỉ viết năm, như `1980`. Đừng đổi tiêu đề các cột. Lưu tệp dưới dạng `.xlsx`.
5. Trở lại Church Manager. Ở ô **Tệp danh sách người (.xlsx)**, chọn tệp vừa lưu, rồi bấm **Kiểm tra tệp**.
6. Trang kiểm tra hiện từng dòng: **Hợp lệ**, hoặc một câu nói rõ dòng nào, cột nào cần sửa.
   **Chưa có gì được lưu.**
   - Có dòng lỗi: không có nút **Lưu**. Sửa các dòng đó trong tệp, lưu tệp, rồi chọn lại tệp.
   - Không có lỗi: bấm **Lưu**. Mọi người trong tệp được thêm cùng lúc. Bấm **Hủy** nếu không muốn lưu.
   - Một dòng trùng tên với một Người đã có chỉ là **cảnh báo**: vẫn lưu được, vì hai người có thể cùng tên.

**Gia đình.** Hai cột **Gia đình** và **Vai trò trong gia đình** không bắt buộc.

- Tên một Gia đình đã có (viết có dấu hay không dấu đều được): Người đó vào Gia đình này.
- Một tên mới: phần mềm tạo **một** Gia đình mới cho mọi dòng có tên đó. Địa chỉ của Gia đình mới là
  **Địa chỉ** đầu tiên trong các dòng đó.
- Có Gia đình thì phải điền Vai trò trong gia đình: **Chủ gia đình**, **Vợ/Chồng**, **Con** hoặc
  **Người thân khác**.
- Nếu hai Gia đình trong phần mềm có cùng tên, dòng đó báo lỗi. Hãy để trống ô Gia đình, rồi chọn Gia đình
  trên trang của Người đó sau khi lưu.
- Gia đình và Trạng thái bắt đầu từ **Ngày bắt đầu** của dòng (để trống là hôm nay).

**Lưu ý**

- Lưu là "tất cả hoặc không gì": hoặc mọi dòng được thêm, hoặc không dòng nào.
- Tệp chỉ thêm Người mới (và Gia đình mới). Tệp không sửa và không xoá ai, không đổi Gia đình nào đã có.
- Phần mềm đọc tệp một lần và không giữ tệp. Chỉ trang tính đầu tiên được đọc. Ghi chú cá nhân không bao
  giờ được đọc từ tệp.
- Tối đa 5.000 người mỗi tệp. Chi phái, Ban ngành và Ghi chú cá nhân thì đặt trên trang của từng Người.

---

## Lịch phân công (Roster)

Lịch phân công cho biết ai làm từng **Phân công** (Service role) trong mỗi Giờ thờ phượng: mỗi tuần một
dòng, mỗi tháng một bảng, mỗi trang một quý. Bấm **Lịch** ở thanh menu, rồi bấm **Lịch phân công**.

### Thiết lập (làm một lần)

Trên trang Lịch phân công, bấm **Thiết lập**.

1. **Phân công.** Có sẵn 4 Phân công: **Bồi linh** (Thứ Năm), **Hướng dẫn chương trình**, **Dâng hiến**
   và **Ban ngành** (Chúa Nhật). Ban ngành do một Ban ngành làm, 2 Giờ thờ phượng một lần, và hiện ở cột
   **Ghi chú**. Bạn có thể thêm một Phân công, đổi tên, hoặc **Ẩn** nó (lịch sử vẫn được giữ).
2. **Thứ tự luân phiên.** Bấm vào tên một Phân công. Thêm từng Người (hoặc Ban ngành) theo thứ tự.
   Bấm **Lên** hoặc **Xuống** để đổi chỗ, **Bỏ ra** để bỏ một người ra. Mỗi người có lượt bằng nhau.
3. **Ngày Bỏ qua.** Thêm một ngày không xếp Phân công (ví dụ Nghỉ Tết, Hội đồng bồi linh) và lý do.
   Lịch phân công hiện lý do ở ngày đó.
4. **Quy tắc trùng người.** Chọn một Người được làm bao nhiêu Phân công. Mặc định: **Một Phân công mỗi Giờ
   thờ phượng** (một tuần có thể làm hai Phân công, nhưng không làm hai Phân công trong cùng một Giờ thờ phượng).

### Tự động xếp lịch (Auto-fill)

1. Trên trang Lịch phân công, bấm **Tự động xếp lịch**.
2. Trang mới cho xem trước các tên mới của quý đang xem. **Chưa có gì được lưu.** Muốn khoảng ngày
   khác: đổi ngày ở ô **Khoảng ngày**, rồi bấm **Xem trước**.
3. Bấm **Lưu các tên mới** để lưu.

Tự động xếp lịch **chỉ điền Phân công còn trống**. Tên đã có không bao giờ bị đổi.

### Đổi người

Trên Lịch phân công, bấm vào ngày của một Giờ thờ phượng. Ở phần **Phân công**, chọn người khác rồi
bấm **Lưu**, hoặc bấm **Bỏ trống**. Tên cũ vẫn được giữ, gạch ngang, kèm ngày bắt đầu và ngày kết thúc.
Không có gì bị xoá.

### Dữ liệu Hội Thánh từ phần mềm cũ

Dữ liệu Hội Thánh lập bằng phần mềm cũ (chưa có Lịch phân công) được nâng cấp **tự động, lần đầu mở**
bằng phần mềm mới: phần mềm thêm Lịch phân công và 4 Phân công có sẵn. Thông tin cũ không bị thay đổi.
Nên sao lưu trước khi mở (xem "Sao lưu" ở dưới).

---

## Dữ liệu được lưu ở đâu

Toàn bộ dữ liệu của một Hội Thánh nằm trong **một thư mục** (gọi là **dữ liệu Hội Thánh**):

- tệp `church.db`: cơ sở dữ liệu,
- thư mục `documents`: các tài liệu bạn đính kèm.

Thư mục này nằm ở: `%LOCALAPPDATA%\ChurchManager\<tên-hội-thánh>\`
(tên viết không dấu, ví dụ `hoi-thanh-tin-lanh-binh-an`).

Cách mở thư mục đó: bấm phím **Windows + R**, gõ `%LOCALAPPDATA%\ChurchManager`, bấm **Enter**.

> Phần mềm **không bao giờ** lưu dữ liệu trong OneDrive. Như vậy dữ liệu không bị đưa lên mạng.

---

## Sao lưu (nên làm mỗi tháng)

1. Tắt phần mềm (xem "Tắt phần mềm" ở trên).
2. Bấm **Windows + R**, gõ `%LOCALAPPDATA%\ChurchManager`, bấm **Enter**.
3. Chép **cả thư mục** của Hội Thánh sang USB hoặc ổ cứng ngoài.

---

## Bàn giao cho mục sư kế nhiệm (Handover)

Bàn giao tạo một bản bàn giao để trao cho mục sư kế tiếp của cùng Hội Thánh.
**Ghi chú cá nhân (Private notes) của bạn bị xoá khỏi bản bàn giao này.** Dữ liệu của bạn không bị thay đổi.
**Hình Hội Thánh** (chọn trong **Cài đặt**) được giữ trong dữ liệu Hội Thánh, nên cũng đi theo bản bàn giao.

1. Trong phần mềm, bấm **Dữ liệu** ở thanh menu.
2. Bấm **Tạo Bàn giao**.
3. Phần mềm tạo một tệp ZIP. Trang có đường link để tải tệp này.
   Tệp cũng được lưu trong `%LOCALAPPDATA%\ChurchManager\handovers\`.
4. Chép tệp ZIP vào USB và trao cho mục sư kế nhiệm.

Nếu phần mềm **không tạo tệp ZIP** và hiện một danh sách: lời trong một ghi chú cá nhân cũng
được viết ở chỗ khác (ví dụ trong một tài liệu). Trang cho biết chỗ đó. Hãy xoá hoặc sửa lời đó ở
từng chỗ (với tài liệu: bấm **Xóa** bên cạnh tài liệu đó, cũng có trong **Tài liệu**). Sửa ghi chú
cá nhân không làm thay đổi tệp tài liệu, nên tệp vẫn sẽ đi theo bản bàn giao. Sau đó bấm
**Tạo Bàn giao** lại. Lưu ý: phần mềm chỉ đọc được tài liệu dạng chữ thường; chữ bên trong tệp
Word hoặc PDF không được kiểm tra.

### Mục sư kế nhiệm mở dữ liệu được bàn giao

1. Cài đặt Church Manager (Bước 1 và Bước 2 ở trên).
2. Giải nén tệp ZIP bàn giao vào một thư mục mới, **không nằm trong OneDrive**.
   Ví dụ: `C:\HoiThanh`. Thư mục này phải có tệp `church.db` và thư mục `documents`.
3. Mở thư mục `church-manager-main`. Bấm vào thanh địa chỉ ở trên cùng, gõ `cmd`, bấm **Enter**.
4. Trong cửa sổ đen, gõ dòng sau rồi bấm **Enter** (thay `C:\HoiThanh` bằng thư mục của bạn):

   ```
   "Mo Church Manager.bat" --copy "C:\HoiThanh"
   ```

   Mỗi lần mở phần mềm, làm lại bước 3 và 4.

---

## Lập dữ liệu Hội Thánh mới (New church setup)

1. Bấm **Dữ liệu** ở thanh menu, rồi chọn **Lập dữ liệu Hội Thánh mới**.
2. Gõ tên Hội Thánh, rồi bấm **Lập dữ liệu Hội Thánh mới**.

Phần mềm tạo dữ liệu mới, trống, chỉ có các danh sách có sẵn. Dữ liệu cũ vẫn còn.
Để mở lại dữ liệu cũ: **Dữ liệu** → **Các Dữ liệu Hội Thánh**.

---

## Khi gặp lỗi

| Bạn thấy | Cách làm |
|---|---|
| `Khong tim thay Python` | Làm lại Bước 1. Nhớ đánh dấu ô **Add python.exe to PATH**. Sau đó khởi động lại máy. |
| Cửa sổ đen hiện rồi tắt ngay | Làm lại Bước 2. Nhớ giải nén tệp ZIP trước khi mở. |
| `Not started: ... busy` | Phần mềm đã đang chạy ở một cửa sổ đen khác. Dùng cửa sổ đó, hoặc tắt nó rồi mở lại. |
| `Not started: ... OneDrive` | Thư mục dữ liệu nằm trong OneDrive. Chuyển nó ra chỗ khác, ví dụ `C:\HoiThanh`. |
| Trình duyệt báo "không truy cập được trang" | Cửa sổ đen đã bị đóng. Bấm đúp **`Mo Church Manager.bat`** lần nữa. |

---

## Dùng với Hermes (không bắt buộc)

Hermes là trợ lý AI chạy trên máy này. Bạn **không cần** Hermes. Church Manager vẫn chạy y như
cũ khi không có Hermes.

Khi bật **Cổng Hermes** (cửa cho Hermes), Hermes có thể đọc dữ liệu Hội Thánh và lưu thông tin
mới giúp bạn, nhưng **chỉ sau khi bạn đồng ý**. Hermes dùng lệnh `python -m churchmgr.agent` và
hướng dẫn trong thư mục `hermes\skills\church-manager`. Hermes **không bao giờ** thấy ghi chú cá nhân.

### Bật

1. Mở Church Manager, bấm **Cài đặt**.
2. Đặt **Cổng Hermes** thành **Bật**.
3. Bấm **Lưu cài đặt**.

### Thêm hướng dẫn (skill) vào Hermes

1. Chép thư mục `hermes\skills\church-manager` (trong thư mục phần mềm) vào
   `%LOCALAPPDATA%\hermes\skills\`. Nếu bạn dùng một hồ sơ (profile) Hermes, chép vào
   `%LOCALAPPDATA%\hermes\profiles\<tên>\skills\`.
2. Chạy lệnh `hermes skills list` và xem có `church-manager` trong danh sách.

### Thử

Trong cửa sổ lệnh ở thư mục phần mềm, chạy `python -m churchmgr.agent status`. Lệnh in tên
Hội Thánh và số người, gia đình, lịch, dâng hiến và khoản chi. Khi Cổng Hermes đang tắt, lệnh
báo cửa đang tắt và không thay đổi gì.

### Cách lưu dữ liệu

1. Hermes chạy lệnh trước mà không có `--yes`. Đây là chạy thử: không lưu gì.
2. Hermes cho bạn biết sẽ lưu gì và hỏi: "Lưu không? có hay không".
3. Chỉ khi bạn nói có, Hermes mới chạy lại lệnh đó với `--yes`. Khi đó mới lưu.

Không lệnh nào xoá hoặc sửa thông tin cũ. Thay đổi duy nhất là đánh dấu một lần thăm đã làm xong.

### Tắt

- Trong Church Manager: **Cài đặt** → **Cổng Hermes** → **Tắt**, rồi **Lưu cài đặt**. Sau đó mọi
  lệnh đều dừng và báo rõ lý do.
- Để gỡ hướng dẫn: xoá thư mục `church-manager` bạn đã chép vào thư mục `skills` của Hermes.

### An toàn

- Ghi chú cá nhân không bao giờ ra khỏi phần mềm. Không lệnh nào đọc chúng.
- Cổng Hermes chỉ điều khiển các lệnh của Hermes. Nó **không** khoá tệp dữ liệu: một chương trình
  khác trên máy vẫn đọc được tệp. Chỉ dùng Hermes mà bạn tin cậy.
- Những gì Hermes đọc sẽ được gửi tới mô hình AI bạn chọn trong Hermes. Nếu mô hình chạy trên mạng
  (cloud), dữ liệu Hội Thánh rời khỏi máy này. Mô hình chạy trên máy (local) giữ dữ liệu tại đây.

---

## Dành cho người rành máy tính

Chạy trực tiếp: `python app.py`. Chỉ cần Python 3.14, không cần cài thêm gói nào.

| Tuỳ chọn | Tác dụng |
|---|---|
| `--port N` | Dùng cổng N. Mặc định: 8765, hoặc cổng trống kế tiếp đến 8785. |
| `--no-browser` | Không tự mở trình duyệt. Cửa sổ in ra địa chỉ. |
| `--copy THƯ_MỤC` | Mở dữ liệu Hội Thánh trong THƯ_MỤC (phải có `church.db`). Không đổi `current.txt`. Biến môi trường tương ứng: `CHURCH_MANAGER_COPY`. |
| `--copies-root THƯ_MỤC` | Đổi thư mục chứa các dữ liệu Hội Thánh (mặc định `%LOCALAPPDATA%\ChurchManager\`). Biến môi trường: `CHURCH_MANAGER_HOME`. Nếu chỉ có `--copy`, thư mục chứa là thư mục cha của dữ liệu Hội Thánh. |

Tệp `current.txt` trong thư mục chứa ghi dữ liệu Hội Thánh nào được mở khi khởi động.

**Kiểm tra toàn bộ:** `python verify.py`. Lệnh này chạy mọi bài kiểm tra, tạo một Hội Thánh giả
50 người trong thư mục tạm, mở phần mềm, kiểm tra mọi ô trên Trang chủ và ô Tìm kiếm, tạo một
bản bàn giao và chứng minh không có ghi chú cá nhân, kiểm tra hai bản Tổng kết dâng hiến và các lệnh
Cổng Hermes (`python -m churchmgr.agent`), chạy Tự động xếp lịch và kiểm tra Lịch phân công. Sau đó lệnh
mở mọi trang bằng Tiếng Việt và bằng English, kiểm tra nút đổi ngôn ngữ, kiểm tra trang Tiếng Việt không
còn chữ tiếng Anh, và mở một dữ liệu Hội Thánh từ phần mềm cũ. In PASS hoặc FAIL cho
từng mục; trả về 0 chỉ khi tất cả đều đạt. Không bao giờ mở dữ liệu thật của bạn. `--keep` giữ thư mục
tạm; `--people N` đặt số người (20 đến 1000).
