# Judge audit

Chạy từ `src/` bằng Python trong môi trường lab.

```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
```

`FAIL` là lớp dương. TP là lỗi phát hiện đúng, FP là báo nhầm lỗi, FN là lỗi bị bỏ sót và TN là câu đạt được cho qua. Sàn calibration là κ ≥ 0.6, precision ≥ 0.8 và recall ≥ 0.7.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Tỉ lệ FAIL replay → hiệu chỉnh Rogan–Gladen | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| `tone_ok` | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | 28% → 30% | Đạt cả ba sàn (exit 0). Có thể dùng để chấm giọng điệu trong phạm vi đã kiểm. |
| `helpful` | 100 | 9 / 0 / 21 / 70 | 0.375 | 1.000 | 0.300 | 9% → 30% | Trượt κ và recall (exit 1). Loại khỏi gate. |

## Audit thủ công các bất đồng

| Case | Judge | Người | Ai đúng? | Bằng chứng và cách sửa rubric |
|---|---|---|---|---|
| Tone H-008 | PASS | FAIL | Người | Cách xưng “em” và dùng “nha” tạo giọng quá suồng sã cho phản hồi chính thức. Thêm ví dụ FAIL cho kiểu xưng hô này và ví dụ PASS dùng “LogiX” với “anh/chị”. |
| Tone H-017 | PASS | FAIL | Người | “Bạn ơi” và “nha” lệch chuẩn xưng hô của kênh khiếu nại. Quy định rõ cách gọi khách phù hợp cho kênh này, kể cả khi câu mở đầu có “Dạ”. |
| Tone H-029 | PASS | FAIL | Người | Câu “không cần nhắn thêm” mang tính ra lệnh. Yêu cầu đọc trọn phản hồi và đánh FAIL nếu có mệnh lệnh gạt khách đi. |
| Tone H-042 | FAIL | PASS | Người | Câu xác nhận khoản hoàn và thời gian, với cách nói lịch sự. Cho phép câu xác nhận ngắn sau khi xử lý xong, kể cả khi thiếu lời xin lỗi. |
| Tone H-051 | FAIL | PASS | Người | “Refund” là thuật ngữ CS LogiX cho phép và câu có cách xưng hô lịch sự. Thêm danh sách thuật ngữ được phép vào rubric. |
| Tone H-070 | PASS | FAIL | Người | Emoji cười ở cuối câu lệch ngữ cảnh khiếu nại. Thêm ví dụ FAIL dùng emoji cười khi phản hồi vấn đề hoàn tiền. |
| Helpful HL-015 | PASS | FAIL | Người | Reply báo 55.000đ, ghi chú ledger là 40.000đ. Đối chiếu bằng code trước khi chấm tính hữu ích và đánh FAIL khi báo sai tiền. |
| Helpful HL-043 | PASS | FAIL | Người | Hai lời xin lỗi bao quanh thông báo 35.000đ, trong khi ghi chú ledger là 20.000đ. Chấm độ đúng của số tiền độc lập với giọng điệu và số lời xin lỗi. |
| Helpful HL-047 | PASS | FAIL | Người | “Ok bạn” lệch chuẩn xưng hô và “xử lý rồi” mơ hồ về kết quả. Yêu cầu nêu trạng thái cụ thể của yêu cầu và dùng chuẩn xưng hô của LogiX. |

Ghi chú của CSV đề nghị kiểm tra lại nhãn người ở H-081 vì annotator có thể đã đọc nhầm ticket. Cần đối chiếu ticket gốc và lấy nhãn thứ hai trước khi sửa nhãn. Bảng calibration sử dụng nguyên nhãn công khai.

## Quyết định dùng judge

`helpful` có precision 1.000 vì cả 9 câu bị judge đánh FAIL đều là lỗi theo nhãn người. Judge vẫn cho qua 21/30 câu FAIL, gồm 18 câu sai tiền và 3 câu sai xưng hô. Loại judge này khỏi gate và dùng code đối chiếu tiền hoàn với ledger. `tone_ok` đạt sàn cho tiêu chí giọng điệu.

Mức 30% sau hiệu chỉnh dùng độ nhạy và độ đặc hiệu ước lượng trên chính CSV replay. Trước khi dùng rubric đã sửa, cần hiệu chỉnh lại trên tập held-out có nhãn người mới và đo riêng các lỗi sai tiền, sai xưng hô và giọng ra lệnh.
