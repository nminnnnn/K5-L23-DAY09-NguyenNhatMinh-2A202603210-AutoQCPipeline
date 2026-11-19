# Báo cáo Day 09 — Nguyễn Nhật Minh, 2A202603210

## 1. Kết luận trước

Pipeline kết luận **Release**. Từ 224 ảnh đầu vào, bước intake giữ lại và xuất 193 ảnh vào `clean_v1`, loại 31 ảnh không đạt yêu cầu. Sau autofix và duyệt mô phỏng 80/80 ảnh, không còn lỗi bắt buộc; còn 13/193 ảnh có cảnh báo, tương đương 6,74%, thấp hơn ngưỡng Hold 10%.

## 2. Lỗi và phân việc

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| `BAD_CLASS_ID` | 6 lỗi/6 ảnh | Máy | ID lớp sai chắc chắn, máy xóa dòng lỗi. |
| `BAD_CLASS_NAME` | 2 lỗi/1 `data.yaml` | Máy | Đồng bộ `names` với `cfg["classes"]`. |
| `BAD_FORMAT` | 3 dòng/3 ảnh | Máy | Dòng không parse được nên được loại an toàn. |
| `BAD_SIZE` | 3 ảnh | Máy | Ảnh không đạt kích thước tối thiểu bị loại. |
| `BOX_HUGE` | 3 cảnh báo/3 ảnh | Người | Box lớn có thể đúng hoặc sai tùy nội dung ảnh. |
| `BOX_OUT_OF_IMAGE` | 8 dòng/8 ảnh | Máy | Clip box về phạm vi `[0,1]`. |
| `BOX_TINY` | 6 box/4 ảnh | Người | Vật thể nhỏ có thể hợp lệ nên máy chỉ cảnh báo. |
| `BOX_ZERO` | 4 dòng/4 ảnh | Máy | Box không có diện tích không thể là nhãn hợp lệ. |
| `CLASS_RARE` | 4 cảnh báo cấp dataset | Người | Cần xem phân bố lớp và mục tiêu dự án. |
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Ảnh không đọc được nên phải loại. |
| `DUP_BOX` | 7 dòng/7 ảnh | Máy | Box cùng lớp có IoU quá cao nên dòng sau bị loại. |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Ảnh trùng byte bị loại để tránh lặp dữ liệu. |
| `DUP_IMAGE_NEAR` | 7 ảnh | Máy | Ảnh gần trùng theo pHash bị loại. |
| `EMPTY_LABEL` | 11 ảnh | Người | File rỗng có thể là ảnh nền thật hoặc nhãn bị thiếu. |
| `LEAK_TEST` | 11 ảnh | Máy | Ảnh trùng tập tham chiếu bị loại để tránh rò rỉ. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Máy không được bịa nhãn; ảnh được chuyển cho người gán. |
| `POSSIBLE_FALSE_POS` | 24 cảnh báo/23 ảnh | Người | Model chỉ đưa ý kiến thứ hai và có thể sai. |
| `POSSIBLE_LOOSE_BOX` | 11 cảnh báo/11 ảnh | Người | Cần nhìn ảnh để quyết định box có lỏng hay không. |
| `POSSIBLE_MISSING` | 32 cảnh báo/32 ảnh | Người | Cần xác nhận model có phát hiện đúng vật thể bị thiếu. |
| `POSSIBLE_WRONG_CLASS` | 13 cảnh báo/13 ảnh | Người | Bất đồng model–nhãn không đủ để máy tự đổi lớp. |

Hàng đợi gồm 98 ảnh và được sắp theo tổng trọng số rủi ro. `NEEDS_LABEL` có trọng số 10 nên sáu ảnh thiếu file nhãn nằm gần đầu hàng; `POSSIBLE_WRONG_CLASS` có trọng số 3, còn `POSSIBLE_MISSING` và `POSSIBLE_FALSE_POS` có trọng số 2. Ảnh có nhiều mã lỗi được cộng điểm, ví dụ `img_0020` có priority 11,524. Với ngân sách 80 ảnh, người duyệt được 80/98 ảnh; trong đó 67 ảnh có ít nhất một cảnh báo ngữ nghĩa. Cụ thể có 32 ảnh `POSSIBLE_MISSING`, 20 ảnh `POSSIBLE_FALSE_POS`, 13 ảnh `POSSIBLE_WRONG_CLASS` và 11 ảnh `POSSIBLE_LOOSE_BOX`; các nhóm có thể chồng lặp.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do và đánh đổi |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | 16 | Near duplicate: `1,00/0,50 → 1,00/0,83`; exact duplicate giữ `1,00/1,00` | Mức 16 bắt 5/6 near-duplicate mà chưa tạo false positive trên calib. Mức 20 làm recall exact duplicate giảm còn 0,33. |
| `second_opinion.conf` | 0,25 | 0,8 | Wrong class: `0,56/0,83 → 1,00/0,83`; missing: `0,50/1,00 → 0,67/0,75` | Giảm báo động giả và tải duyệt; đánh đổi là recall missing giảm và loose-box vẫn yếu. |

Calibration có thể đánh lừa vì tập calib chỉ có 39 ảnh, trong đó chỉ sáu near-duplicate, nên không đại diện đầy đủ cho 224 ảnh raw. Ngưỡng pHash 16 đạt F1 0,91 trên calib nhưng khi chạy raw đã đánh dấu 8 exact duplicate và 7 near-duplicate, tổng cộng 15 ảnh; vì vậy vẫn cần mở kiểm tra một số cặp trước khi áp dụng cho dự án khác. Tương tự, `second_opinion.conf=0,8` cải thiện precision nhưng bỏ sót nhiều box lỏng: recall `POSSIBLE_LOOSE_BOX` chỉ còn 0,20.

## 4. Cửa chặn và điều pipeline không bắt được

### Kiểm chứng cửa chặn

Tôi chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`. Pipeline nhận 193/224 ảnh và loại 31 ảnh ở intake. Trước autofix có 36 lỗi bắt buộc và 104 cảnh báo; máy thực hiện 35 thay đổi nhưng vẫn còn 6 lỗi bắt buộc cùng hàng đợi 98 ảnh. Vì ngân sách duyệt bằng 0, không có ảnh nào được người xử lý. Gate kết luận **Rework**, trả mã thoát **20** và không tạo `work/exp_nb/clean_v1`. Kết quả này chứng minh lỗi severity `ERROR` thực sự chặn việc phát hành dataset.

### Điểm mù quan sát thủ công

- `img_0002.jpg`: một vật thể không phải người bị gán nhãn lớp `person`.
- `img_0005.jpg`: một vật thể không phải người bị gán nhãn lớp `person`.
- `img_0007.jpg`: ảnh có đối tượng `car` nhưng thiếu box nhãn tương ứng.

Ba ảnh trên không xuất hiện trong `02_error_list_v1`, hàng đợi duyệt hay danh sách lỗi cuối. Kiểm tra cú pháp không thể nhận biết nội dung thật, còn model second opinion có thể cùng bỏ sót hoặc cùng phân loại sai với nhãn. Vì vậy Release không có nghĩa mọi nhãn đều đúng tuyệt đối; vẫn cần lấy mẫu QC thủ công.

## 5. Train: raw vs clean

**Chưa chạy.** Tôi ưu tiên hoàn thành và kiểm chứng phần pipeline lõi trước; vì vậy chưa đưa ra kết luận raw hay clean cho chất lượng model tốt hơn. Cần chạy cùng model, epoch, tập test và ít nhất hai seed cho mỗi biến thể trước khi kết luận.

## 6. Quyết định và ghi chú AI

Quyết định cuối là **Release** vì không còn lỗi bắt buộc và tỷ lệ ảnh còn cảnh báo là 13/193 = 6,74%, thấp hơn ngưỡng Hold 10%. Tuy nhiên Release chỉ có nghĩa lô dữ liệu đạt gate hiện tại, không bảo đảm mọi nhãn đều đúng. Ba lỗi quan sát thủ công ở `img_0002`, `img_0005` và `img_0007` cho thấy vẫn cần lấy mẫu QC thủ công sau phát hành.

- **Prompt AI chính:** yêu cầu giải thích và triển khai bốn module `label_format`, `gate`, `autofix`, `second_opinion` theo docstring, dùng ngưỡng từ cấu hình và xử lý các ca biên trong unit test.
- **Cách kiểm code AI:** chạy test riêng sau từng chức năng, sau đó chạy toàn bộ 79 test, kiểm tra audit log, calibration, pipeline e2e và trực quan hóa nhãn trên ảnh.
- **Một lần AI sai:** AI ban đầu giả định terminal đang dùng đúng `.venv`, trong khi `python` thực tế trỏ tới môi trường cũ tại `D:\Vinuni\.venv`, dẫn đến `ModuleNotFoundError: PIL`. Tôi kiểm tra `sys.executable`, chuyển sang `.venv` trong repo và chạy lại test.

### 6(b). Bonus CVAT — lọc box nhỏ

Tôi import nhãn YOLO 1.1 của năm ảnh vào CVAT và áp dụng bộ lọc `width < 20`. CVAT tìm được tổng cộng **19 box**: `img_0026.jpg` có 6 box, `img_0030.jpg` có 4 box, `img_0051.jpg` có 3 box, `img_0069.jpg` có 2 box và `img_0161.jpg` có 4 box.

Pipeline báo **6 `BOX_TINY` trên 4 ảnh**: một box ở `img_0026`, một box ở `img_0051`, một box ở `img_0069` và ba box ở `img_0161`; `img_0030` không có trong danh sách `BOX_TINY` ban đầu. CVAT tìm nhiều box hơn vì bộ lọc chỉ kiểm tra chiều rộng nhỏ hơn 20 px, trong khi pipeline dùng ngưỡng chặt hơn: cạnh ngắn nhất của box nhỏ hơn 12 px. Vì hai quy tắc không hoàn toàn giống nhau, CVAT phù hợp để mở rộng tập ứng viên cho người gán nhãn xem lại, chứ 19 box không đồng nghĩa với 19 lỗi chắc chắn.

Thuộc tính `can_review=true` được người gán dùng để đánh dấu một box khó hoặc chưa chắc chắn, cần người thứ hai kiểm tra. Trong pipeline, thông tin tương tự được biểu diễn bằng issue mức `WARN` và đưa ảnh vào `05_review_queue.csv` để ưu tiên duyệt thủ công.

Ảnh bằng chứng: [`evidence/cvat_width_lt_20.png`](evidence/cvat_width_lt_20.png).
