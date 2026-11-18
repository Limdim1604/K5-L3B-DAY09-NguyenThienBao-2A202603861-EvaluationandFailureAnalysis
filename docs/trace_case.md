# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Trial C-002@11

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (item `E-002`). Đã replay riêng bằng CLI. Bổ sung `run_id` khi sinh report M4. |
| Triệu chứng | Ledger ghi 1 khoản hoàn 20.000đ, trong khi nhãn yêu cầu 0 khoản và 0đ. Reply #6 nói đã hoàn 20.000đ cho `O-202`. Grader Day 8 FAIL với `status resolved != denied`. |
| Bước sai đầu tiên | Event #3 `model_override`, payload `{"delay_days": 5}`. Agent dùng số ngày từ ticket để thay dữ kiện DB. |
| Vì sao là bước đầu tiên | #1 `handoff` chọn đúng claim, #2 `investigator` thấy đơn `O-202` và đọc đúng `delay_days: 2`. Sau bước ghi đè #3, quote #4 mới áp dụng `SHIP-LATE-03` và đề xuất 20.000đ. |
| Failure mode | [FM-03 · ticket_trust](failure_taxonomy.md) |
| Đối chứng | `fixed C-002@11` giữ 2 ngày từ DB, event #3 `quote` trả `amount_vnd: 0` và `reason: no_entitlement`. Ledger 0đ, trạng thái `denied`, grader Day 8 PASS. |
| Regression test | `test_c002_keeps_database_delay` trong `src/tests/test_lab9_graders.py` chạy cả hai shape trên cùng claim và seed. Assertion xác nhận `DbFactKept` báo lỗi trên `seeded_regression`. Trên `fixed`, grader cho qua, kết quả là `denied` và ledger ghi 0đ. |
| Chưa chắc chắn | Hai replay dùng một seed. Chúng xác định bước sai trong trial này nhưng chưa đo tần suất lỗi trên các seed hay claim khác. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
