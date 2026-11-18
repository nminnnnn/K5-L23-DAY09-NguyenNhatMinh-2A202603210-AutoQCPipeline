"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    issues = []
    settings = cfg["label_format"]

    overflow_tol = settings["overflow_tol"]
    dup_box_iou = settings["dup_box_iou"]
    min_box_px = settings["min_box_px"]
    max_box_frac = settings["max_box_frac"]

    for label_path in ds.label_files():
        stem = label_path.stem
        previous_boxes = []
        image_size = ds.image_size(stem)

        for line_number, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except ValueError as exc:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_FORMAT",
                        image=stem,
                        line=line_number,
                        message=str(exc),
                    )
                )
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_CLASS_ID",
                        image=stem,
                        line=line_number,
                        message=f"ID lớp {class_id} nằm ngoài phạm vi hợp lệ",
                    )
                )
                continue

            if width <= 0 or height <= 0:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_ZERO",
                        image=stem,
                        line=line_number,
                        message="Chiều rộng hoặc chiều cao của box không dương",
                    )
                )
                continue

            box = (cx, cy, width, height)

            left = cx - width / 2
            right = cx + width / 2
            top = cy - height / 2
            bottom = cy + height / 2

            overflow = max(
                0.0,
                -left,
                -top,
                right - 1.0,
                bottom - 1.0,
            )

            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_OUT_OF_IMAGE",
                        image=stem,
                        line=line_number,
                        message=f"Box tràn ảnh {overflow:.6f}",
                        extra={"overflow": overflow},
                    )
                )

            is_duplicate = any(
                previous_class == class_id
                and iou_xywh(previous_box, box) > dup_box_iou
                for previous_class, previous_box in previous_boxes
            )

            if is_duplicate:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="DUP_BOX",
                        image=stem,
                        line=line_number,
                        message="Box trùng với một box cùng lớp trước đó",
                    )
                )

            if image_size is not None:
                image_width, image_height = image_size
                short_side_px = min(
                    width * image_width,
                    height * image_height,
                )

                if short_side_px < min_box_px:
                    issues.append(
                        Issue(
                            check="label_format",
                            severity=WARN,
                            code="BOX_TINY",
                            image=stem,
                            line=line_number,
                            message=f"Cạnh ngắn của box chỉ có {short_side_px:.2f}px",
                        )
                    )

            if width * height > max_box_frac:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_HUGE",
                        image=stem,
                        line=line_number,
                        message="Box chiếm diện tích quá lớn",
                    )
                )

            previous_boxes.append((class_id, box))

    return issues
