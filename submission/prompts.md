# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Nhóm | Codex | Phân tích cấu trúc lab, các loại lỗi và ràng buộc validator chỉ đọc delivery. | Không thể thay người review ảnh hay tự điền verdict. | Chỉ dùng AI cho validator/công cụ; verdict được lấy từ bảng review do người dùng cung cấp. |
| 2 | Nhóm | Codex | Viết validator lỗi luật và sinh candidate detection–panoptic bằng thư viện chuẩn. | Heuristic `instance_merge` ban đầu sinh quá nhiều candidate. | Chạy lô sạch 50 ảnh, siết điều kiện coverage pixel và IoU box; giữ review thủ công cho candidate. |
