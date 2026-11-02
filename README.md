# Church Manager

Church Manager giúp một mục sư quản nhiệm điều hành một Hội Thánh: tín hữu, gia đình, chi phái,
lịch, tài chính, thăm viếng, giấy tờ và công văn đi. Chương trình chạy trên máy của bạn, mở trong
trình duyệt web. **Không cần Internet. Dữ liệu không gửi lên mạng.**

Bạn chỉ cần làm phần **Cài đặt** một lần. Những lần sau, chỉ cần làm phần **Mở chương trình**.

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

> Quan trọng: phải giải nén. Đừng mở chương trình từ bên trong tệp ZIP.

Xong. Bạn đã cài đặt xong.

---

## Mở chương trình (mỗi lần dùng)

1. Mở thư mục `church-manager-main`.
2. Bấm đúp (nhấp nhanh 2 lần) vào tệp **`Mo Church Manager.bat`**.
3. Một cửa sổ đen hiện ra. Sau vài giây, trình duyệt tự mở Church Manager.
4. **Đừng đóng cửa sổ đen** khi đang làm việc. Nó là "máy chạy" của chương trình.

Nếu trình duyệt không tự mở: mở trình duyệt và gõ địa chỉ **http://127.0.0.1:8765**

> Nếu Windows hiện khung xanh "Windows protected your PC": bấm **More info / Thông tin thêm**,
> rồi bấm **Run anyway / Vẫn chạy**.

**Lần đầu tiên**, chương trình hỏi tên Hội Thánh. Gõ tên Hội Thánh, rồi bấm nút bắt đầu.
Chương trình tạo một **bản dữ liệu Hội Thánh** mới, trống, với các danh sách có sẵn.

### Tắt chương trình

1. Đóng trang Church Manager trong trình duyệt.
2. Bấm vào cửa sổ đen, rồi bấm **Ctrl + C** (giữ phím Ctrl, bấm phím C).
3. Nếu cửa sổ hỏi `Terminate batch job (Y/N)?`, gõ **Y** rồi bấm **Enter**.

---

## Dữ liệu được lưu ở đâu

Toàn bộ dữ liệu của một Hội Thánh nằm trong **một thư mục** (gọi là **bản dữ liệu Hội Thánh**):

- tệp `church.db`: cơ sở dữ liệu,
- thư mục `documents`: các giấy tờ bạn đính kèm.

Thư mục này nằm ở: `%LOCALAPPDATA%\ChurchManager\<tên-hội-thánh>\`
(tên viết không dấu, ví dụ `hoi-thanh-tin-lanh-binh-an`).

Cách mở thư mục đó: bấm phím **Windows + R**, gõ `%LOCALAPPDATA%\ChurchManager`, bấm **Enter**.

> Chương trình **không bao giờ** lưu dữ liệu trong OneDrive. Như vậy dữ liệu không bị đưa lên mạng.

---

## Sao lưu (nên làm mỗi tháng)

1. Tắt chương trình (xem "Tắt chương trình" ở trên).
2. Bấm **Windows + R**, gõ `%LOCALAPPDATA%\ChurchManager`, bấm **Enter**.
3. Chép **cả thư mục** của Hội Thánh sang USB hoặc ổ cứng ngoài.

---

## Bàn giao cho mục sư kế nhiệm (Handover)

Bàn giao tạo một bản sao dữ liệu để trao cho mục sư kế tiếp của cùng Hội Thánh.
**Ghi chú riêng (Private notes) của bạn bị xoá khỏi bản sao này.** Dữ liệu của bạn không bị thay đổi.

1. Trong chương trình, bấm **Copies** ở thanh menu.
2. Bấm **Make Handover**.
3. Chương trình tạo một tệp ZIP. Trang có đường link để tải tệp này.
   Tệp cũng được lưu trong `%LOCALAPPDATA%\ChurchManager\handovers\`.
4. Chép tệp ZIP vào USB và trao cho mục sư kế nhiệm.

Nếu chương trình **không tạo tệp ZIP** và hiện một danh sách: lời trong một ghi chú riêng cũng
được viết ở chỗ khác (ví dụ trong một giấy tờ). Trang cho biết chỗ đó. Hãy xoá hoặc sửa lời đó ở
từng chỗ (với giấy tờ: bấm **Delete** bên cạnh giấy tờ đó, cũng có trong **Documents**). Sửa ghi chú
riêng không làm thay đổi tệp giấy tờ, nên tệp vẫn sẽ đi theo bản bàn giao. Sau đó bấm
**Make Handover** lại. Lưu ý: chương trình chỉ đọc được giấy tờ dạng chữ thường; chữ bên trong tệp
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

   Mỗi lần mở chương trình, làm lại bước 3 và 4.

---

## Bắt đầu một Hội Thánh mới (New church setup)

1. Bấm **Copies** ở thanh menu, rồi chọn **New church setup**.
2. Gõ tên Hội Thánh, rồi bấm **Start New church setup**.

Chương trình tạo một bản dữ liệu mới, trống, chỉ có các danh sách có sẵn. Dữ liệu cũ vẫn còn.
Để mở lại dữ liệu cũ: **Copies** → **Church copies**.

---

## Khi gặp lỗi

| Bạn thấy | Cách làm |
|---|---|
| `Khong tim thay Python` | Làm lại Bước 1. Nhớ đánh dấu ô **Add python.exe to PATH**. Sau đó khởi động lại máy. |
| Cửa sổ đen hiện rồi tắt ngay | Làm lại Bước 2. Nhớ giải nén tệp ZIP trước khi mở. |
| `Not started: ... busy` | Chương trình đã đang chạy ở một cửa sổ đen khác. Dùng cửa sổ đó, hoặc tắt nó rồi mở lại. |
| `Not started: ... OneDrive` | Thư mục dữ liệu nằm trong OneDrive. Chuyển nó ra chỗ khác, ví dụ `C:\HoiThanh`. |
| Trình duyệt báo "không truy cập được trang" | Cửa sổ đen đã bị đóng. Bấm đúp **`Mo Church Manager.bat`** lần nữa. |

---

## Dùng với Hermes (không bắt buộc)

Hermes là trợ lý AI chạy trên máy này. Bạn **không cần** Hermes. Church Manager vẫn chạy y như
cũ khi không có Hermes.

Khi bật **Hermes door** (cửa cho Hermes), Hermes có thể đọc dữ liệu Hội Thánh và lưu thông tin
mới giúp bạn, nhưng **chỉ sau khi bạn đồng ý**. Hermes dùng lệnh `python -m churchmgr.agent` và
hướng dẫn trong thư mục `hermes\skills\church-manager`. Hermes **không bao giờ** thấy ghi chú riêng.

### Bật

1. Mở Church Manager, bấm **Settings**.
2. Đặt **Hermes door** thành **On**.
3. Bấm **Save settings**.

### Thêm hướng dẫn (skill) vào Hermes

1. Chép thư mục `hermes\skills\church-manager` (trong thư mục chương trình) vào
   `%LOCALAPPDATA%\hermes\skills\`. Nếu bạn dùng một hồ sơ (profile) Hermes, chép vào
   `%LOCALAPPDATA%\hermes\profiles\<tên>\skills\`.
2. Chạy lệnh `hermes skills list` và xem có `church-manager` trong danh sách.

### Thử

Trong cửa sổ lệnh ở thư mục chương trình, chạy `python -m churchmgr.agent status`. Lệnh in tên
Hội Thánh và số người, gia đình, mục lịch, dâng hiến và chi phí. Khi Hermes door đang tắt, lệnh
báo cửa đang tắt và không thay đổi gì.

### Cách lưu dữ liệu

1. Hermes chạy lệnh trước mà không có `--yes`. Đây là chạy thử: không lưu gì.
2. Hermes cho bạn biết sẽ lưu gì và hỏi: "Lưu không? có hay không".
3. Chỉ khi bạn nói có, Hermes mới chạy lại lệnh đó với `--yes`. Khi đó mới lưu.

Không lệnh nào xoá hoặc sửa thông tin cũ. Thay đổi duy nhất là đánh dấu một lần thăm đã làm xong.

### Tắt

- Trong Church Manager: **Settings** → **Hermes door** → **Off**, rồi **Save settings**. Sau đó mọi
  lệnh đều dừng và báo rõ lý do.
- Để gỡ hướng dẫn: xoá thư mục `church-manager` bạn đã chép vào thư mục `skills` của Hermes.

### An toàn

- Ghi chú riêng không bao giờ ra khỏi chương trình. Không lệnh nào đọc chúng.
- Hermes door chỉ điều khiển các lệnh của Hermes. Nó **không** khoá tệp dữ liệu: một chương trình
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
| `--copy THƯ_MỤC` | Mở bản dữ liệu Hội Thánh trong THƯ_MỤC (phải có `church.db`). Không đổi `current.txt`. Biến môi trường tương ứng: `CHURCH_MANAGER_COPY`. |
| `--copies-root THƯ_MỤC` | Đổi thư mục chứa các bản dữ liệu (mặc định `%LOCALAPPDATA%\ChurchManager\`). Biến môi trường: `CHURCH_MANAGER_HOME`. Nếu chỉ có `--copy`, thư mục chứa là thư mục cha của bản dữ liệu. |

Tệp `current.txt` trong thư mục chứa ghi bản dữ liệu nào được mở khi khởi động.

**Kiểm tra toàn bộ:** `python verify.py`. Lệnh này chạy mọi bài kiểm tra, tạo một Hội Thánh giả
50 người trong thư mục tạm, mở chương trình, kiểm tra mọi ô trên Dashboard và ô Tìm kiếm, tạo một
bản bàn giao và chứng minh không có ghi chú riêng, kiểm tra hai bản Giving statement và các lệnh
Hermes door (`python -m churchmgr.agent`). In PASS hoặc FAIL cho từng mục; trả về 0 chỉ khi tất cả
đều đạt. Không bao giờ mở dữ liệu thật của bạn. `--keep` giữ thư mục tạm; `--people N` đặt số
người (20 đến 1000).
