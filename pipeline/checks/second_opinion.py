"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    settings = cfg["second_opinion"]
    conf_threshold = settings["conf"]
    min_area_px = settings["min_area_px"]
    fp_conf = settings["fp_conf"]
    iou_missing = settings["iou_missing"]
    iou_match = settings["iou_match"]
    iou_loose = settings["iou_loose"]

    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    issues = []

    # image_files() được sắp xếp theo tên, giúp kết quả luôn deterministic.
    for image_path in ds.image_files():
        stem = image_path.stem

        if stem not in preds:
            continue

        label_lines = ds.read_label_lines(stem)
        if label_lines is None:
            continue

        image_size = ds.image_size(stem)
        if image_size is None:
            continue

        image_width, image_height = image_size
        labels = ds.valid_boxes(stem)
        image_predictions = preds[stem]

        # Lượt 1: model nhìn thấy vật nhưng nhãn có thể thiếu, sai lớp
        # hoặc có box quá lỏng. Lượt này lọc cả confidence lẫn diện tích.
        filtered_predictions = []
        for prediction in image_predictions:
            class_id, confidence, cx, cy, width, height = prediction
            area_px = width * image_width * height * image_height

            if confidence >= conf_threshold and area_px >= min_area_px:
                filtered_predictions.append(prediction)

        for prediction in filtered_predictions:
            pred_class, confidence, cx, cy, width, height = prediction
            pred_box = (cx, cy, width, height)

            candidates = []
            for label in labels:
                label_class, lx, ly, lw, lh = label
                overlap = iou_xywh(pred_box, (lx, ly, lw, lh))
                if overlap >= iou_missing:
                    candidates.append((label_class, overlap))

            if not candidates:
                issues.append(
                    Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_MISSING",
                        image=stem,
                        message="Model thấy vật nhưng không có box nhãn tương ứng",
                        extra={"conf": confidence},
                    )
                )
                continue

            same_class_ious = [
                overlap
                for label_class, overlap in candidates
                if label_class == pred_class
            ]

            if same_class_ious:
                best_same_class_iou = max(same_class_ious)
                if best_same_class_iou < iou_loose:
                    issues.append(
                        Issue(
                            check="second_opinion",
                            severity=WARN,
                            code="POSSIBLE_LOOSE_BOX",
                            image=stem,
                            message="Nhãn đúng lớp nhưng box có thể bị lỏng hoặc lệch",
                            extra={
                                "conf": confidence,
                                "iou": best_same_class_iou,
                            },
                        )
                    )
                continue

            best_other_class_iou = max(overlap for _, overlap in candidates)
            if best_other_class_iou >= iou_match:
                issues.append(
                    Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_WRONG_CLASS",
                        image=stem,
                        message="Model và nhãn có thể không thống nhất về lớp",
                        extra={
                            "conf": confidence,
                            "iou": best_other_class_iou,
                        },
                    )
                )

        # Lượt 2: mỗi label phải khớp ít nhất một prediction đủ fp_conf.
        # Không lọc diện tích ở lượt này: prediction nhỏ vẫn có thể xác nhận
        # rằng một box nhãn không phải false positive.
        fp_predictions = []
        for prediction in image_predictions:
            _, confidence, cx, cy, width, height = prediction
            if confidence >= fp_conf:
                fp_predictions.append((cx, cy, width, height))

        valid_labels_with_lines = []
        for line_number, text in label_lines:
            try:
                label = parse_yolo_line(text)
            except ValueError:
                continue

            class_id, cx, cy, width, height = label
            if not 0 <= class_id < len(ds.classes):
                continue
            if width <= 0 or height <= 0:
                continue

            valid_labels_with_lines.append(
                (line_number, (cx, cy, width, height))
            )

        for line_number, label_box in valid_labels_with_lines:
            best_iou = max(
                (iou_xywh(label_box, pred_box) for pred_box in fp_predictions),
                default=0.0,
            )

            if best_iou < iou_missing:
                issues.append(
                    Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_FALSE_POS",
                        image=stem,
                        line=line_number,
                        message="Box nhãn không khớp với prediction nào của model",
                        extra={"iou": best_iou},
                    )
                )

    return issues
