# Bảo mật khi làm việc — r3007

## 1. Phân công 4 người và ca USB: hết giờ, muốn chép lô về nhà làm tiếp

Nhóm chia việc theo nguyên tắc quyền tối thiểu: Thành viên 1 phụ trách điều phối,
quyết định Hold/Release và phê duyệt cuối; Thành viên 2 chạy validator, quản lý
manifest/hash; Thành viên 3 review ảnh và ghi review log; Thành viên 4 lập
handover, lineage và kiểm tra đóng gói. Hết giờ, không ai chép delivery, ảnh,
mask hay nhãn sang USB, email cá nhân hoặc tài khoản đám mây cá nhân. Các cách đó
đều tạo bản sao ngoài vùng kiểm soát, không có audit log và có thể làm lộ ảnh có
người. Nếu cần làm tiếp, Thành viên 1 xin gia hạn/quyền truy cập trên môi trường
được phê duyệt; Thành viên 4 chỉ bàn giao link/thư mục được quản trị, còn mỗi
người đăng nhập bằng tài khoản của chính mình.

## 2. Năm việc: được hay không

- Mở job được giao trên máy công ty: được, nếu đăng nhập cá nhân, dùng phạm vi
  job đã cấp và khóa màn hình khi rời máy.
- Chụp màn hình gửi người quen: không được, vì ảnh và nhãn có thể là dữ liệu dự
  án; người quen không có quyền truy cập hay nghĩa vụ bảo mật.
- Chép lô ra USB: không được, trừ khi USB mã hóa và quy trình của tổ chức cho
  phép bằng văn bản; lô r3007 không có phê duyệt đó.
- Dán nhãn thật lên chatbot công khai: không được đối với dữ liệu dự án thật;
  cần dùng công cụ nội bộ đã được duyệt hoặc mô tả đã khử định danh. Với lab
  COCO công khai, mọi lần dùng AI vẫn phải ghi vào `prompts.md`.
- Đưa tài khoản CVAT cho đồng nghiệp: không được; cần mời đồng nghiệp bằng tài
  khoản riêng, vai trò tối thiểu và ghi nhận được lịch sử thao tác.

## 3. Ca khuôn mặt: phát hiện mặt người rõ trong lô

Trong ảnh `000000000885` có khuôn mặt người chơi quần vợt nhìn rõ. Trạng thái
của lô là **Hold** và Thành viên 1 phải báo người phụ trách dữ liệu/bảo mật cùng
quản trị CVAT để xác nhận yêu cầu làm mờ, phạm vi ảnh bị ảnh hưởng và quy trình
gán lại. Nhóm không tự làm mờ hoặc xoá ảnh: thay đổi tự phát sẽ phá manifest,
hash, truy vết và có thể làm hỏng bằng chứng. Sau khi có chỉ dẫn chính thức,
Thành viên 3 review ảnh cần xử lý, Thành viên 2 kiểm hash của bản mới, và Thành
viên 4 tạo release v2 mới có lineage thay vì ghi đè bản đang được giữ lại.
