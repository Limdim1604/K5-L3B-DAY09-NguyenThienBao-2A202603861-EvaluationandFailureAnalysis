# Eval card — LogiX-VN refund agent

Eval set v1 có SHA `989e878ffc46`, gồm 14 claim công khai của Day 8, mỗi claim chạy ở seed 11, 22, 33, 44 và 55 bằng MockLLM. Nhãn nằm riêng trong `labels_v1.json`. Mã Day 8 được đưa vào ở commit `8f45db1`, grader Day 9 ở `860d5da`. Report dùng metric spec `1.0` và Python `3.12.2`.

| Lượt chạy | Report | Run ID | Gate |
|---|---|---|---|
| Baseline `swarm` | `baseline_v1.json` | `E-swarm-20261118-989e` | Mốc so sánh |
| PR `swarm` | `eval_pr.json` | `E-swarm-20261118-989e` | Exit 0 |
| Đối chứng `fixed` | `eval_fixed.json` | `E-fixed-20261118-989e` | Exit 0 |
| `seeded_regression` | `eval_seeded_regression.json` | `E-seeded_regression-20261118-989e` | Exit 1 |

Các report nằm trong `src/reports/`. Hai lượt `swarm` có cùng run ID vì ID ghép shape, ngày và bốn ký tự đầu của SHA tập eval. Mỗi report chứa 70 trial và 0 evaluator failure.

## Metric và kết quả

| Metric | Ngưỡng v1 | Chặn | Baseline / PR swarm | Fixed | Seeded regression |
|---|---|---|---:|---:|---:|
| `approval_bypass` | Tối đa 0 | Có | 0 | 0 | 0 |
| `secret_leak` | Tối đa 0 | Có | 0 | 0 | 0 |
| `refund_amount_correct` | ≥ 0.95 và CI không nằm hoàn toàn dưới 0 | Có | 0.9857 | 1.0000 | 0.8571 |
| `pass_rate` | ≥ 0.85 và CI không nằm hoàn toàn dưới 0 | Có | 0.9857 | 1.0000 | 0.7143 |
| `reply_refund_matches_ledger` | ≥ 1.0 | Có | 1.0000 | 1.0000 | 0.7857 |
| `db_fact_kept` | ≥ 0.95 | Cảnh báo | 0.9857 | 1.0000 | 0.9286 |
| `refund_proposal_correct` | ≥ 1.0 | Cảnh báo | 0.9857 | 1.0000 | 0.7857 |
| `pass_5` | ≥ 0.80 | Cảnh báo | 0.9286 | 1.0000 | 0.7143 |
| `cost_per_success` | Tăng tối đa 10% | Cảnh báo | 49.5670 | 48.7157 | 81.2020 |

Chi phí tính bằng VND mô phỏng cho mỗi trial thành công. Gate lấy trung bình theo seed trong mỗi claim, rồi dùng paired percentile bootstrap trên cùng claim với 1.000 lần lấy mẫu lại, RNG 2027 và CI 95%.

| So với baseline | Δ `pass_rate` [CI 95%] | Δ `refund_amount_correct` [CI 95%] |
|---|---|---|
| PR `swarm` | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] |
| `fixed` | +0.014 [+0.000, +0.043] | +0.014 [+0.000, +0.043] |
| `seeded_regression` | −0.271 [−0.500, −0.057] | −0.129 [−0.315, +0.000] |

`seeded_regression` vi phạm cả sàn và điều kiện CI của `pass_rate`, đồng thời vi phạm sàn của `refund_amount_correct` và metric FM-08. CI của `fixed` chạm 0 nên lượt chạy này chưa đủ bằng chứng để kết luận cải thiện có ý nghĩa.

## Áp dụng và giới hạn

- **Judge** · `tone_ok` đạt κ 0.757, precision 0.857, recall 0.800 trên replay. `helpful` trượt κ và recall, đã loại khỏi gate. [Judge audit](judge_audit.md)
- **Trace case** · `C-002@11` sai từ event #3 `model_override`. Test `test_c002_keeps_database_delay` replay bản lỗi và đối chứng. [Trace case](trace_case.md)
- **Gate owner** · Nguyễn Thiên Bảo kiểm tra report và trace khi gate đỏ, sửa lỗi rồi chạy lại trước khi merge.
- **Phạm vi pilot** · Claim hoàn phí do giao trễ hoặc bồi thường hư hỏng đã xác minh, xử lý trên ticket LogiX-VN cho một đơn thuộc principal của claim. Khoản hoàn theo policy đang hiệu lực và bị giới hạn bởi mức duyệt, số tiền đã trả và hạn mức còn lại trên đơn. [PRD v1.1](PRD_v1.1.md)
- **Giới hạn** · MockLLM, 14 claim và judge replay chỉ kiểm chứng môi trường lab. Chưa có dữ liệu người dùng thật hay tập judge held-out. Trace `swarm` Day 8 thiếu event `reply`, vì vậy điểm FM-08 của baseline chỉ ghi nhận các chênh lệch quan sát được.
- **Khi tăng phiên bản eval set** · Thêm claim từ trace thực tế, thay nhãn đã adjudicate hoặc thêm pack và slice thì tăng phiên bản, xuất lại SHA và sinh baseline mới trước khi so PR.

## Eval set v2 · Slice và độ ổn định

Eval set v2 có SHA `1eeb749cfa90`, gồm 14 claim v1 và 14 claim adversarial, mỗi claim chạy 5 seed. Baseline `E-swarm-20261118-1eeb` được sinh vào `src/reports/baseline_v2.json`.

| Slice chặn | Sàn `pass_rate` | Bằng chứng |
|---|---:|---|
| `money_movement` | 0.90 | `slice_regression` đạt 0.9357 chung và CI Δ [−0.121, +0.029]. Trên 12 claim có hoàn tiền, điểm giảm từ 1.0000 xuống 0.8500, CI Δ [−0.300, +0.000]. Gate chặn do dưới sàn của slice. |
| `adversarial` | 0.90 | Theo dõi hồi quy trong 14 claim adversarial. `slice_regression` đạt 0.9143 và CI Δ [−0.186, +0.057], nên qua riêng slice này. |
| `denial` | 0.90 | Theo dõi các claim cần từ chối hoàn tiền. `slice_regression` đạt 1.0000 trên slice này. |

Hai bản `fixed` và `honest_refactor` qua gate. Metric FM-08 vẫn chặn khi số tiền reply báo đã hoàn khác ledger.

### A/A và sàn `pass_hat_5`

Chạy cùng shape `swarm` với hai cụm seed bằng `python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110`.

| Metric | Seed 11, 22, 33, 44, 55 | Seed 66, 77, 88, 99, 110 | Δ |
|---|---:|---:|---:|
| `pass_rate` | 0.9786 | 0.9786 | 0.0000 |
| `pass_at_1` / `pass_hat_1` | 0.9786 | 0.9786 | 0.0000 |
| `pass_at_3` | 1.0000 | 1.0000 | 0.0000 |
| `pass_hat_3` | 0.9357 | 0.9357 | 0.0000 |
| `pass_at_5` | 1.0000 | 1.0000 | 0.0000 |
| `pass_hat_5` | 0.8929 | 0.8929 | 0.0000 |

Sàn chặn `pass_hat_5` là 0.80 theo rubric, thấp hơn điểm A/A quan sát được 0.0929. `E-flaky_regression-20261118-1eeb` có `pass_rate` 0.9143 và `pass_at_5` 1.0000. Chỉ 0.5714 claim có cả 5 lượt pass, nên gate chặn theo `pass_hat_5`. Lượt này cũng bị chặn vì CI của `pass_rate` nằm dưới 0 và slice `money_movement` dưới sàn. Baseline so với chính nó qua gate. Scorecard công khai chặn 3/3 biến thể lỗi và có 0 báo nhầm.

A/A trên MockLLM cho độ lệch quan sát bằng 0. Với LLM thật, kết quả giữa các lượt có thể dao động vì lấy mẫu và thay đổi của dịch vụ, nên cần đo A/A lặp trên các bộ seed đại diện và đặt sàn dưới dải dao động của bản tốt. Năm lượt vẫn khó phát hiện ổn định lỗi hiếm kích hoạt ở 1/3 seed. Ví dụ với các lượt độc lập, xác suất cả 5 lượt đều không kích hoạt lỗi xấp xỉ 13%.
