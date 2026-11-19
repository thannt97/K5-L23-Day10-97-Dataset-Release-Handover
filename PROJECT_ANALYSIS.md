# Báo cáo phân tích project — Day 10 Dataset Release Handover

> Thời điểm rà soát: 19/11/2026. Báo cáo mô tả đúng trạng thái checkout hiện tại,
> không suy diễn số liệu chưa được sinh từ dữ liệu thực.

## 1. Mục tiêu và phạm vi

Project là bộ khung một lab nhóm (5–6 người, khoảng 4 giờ) về kiểm soát chất
lượng và bàn giao dataset. Nhóm phải phát hiện lỗi trong một lô 250 ảnh COCO có
hai biểu diễn nhãn: detection YOLO và panoptic; sau đó quyết định phát hành,
lập lineage và tạo release v2 không ghi đè lô gốc.

Các tiêu chí trọng tâm là:

1. Phát hiện lỗi luật có thể chứng minh từ file bàn giao.
2. Phát hiện lỗi ngữ nghĩa bằng đối chiếu hai nguồn nhãn, rồi xác nhận bằng mắt.
3. Giữ bằng chứng review, quyết định HOLD/Release, truy vết người và job.
4. Bàn giao v2 có manifest/hash có thể tái lập.

## 2. Kiến trúc repository

| Thành phần | Vai trò | Trạng thái |
|---|---|---|
| `scripts/download_public.py` | Tải COCO, chuyển annotation detection sang YOLO, tạo pool practice/calib/test | Có |
| `scripts/inject_release.py` | Sinh delivery, lỗi giả lập theo seed và ground truth riêng tư | Có |
| `validator/validate.py` | Validator lỗi luật và sinh ứng viên review | Có (chưa kiểm thử trên COCO thật) |
| `scripts/score_findings.py` | Tự đo F1 theo lỗi luật/lỗi ngữ nghĩa và truy vết | Có |
| `scripts/check_handover.py` | Kiểm 17 điều kiện nhất quán của release v2 | Có |
| `scripts/lineage.py` | Ghi event append-only và đánh giá ảnh hưởng run train | Có |
| `scripts/pack_release.py` | Đóng gói ZIP tái lập và tạo SHA-256 | Có |
| `submission/` | Bài làm được commit | Mới có mẫu |

`_private/` là ground truth do injector tạo ra; validator và bài nộp không được
đọc thư mục này. `runs/` và `data_source/` bị gitignore, còn artefact cần nộp
được sao chép sang `submission/`.

## 3. Luồng thực thi chuẩn

1. Chạy `python3 scripts/download_public.py` để tải pool practice 250 ảnh và
   pool calib 50 ảnh.
2. Chạy `python3 scripts/run_lab.py --seeds <seed>` để sinh lô luyện tập và
   một event training `R-021`.
3. Viết và chạy validator trên `runs/r<seed>/delivery`.
4. Chạy validator trên lô sạch tạo từ `inject_release.py --no-faults` để đo
   nhiễu tự nhiên của thuật toán đối chiếu.
5. Review từng ứng viên, ghi `confirmed`/`rejected` có lý do quan sát ảnh.
6. Gộp lỗi luật và lỗi đã xác nhận vào `errors.json`.
7. Ghi HOLD v1, truy vấn tác động lineage và tạo v2 ở `handover/`.
8. Tạo trace/security, đóng gói, chạy `check_handover.py` đến khi H1–H17 PASS.
9. Dùng `export_submission.py` để chép artefact sang `submission/`.

## 4. Các lỗi cần phát hiện

| Nhóm | Loại |
|---|---|
| Luật detection | `missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`, `scene_leak`, `guideline_mismatch` |
| Luật panoptic | `invalid_category_id`, `thing_overlap` |
| Ngữ nghĩa/review | `class_swap`, `bbox_drift`, `missing_box`, `category_swap`, `instance_merge` |

Đơn vị chấm là cặp `(type, target)`. Riêng `scene_leak` dùng `scene_id` làm
target, các lỗi khác dùng tên ảnh không có phần mở rộng. F1 phạt cả báo thừa
lẫn bỏ sót, do đó không được đưa tất cả ứng viên vào `errors.json`.

## 5. Yêu cầu tối thiểu của validator

Validator phải có giao diện:

```text
python3 validator/validate.py <delivery> --out <errors.json> [--candidates <candidates.json>]
```

Ràng buộc: chỉ thư viện chuẩn; chỉ đọc delivery truyền vào; không mạng; không
đọc `data_source/`, `_private/` hay annotation COCO gốc. Phần kiểm luật cần
đặc biệt lưu ý:

- SHA-256 phải tính trên bytes thật của file, không chỉ kiểm định dạng hash.
- `duplicate_box` cần cùng class, cùng kích thước và lệch tâm khoảng 1–2 px;
  chỉ dùng ngưỡng IoU sẽ gây dương tính giả.
- `guideline_mismatch` đối chiếu metadata với guideline theo `job_id` trong
  `jobs.csv`, không suy luận từ các ảnh khác.
- `thing_overlap` so pixel mask theo segment id RGB và so với area khai báo.

Phần ứng viên nên ghép class qua tên, không qua ID vì ID YOLO và category ID
COCO khác nhau. Pixel của segment nằm ngoài detection box là tín hiệu mạnh hơn
IoU bbox đơn thuần cho `bbox_drift`; một segment phủ hai box cùng lớp là tín
hiệu `instance_merge`. Kết luận cuối vẫn phải do người xem ảnh đưa ra.

## 6. Quy tắc bàn giao v2

Không sửa `delivery/` v1. Với lỗi detection hoặc thiếu ảnh, loại ảnh khỏi v2
và ghi đúng annotator/reviewer vào `rework_queue.csv`. Với `wrong_hash`,
`guideline_mismatch`, `scene_leak`, có thể sửa metadata/manifest/split tại v2
sau khi kiểm chứng. Lỗi chỉ thuộc panoptic không làm detection v2 sai, nên ảnh
được giữ lại và phải được thông báo trong README.

v2 bắt buộc có `images/`, `labels/`, `manifest.csv`, `label_summary.csv`,
`truyvet.csv`, `README.txt`, `rework_queue.csv` và file SHA-256 của ZIP.
`check_handover.py` xác nhận các điều kiện này qua H1–H17, nhưng PASS không
chứng minh nhãn ngữ nghĩa đúng.

## 7. Kiểm thử đã thực hiện

| Kiểm tra | Kết quả |
|---|---|
| `python3 -m compileall -q validator scripts tests` | Pass |
| `python3 -m unittest -q tests/test_validator.py` | 2 pass |
| Git worktree | Có thay đổi có chủ đích: validator, test, README validator và báo cáo |

Hai test fixture kiểm tra validator trên delivery tối thiểu và các lỗi
hash/class/bbox/guideline/scene leak. Sau đó đã tải pool practice/calib và chạy
đo thực tế như bảng bên dưới. Pool test vẫn chỉ dành cho giảng viên.

| Lô | F1 lỗi luật | F1 tổng | Ứng viên review |
|---|---:|---:|---:|
| `r3007` | ≈ 1.0 | ≈ 0.7 | 96 |
| `r3008` | ≈ 1.0 | ≈ 0.7 | 97 |
| `clean` (seed 5, không lỗi gài) | ≈ 1.0 | ≈ 1.0 | 17 |

F1 tổng vẫn thấp vì chưa có lỗi ngữ nghĩa nào được con người review/xác nhận;
đây là trạng thái đúng quy trình, không phải số liệu để điền là kết quả cuối.

## 8. Khoảng trống và rủi ro hiện tại

1. Lỗi ngữ nghĩa trong các candidate chưa được review bằng mắt nên chưa thể
   thêm vào `errors.json` hoặc khẳng định F1 cuối.
2. `submission/TEAM.md`, `submission/REPORT.md`, `submission/prompts.md` còn
   placeholder; chưa đáp ứng cấu trúc nộp bài.
3. Chưa có dữ liệu, run, review log, trace, security, lineage thực tế hoặc v2;
   không được ghi sẵn số liệu thay thế.
4. Dữ liệu tải khoảng 1 GB, là phụ thuộc mạng và dung lượng trước khi test tích
   hợp được thực hiện.
5. Review ngữ nghĩa phụ thuộc người xem ảnh. Ghi "có lỗi" chung chung không đủ;
   mỗi note phải nêu vật/box/segment quan sát được và dài tối thiểu 20 ký tự.

## 9. Kế hoạch hoàn thành ưu tiên

| Ưu tiên | Việc | Điều kiện hoàn tất |
|---:|---|---|
| P0 | Tải dữ liệu, chọn seed, khai báo thành viên | Delivery được sinh; TEAM.md đầy đủ |
| P1 | Kiểm thử/effect chỉnh validator lỗi luật | Hoàn tất: F1 luật ≈ 1.0 trên r3007, r3008 và clean |
| P2 | Sinh ứng viên cross-check và công cụ xem ảnh | Có candidates; baseline clean 17 ứng viên; 3 candidate đã được người review xác nhận |
| P3 | Review, chốt errors, HOLD và impact | Hoàn tất phần đã review: 14 lỗi; lineage có HOLD; `R-021` affected |
| P4 | Tạo v2, trace, security, packaging | Hoàn tất: H1–H17 PASS |
| P5 | Xuất submission và kiểm tra cuối | Không còn placeholder; artefact đúng cấu trúc |

## 10. Kết luận

Project có cấu trúc, tài liệu, script sinh dữ liệu, kiểm thử và guardrail rõ
ràng. Tuy nhiên checkout hiện tại mới là điểm xuất phát của học viên. Công việc
cần làm tiếp là hiện thực validator, tải dữ liệu để kiểm thử tích hợp, thực hiện
review có bằng chứng và tạo toàn bộ artefact bàn giao; không nên điền báo cáo
hoặc số liệu trước khi có output thật từ các bước đó.

## 11. Kết quả handover trên seed r3007

Đã tạo `lab250_68efac8c866e_v2` từ 11 lỗi luật và 3 lỗi `category_swap` do
người review xác nhận: 246 ảnh giữ lại, 4 ảnh lỗi detection chuyển vào rework
queue, 1,675 nhãn trong v2. Quyết định v1 là Hold (14/250 = 5.6%, vượt ngưỡng
2%); lineage cho thấy `R-021` cần review hoặc retrain.

`check_handover.py` hiện PASS toàn bộ H1–H17. `security.md` phân công bốn vai
trò và dùng ảnh `000000000885` đã kiểm tra trực quan làm ví dụ khuôn mặt; kết
luận là Hold và báo người phụ trách. Sau mỗi thay đổi v2 cần chạy lại
`pack_release.py`.
