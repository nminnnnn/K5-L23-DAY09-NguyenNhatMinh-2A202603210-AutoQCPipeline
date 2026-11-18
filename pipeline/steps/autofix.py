"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    fixes = []
    # Sửa danh sách tên lớp trong data.yaml.
    has_bad_class_name = any(
        issue.severity == ERROR
        and issue.code == "BAD_CLASS_NAME"
        for issue in issues
    )

    if has_bad_class_name and ds.yaml_path.exists():
        yaml_data = yaml.safe_load(
            ds.yaml_path.read_text(encoding="utf-8")
        ) or {}

        before_names = yaml_data.get("names")
        correct_names = list(cfg["classes"])

        # Chỉ sửa khi nội dung hiện tại thực sự khác.
        if before_names != correct_names:
            yaml_data["names"] = correct_names

            ds.yaml_path.write_text(
                yaml.safe_dump(
                    yaml_data,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )

            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": str(before_names),
                "after": str(correct_names),
            })

    # Xóa ảnh và nhãn không được phép đi tiếp trong pipeline.
    remove_image_codes = {
        "LEAK_TEST",
        "CORRUPT_IMAGE",
        "BAD_SIZE",
    }

    removed_images = {
        issue.image
        for issue in issues
        if (
            issue.severity == ERROR
            and (
                issue.code.startswith("DUP_IMAGE_")
                or issue.code in remove_image_codes
            )
        )
    }

    for stem in sorted(removed_images):
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)

        image_existed = image_path is not None and image_path.exists()
        label_existed = label_path.exists()

        if image_existed:
            image_path.unlink()

        if label_existed:
            label_path.unlink()

        if image_existed or label_existed:
            fixes.append({
                "image": stem,
                "line": None,
                "action": "remove_image",
                "before": "ảnh và/hoặc nhãn tồn tại",
                "after": "đã xóa khỏi working dataset",
            })

    # Không tự tạo nhãn khi ảnh chưa có file label; chuyển cho người gán.
    needs_label_images = {
        issue.image
        for issue in issues
        if (
            issue.severity == ERROR
            and issue.code == "MISSING_LABEL_FILE"
            and issue.image not in removed_images
        )
    }

    for stem in sorted(needs_label_images):
        label_path = ds.label_path(stem)

        if not label_path.exists():
            fixes.append({
                "image": stem,
                "line": None,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    drop_codes = {
        "BAD_FORMAT",
        "BAD_CLASS_ID",
        "BOX_ZERO",
        "DUP_BOX",
    }

    line_actions = defaultdict(lambda: defaultdict(set))

    # Gom các thao tác theo ảnh và số dòng gốc.
    for issue in issues:
        if issue.severity != ERROR:
            continue

        # Ảnh đã bị xóa thì không tiếp tục sửa các dòng nhãn của ảnh đó.
        if issue.image in removed_images:
            continue

        if (
            issue.code in drop_codes
            or issue.code == "BOX_OUT_OF_IMAGE"
        ) and issue.line is not None:
            line_actions[issue.image][issue.line].add(issue.code)

    for stem in sorted(line_actions):
        label_path = ds.label_path(stem)

        if not label_path.exists():
            continue

        original_lines = label_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        new_lines = []
        file_changed = False

        for line_number, original in enumerate(original_lines, start=1):
            codes = line_actions[stem].get(line_number, set())

            # Xóa dòng được ưu tiên hơn clip.
            if codes & drop_codes:
                fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "drop_line",
                    "before": original,
                    "after": "",
                })
                file_changed = True
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    class_id, cx, cy, width, height = parse_yolo_line(original)
                except ValueError:
                    # Phòng trường hợp issue không còn khớp nội dung file.
                    new_lines.append(original)
                    continue

                # Chuyển YOLO xywh thành bốn mép.
                x1 = cx - width / 2
                y1 = cy - height / 2
                x2 = cx + width / 2
                y2 = cy + height / 2

                # Cắt các mép về phạm vi ảnh.
                x1 = max(0.0, x1)
                y1 = max(0.0, y1)
                x2 = min(1.0, x2)
                y2 = min(1.0, y2)

                # Box nằm hoàn toàn ngoài ảnh, không còn diện tích.
                if x2 <= x1 or y2 <= y1:
                    fixes.append({
                        "image": stem,
                        "line": line_number,
                        "action": "drop_line",
                        "before": original,
                        "after": "",
                    })
                    file_changed = True
                    continue

                # Chuyển bốn mép trở lại định dạng YOLO.
                new_cx = (x1 + x2) / 2
                new_cy = (y1 + y2) / 2
                new_width = x2 - x1
                new_height = y2 - y1

                clipped_line = (
                    f"{class_id} "
                    f"{new_cx:.6g} "
                    f"{new_cy:.6g} "
                    f"{new_width:.6g} "
                    f"{new_height:.6g}"
                )

                if clipped_line != original:
                    fixes.append({
                        "image": stem,
                        "line": line_number,
                        "action": "clip_box",
                        "before": original,
                        "after": clipped_line,
                    })
                    file_changed = True

                new_lines.append(clipped_line)
                continue

            # Dòng không có lỗi cần sửa.
            new_lines.append(original)

        if file_changed:
            content = "\n".join(new_lines)

            if new_lines:
                content += "\n"

            label_path.write_text(content, encoding="utf-8")

    return fixes
