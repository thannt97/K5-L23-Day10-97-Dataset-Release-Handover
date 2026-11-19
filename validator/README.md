# Validator của nhóm

Viết `validate.py` ở đây. Giao diện cố định:

```
python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

Chỉ đọc thư mục delivery được truyền vào; chỉ thư viện chuẩn; không mạng. Xem [GUIDE.md](../GUIDE.md) Pha 1–2 và [RULES.md](../RULES.md).

## Đầu ra hiện có

`validate.py` ghi `errors.json` theo dạng:

```json
{"errors": [{"type": "wrong_hash", "target": "000000000139"}]}
```

File này chỉ gồm lỗi luật có thể xác minh từ delivery. Khi truyền
`--candidates`, validator còn ghi:

```json
{"candidates": [{"image": "000000000139", "type": "bbox_drift", "detail": "..."}]}
```

Candidate là hàng đợi để người trong nhóm mở ảnh kiểm tra; không được chép trực
tiếp chúng sang `errors.json`. Với tín hiệu đổi lớp, validator dùng loại
`class_or_category_swap` vì ảnh mới xác định được detection hay panoptic bên
nào sai.
