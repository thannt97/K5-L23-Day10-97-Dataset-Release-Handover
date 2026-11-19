# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): `r3007: ≈1.0 / ≈0.3 / ≈0.7`; `r3008: ≈1.0 / — / ≈0.7`.
- Số ứng viên trên lô sạch (`--no-faults`): 17; hàng đợi trên seed luyện tập `r3007`: 96 candidate.
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): với `instance_merge`, hai detection box cùng lớp phải phủ mỗi box ≥35% segment, tổng phủ ≥75% và IoU hai box ≤0.20. Ngưỡng được điều chỉnh trên lô sạch để hàng đợi còn 17 ca, sau đó áp dụng nguyên vẹn cho seed luyện tập.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Báo toàn bộ candidate coi tín hiệu là lỗi sẽ tăng FP, làm precision giảm; F1 là trung bình điều hoà của precision và recall nên cũng giảm. Ví dụ, lô sạch vẫn có 17 candidate dù không có lỗi gài; đây là lệch tự nhiên giữa detection và panoptic. Vì vậy nhóm chỉ đưa 3 ca đã xem ảnh và xác nhận vào lỗi ngữ nghĩa, không đưa 92 dòng `needs_review` vào `errors.json`.

## 3. Quyết định và lineage
QC v1 là 14/250 = 5.6%, vượt ngưỡng 2%, nên quyết định HOLD. Lineage ghi `R-021: affected=True action=review_or_retrain`: model có thể đã học từ nhãn sai; thay dataset không tự sửa trọng số đã train nên run phải được xem lại hoặc train lại.

## 4. Hash chứng minh gì, không chứng minh gì?
SHA-256 chứng minh bytes của file trong manifest không bị đổi kể từ lúc lập manifest; nhờ đó kiểm được tính toàn vẹn và truy vết. Hash không chứng minh đối tượng trong ảnh được gán đúng lớp, box đúng vị trí hay quyết định review là đúng.

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
