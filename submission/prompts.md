# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Nguyễn Thanh Thản | Codex | Phân tích cấu trúc lab, các loại lỗi và ràng buộc validator chỉ đọc delivery. | Không thể thay người review ảnh hay tự điền verdict. | Chỉ dùng AI cho validator/công cụ; verdict được lấy từ bảng review do người dùng cung cấp. |
| 2 | Đào Quang Tuấn, Nguyễn Đại | Codex | Viết validator lỗi luật và sinh candidate detection–panoptic bằng thư viện chuẩn. | Heuristic `instance_merge` ban đầu sinh quá nhiều candidate. | Chạy lô sạch 50 ảnh, siết điều kiện coverage pixel và IoU box; giữ review thủ công cho candidate. |
| 3 | Phan Thanh Hào | Codex | Tạo handover v2, trace, kiểm tra hash/lineage và báo cáo. | Không thể biết tên nhóm, MSHV, GitHub hay tự xác nhận khuôn mặt nếu chưa xem ảnh. | Thông tin thành viên do nhóm tự điền; kiểm tra trực quan ảnh `000000000885` trước khi nêu trong security.md. |
