# Nộp bài — Nguyễn Nhật Minh, 2A202603210

## Repository

- Repository: [nminnnnn/K5-L23-DAY09-NguyenNhatMinh-2A202603210-AutoQCPipeline](https://github.com/nminnnnn/K5-L23-DAY09-NguyenNhatMinh-2A202603210-AutoQCPipeline)
- Nhánh nộp bài: `main`
- Tiêu đề `README.md` đã có đầy đủ họ tên và MSHV.

## Trạng thái hoàn thành

- [x] Hoàn thành bốn module `label_format`, `second_opinion`, `autofix` và `gate`.
- [x] Toàn bộ **79 unit test và test e2e đều pass**.
- [x] Calibrate hai ngưỡng: `duplicates.phash_dist=16` và `second_opinion.conf=0.8`.
- [x] Chạy pipeline end-to-end và sinh đầy đủ báo cáo, audit log, review queue cùng dataset export.
- [x] Kết luận cuối: **Release** — 0 lỗi bắt buộc; 13/193 ảnh còn cảnh báo (6,74%), thấp hơn ngưỡng 10%.
- [x] Chứng minh gate hoạt động với review budget bằng 0: **Rework**, exit code 20 và không export dataset.
- [x] Hoàn thành bonus CVAT **+2** trên 5 ảnh: lọc `width < 20`, ghi nhận 19 box và đối chiếu với `BOX_TINY`.
- [x] Không commit `work/` hoặc file trọng số `*.pt`.

Phần train so sánh raw và clean là hạng mục tùy chọn, chấm riêng 15 điểm và không nằm trong phạm vi phiên bản nộp này. Trạng thái này được khai báo trung thực trong báo cáo.

## Bằng chứng chính

| Nội dung | Bằng chứng |
|---|---|
| Báo cáo cuối | [`submission/REPORT.md`](submission/REPORT.md) |
| Calibration | [`submission/calibration/`](submission/calibration/) |
| Báo cáo pipeline | [`submission/reports/`](submission/reports/) |
| Dataset sạch và manifest | [`submission/export/clean_v1/`](submission/export/clean_v1/) |
| Bonus CVAT +2 | [`submission/evidence/cvat_width_lt_20.png`](submission/evidence/cvat_width_lt_20.png) |

## Kiểm tra trước khi nộp

Trên Windows PowerShell, chạy:

```powershell
$env:PYTHONUTF8 = "1"
python -m pytest -q
python scripts\check_submission.py --no-train
```

Link repository được nộp trên LMS theo kênh giảng viên quy định.
