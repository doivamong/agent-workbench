# TRIẾT LÝ

> 🇬🇧 / 🇻🇳 **Đây là bản dịch tiếng Việt.** Bản tiếng Anh — [`../PHILOSOPHY.md`](../PHILOSOPHY.md) —
> là **nguồn chân lý**: nó là bản chuẩn. Nếu hai bản lệch nhau ở bất cứ điểm nào, **tin bản tiếng Anh** —
> file đó thắng.

<!-- en-sha256: 9d5d0dd01f1eb3f1d8b929f4b1e01f87f734fb64428c603c47c25817c318fb97 leak-scan: ignore[high_entropy_hex] -->

**Chuẩn (Canonical).** Đây là nguồn chân lý cho việc vì sao Agent Workbench tồn tại và nó phải hành
xử ra sao. [`README.md`](../README.md), [`CLAUDE.md`](../CLAUDE.md), và [`AGENTS.md`](../AGENTS.md)
trích đúng một dòng rồi link về đây — chúng không lặp lại nó. Nếu bất cứ thứ gì trong repo mâu thuẫn
với file này, file này thắng.

> **best-fit, honest about limits, not gospel.** (chọn cái phù hợp nhất, trung thực về giới hạn, không phải chân lý tuyệt đối)

Đó là một dòng mà mọi file khác trích nguyên văn.

## Bốn tenet

1. **Giải phóng (Liberation).** Bộ kit là lớp phương pháp luận generic được rút ra từ một codebase
   production riêng tư không bao giờ công khai được — tách ra để tri thức không bị chôn vùi ở đó mãi
   mãi. *Hệ quả:* nó mang theo không một chút IP nghiệp vụ, PII, secret hay định danh domain nào;
   đúc kết phương pháp, không bao giờ bê nguyên cả mã nguồn.

2. **Hữu ích hơn chỉ số (Utility over metrics).** Nó không được công bố để lấy star, lượt dùng
   (adoption), hay sự chú ý. Nó tồn tại để ai cần tới nó thì né được những sai lầm tránh được.
   *Hệ quả:* một thành phẩm đã làm xong việc của nó ngay khoảnh khắc nó có sẵn, đúng, và trung thực vào
   ngày ai đó với tay tới nó — dù có được đếm hay không. Đừng thêm tính năng chỉ để trông to hơn —
   nhưng *hãy* lớn lên theo nhu cầu thật: một tool hay một bài học giành được chỗ đứng khi nó đúc
   kết một phương pháp thật mà thiếu đi thì ai đó sẽ vấp. Cái mà gate chặn là sự phù phiếm, không
   phải tham vọng; sự phát triển có kỷ luật qua nhiều chu kỳ là sứ mệnh, không phải một rủi ro.

3. **Trung thực về giới hạn là cốt lõi đạo đức (Honesty about limits is the ethical core).** Chịu
   lực, không phải trang trí: một guard bị thổi phồng sẽ gây ra đúng cái vấp mà nó lẽ ra phải ngăn.
   *Hệ quả:* mọi tool và doc nói thẳng cái nó KHÔNG làm; guardrail là dây an toàn, không phải ranh
   giới bảo mật; và cái gì SHIPS luôn được phân biệt rõ với cái gì là một BLUEPRINT bạn tự triển khai
   (bảng trạng thái nằm trong [README.md](../README.md#status--honesty) — link tới đó, đừng lặp lại).

4. **Người hưởng lợi kép, ngang nhau (Dual, co-equal beneficiary).** Hai người đọc quan trọng ngang
   nhau: một người lạ cần tới nó, và chính tác giả ở tương lai khi bootstrap một codebase mới.
   *Hệ quả:* bộ kit vẫn là một starter framework thả vào là dùng được ngay từ ngày đầu; các bài
   học cũng là sản phẩm, ngang hàng với tool.

## Điều gì sẽ phản bội nó

Một thay đổi *bảo vệ* triết lý này nếu nó đúc kết một nhu cầu thật, bịt một kẽ hở, hay làm cho một
nguyên tắc ẩn trở nên grep được — phát triển có kỷ luật thì được hoan nghênh. Một thay đổi *phản bội*
nó nếu nó làm bất cứ điều nào sau đây — hãy bắt chúng trong review:

- một tính năng hay tool được thêm vào để trông to hơn thay vì vì một nhu cầu thật đòi hỏi — sự phình
  to mà không được đúc kết (phản bội tenet 2 và 4);
- doc của một guard bỏ mất dòng "cái nó KHÔNG làm", hoặc một tuyên bố tuyệt đối ("ngăn chặn",
  "đảm bảo", "an toàn") nằm cạnh một guard mà không có lời rào nào;
- lối diễn đạt kiểu star / lượt dùng / lượt truy cập len vào câu chữ;
- một tool ship mà không dán nhãn SHIPS vs BLUEPRINT;
- một định danh nghiệp vụ, đường dẫn máy thật, PII, hay secret quay trở lại;
- `CLAUDE.md` phình quá ngân sách ngắn của nó thay vì link ra ngoài;
- công việc làm **cho persona người-không-lập-trình** lại ship dưới dạng đánh bóng dashboard hay
  marketing kiểu "dễ / an toàn cho người không biết code", HOẶC giấu lời rào của nó trong một doc mà
  persona đó sẽ không bao giờ đọc — thay vì là một guard **fail-closed** (chặn-khi-lỗi) lặng lẽ, hoặc
  một lời rào mà agent **nói rõ bằng ngôn ngữ đời thường ngay tại thời điểm có rủi ro**. Một "dây an
  toàn" trung thực mà người dùng lại hiểu thành "két sắt" thì chính là phản bội đúng người mà nó tự
  nhận là bảo vệ. (Một guard *fail-open* (lỗi-thì-mở) thì vẫn ổn — leak-scan của chính bộ kit là một
  ví dụ — miễn là lời rào của nó được nói ra hoặc nêu rõ, chứ không bị chôn giấu.)
- **file này phình thành một bản tuyên ngôn** thay vì một ràng buộc cô đọng.

## Dành cho một agent context mới đang sửa repo này

Bốn tenet là chịu lực, không phải trang trí. Trước khi bạn đổi hành vi của một tool, doc của nó, hay
giọng của dự án, hãy đọc lại chúng. Giữ dòng trung thực trên mọi guard. Giữ cho mỗi file vệ tinh vẫn
link về file này. Chỉ sửa file này nếu chính triết lý đã đổi — đừng bao giờ để một file vệ tinh mâu
thuẫn với nó.

## Cách nó giữ nhất quán — và giới hạn của nó

[`tests/test_philosophy_anchor.py`](../tests/test_philosophy_anchor.py) là một tripwire CI: nó kiểm
rằng các file vệ tinh vẫn link về đây và rằng câu chữ tenet chuẩn chỉ sống trong file này. Skill
[`awb-review`](../.claude/skills/awb-review/SKILL.md) bổ sung phép kiểm ngữ nghĩa mà một regex không
làm được. **Giới hạn trung thực:** điều này giữ cho bề mặt công khai, các adopter, và một repo tương
lai được gieo mầm từ file này luôn nhất quán — nó **không** chi phối pipeline build/port riêng tư của
chính repo này, vốn có charter nội bộ riêng.

## Nó KHÔNG phải là gì

- **Không phải một bản tuyên ngôn.** Nếu một dòng ở đây thuyết giáo thay vì ràng buộc code hay docs,
  hãy cắt nó đi.
- Không phải lúc nào cũng được nạp — `CLAUDE.md` mang cái cốt lõi một dòng; đây là phần chi tiết mà
  nó link tới.
- File này cũng là một **hạt giống ngày đầu (day-1 seed)**: chép nó (cùng anchor test của nó) vào một
  repo mới để mang nguyên vẹn triết lý vận hành từ commit đầu tiên.
