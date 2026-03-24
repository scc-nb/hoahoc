import os
import random
from nicegui import ui
import re
from collections import defaultdict
from datetime import datetime
import json

def is_chemical_equation(opt: str) -> bool:
    if not opt:
        return False

    score = 0

    if '→' in opt or r'\rightarrow' in opt:
        score += 2

    if '+' in opt:
        score += 1

    if re.search(r'[A-Z][a-z]?\d*', opt):  # HCl, Na, KMnO4
        score += 1

    if re.search(r'_[0-9]', opt):  # H_2, SO_4
        score += 1

    return score >= 3
def build_exam_questions(all_questions, total=50):
    grouped = defaultdict(list)
    for q in all_questions:
        grouped[q["module"]].append(q)

    modules = list(grouped.keys())
    n = len(modules)

    per_module = total // n
    remainder = total % n

    selected = []

    # lấy đều mỗi chương
    for m in modules:
        qs = grouped[m]
        take = min(per_module, len(qs))
        selected.extend(random.sample(qs, take))

    # lấy phần dư
    if remainder > 0:
        pool = []
        for m in modules:
            pool.extend([q for q in grouped[m] if q not in selected])
        if pool:
            selected.extend(random.sample(pool, min(remainder, len(pool))))

    random.shuffle(selected)

    # đánh lại số câu trong đề
    for i, q in enumerate(selected, start=1):
        q["no"] = i

    return selected

def fix_broken_lines(text: str) -> str:
    """
    Gộp CHỈ các câu văn giải thích bị OCR gãy dòng.
    KHÔNG gộp:
    - Bước 1:, Bước 2:
    - Gạch đầu dòng •
    - Công thức, phương trình, biểu thức
    """
    if not text:
        return ""

    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    merged = []

    for line in lines:

        # 1. Tiêu đề bước
        if re.match(r'^\*?\s*Bước\s*\d+\s*:', line, re.IGNORECASE):
            merged.append(line)
            continue

        # 2. Gạch đầu dòng
        if re.match(r'^[•\-–]', line):
            merged.append(line)
            continue

        # 3. Công thức / phương trình / biểu thức
        if (
                '→' in line
                or r'\rightarrow' in line  # thêm dòng này
                or '$' in line  # thêm dòng này
                or '\\' in line  # thêm dòng này (bắt \mathrm, \PO ...)
                or re.search(r'_[0-9]', line)  # thêm dòng này (H_3, K_2...)
                or '=' in line
                or re.search(r'\(.+\)', line)
        ):
            merged.append(line)
            continue

        # 4. Chỉ gộp CÂU VĂN
        if merged and not re.search(r'[.!?]$', merged[-1]):
            merged[-1] += ' ' + line
        else:
            merged.append(line)

    return '\n'.join(merged)

def html_safe_text(text: str) -> str:
    """
    - Chống orphan word (O., H., A., ...)
    - Giữ xuống dòng chuẩn
    - An toàn cho HTML & PDF
    """
    if not text:
        return ""

    # Chống rơi chữ đơn vị (O., H., A., ...)
    text = re.sub(r' (\w)\.', r'&nbsp;\1.', text)

    # Xuống dòng HTML
    text = text.replace('\n', '<br>')

    return text




# --- Các hàm bổ trợ ---
try:
    from pdf_parser import parse_pdf_questions
    from chem_utils import chem_to_latex
except ImportError:
    def parse_pdf_questions(f):
        return [{"module": "ĐƯƠNG LƯỢNG",
                "question": "Đương lượng gam của một chất là:",
                "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                "correct": "A",
                "tip": "Mẹo: ☞ Đương lượng gam = khối lượng phản ứng với 1 phần H hoặc 8 phần O."}]


    def chem_to_latex(t):
        return t



# ===================== STATE & UI MANAGER =====================
class QuizApp:
    def __init__(self):
        self.all_questions = []
        self.questions = []
        self.current_idx = 0
        self.results = {}
        self.opts = {}
        self.correct_contents = {}
        self.page_name = 'mode'
        self.exam_mode = False
        self.exam_saved = False

        # Các biến lưu trữ UI Elements (Sẽ được gán khi trang load)
        self.header_el = None
        self.drawer_el = None
        self.mode_container = None
        self.quiz_container = None
        self.sidebar_container = None
        self.quiz_content_area = None


    def load_data(self):
        # Ưu tiên đọc từ file JSON siêu nhẹ
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding="utf-8") as f:
                self.all_questions = json.load(f)
        elif os.path.exists("hhp.pdf"):
            # Dự phòng nếu chạy ở máy tính vẫn còn file PDF
            self.all_questions = parse_pdf_questions("hhp.pdf")
        else:
            self.all_questions = [
                {"module": "VÔ CƠ", "question": "Axit Sunfuric là $H_2SO_4$",
                 "options": ["Đúng", "Sai", "Khác", "Không rõ"], "correct": "A",
                 "tip": "Mẹo: Ghi nhớ gốc $SO_4$ hóa trị II."},
                {"module": "HỮU CƠ", "question": "Metan là $CH_4$", "options": ["Sai", "Đúng", "Khác", "Không rõ"],
                 "correct": "B", "tip": "Mẹo: Ankan đơn giản nhất."}
            ]

    def build_module_numbers(self):
        """Map index -> số câu trong chương"""
        module_count = defaultdict(int)
        local_no = {}

        for idx, q in enumerate(self.questions):
            m = q["module"]
            module_count[m] += 1
            local_no[idx] = module_count[m]

        return local_no
    def set_question(self, idx):
        self.current_idx = idx
        self.render_quiz()
        self.render_sidebar()

    def handle_answer(self, choice):
        correct = self.correct_contents[self.current_idx]
        self.results[self.current_idx] = (choice == correct)
        self.render_quiz()
        self.render_sidebar()

    def render_exam_distribution_mini(self):
        from collections import Counter

        counter = Counter(q["module"] for q in self.questions)
        max_v = max(counter.values())

        with ui.column().classes(
                'absolute top-4 right-4 w-56 p-3 bg-white rounded-xl '
                'shadow-md border text-xs'
        ):
            ui.label("📊 PHÂN BỐ CHƯƠNG") \
                .classes('font-bold text-blue-900 mb-2 text-xs')

            for m, c in counter.items():
                percent = int(c / max_v * 100)

                with ui.row().classes('items-center justify-between'):
                    ui.label(m).classes('text-slate-600 font-semibold')
                    ui.label(f"{c}").classes('text-slate-400')

                ui.html(f"""
                <div style="
                    background:#e5e7eb;
                    height:6px;
                    border-radius:6px;
                    margin:2px 0 6px 0;
                ">
                    <div style="
                        width:{percent}%;
                        height:6px;
                        background:#2563eb;
                        border-radius:6px;
                    "></div>
                </div>
                """)
    def render_sidebar(self):
        if not self.sidebar_container:
            return
        self.sidebar_container.clear()

        # =========================
        # 📝 THI THỬ → CHỈ HIỆN 1–50
        # =========================
        if self.exam_mode:
            with self.sidebar_container:

                ui.label("📋 DANH SÁCH CÂU") \
                    .classes('text-lg font-bold mb-4 px-4 mt-6 text-blue-900')

                with ui.grid(columns=4).classes('gap-2 p-4'):
                    for i in range(len(self.questions)):
                        COLOR_GRAY = '#9e9e9e'
                        COLOR_BLUE = '#2196f3'
                        COLOR_GREEN = '#4caf50'
                        COLOR_RED = '#f44336'

                        if i in self.results:
                            bg_color = COLOR_GREEN if self.results[i] else COLOR_RED
                        elif i == self.current_idx:
                            bg_color = COLOR_BLUE
                        else:
                            bg_color = COLOR_GRAY

                        border = (
                            'border: 3px solid #000 !important;'
                            if i == self.current_idx else ''
                        )

                        ui.button(
                            str(i + 1),
                            on_click=lambda i=i: self.set_question(i)
                        ).style(
                            f'background:{bg_color}!important;'
                            f'color:white!important;'
                            f'{border}'
                            f'min-width:44px;height:44px;'
                        ).classes('font-bold rounded-lg text-xs')
                ui.separator().classes('mx-4 my-2 opacity-60')
                self.render_exam_distribution_sidebar()
            return  # ⛔ RẤT QUAN TRỌNG – KHÔNG CHẠY CODE DƯỚI

        # ==================================================
        # 📘 ÔN TẬP → CHIA THEO CHƯƠNG (GIỮ NGUYÊN CODE CŨ)
        # ==================================================
        from collections import defaultdict
        grouped_data = defaultdict(list)
        local_no = self.build_module_numbers()
        for idx, q in enumerate(self.questions):
            mod_name = q.get('module', 'HÓA HỌC').upper()
            grouped_data[mod_name].append(idx)

        with self.sidebar_container:
            ui.label("📋 DANH SÁCH CÂU") \
                .classes('text-lg font-bold mb-2 px-4 mt-6 text-blue-900')

            for mod_name, indices in grouped_data.items():
                ui.label(f"● {mod_name} ({len(indices)} câu)") \
                    .classes(
                    'px-4 text font-black text-slate-500 mt-4 '
                    'tracking-wider uppercase'
                )

                with ui.grid(columns=4).classes('gap-2 p-4 pt-1'):
                    for i in indices:
                        COLOR_GRAY = '#9e9e9e'
                        COLOR_BLUE = '#2196f3'
                        COLOR_GREEN = '#4caf50'
                        COLOR_RED = '#f44336'

                        if i in self.results:
                            bg_color = COLOR_GREEN if self.results[i] else COLOR_RED
                        elif i == self.current_idx:
                            bg_color = COLOR_BLUE
                        else:
                            bg_color = COLOR_GRAY

                        border_style = (
                            'border: 3px solid #000 !important;'
                            if i == self.current_idx else ''
                        )

                        ui.button(
                            str(local_no[i]),
                            on_click=lambda i=i: self.set_question(i)
                        ).style(
                            f'background-color:{bg_color}!important;'
                            f'color:white!important;'
                            f'{border_style}'
                            f'min-width:44px;height:44px;'
                        ).classes(
                            'shadow-none font-bold rounded-lg '
                            'transition-none text-xs'
                        )

    def render_exam_distribution_sidebar(self):
        from collections import Counter

        with self.sidebar_container:  # ⭐ BẮT BUỘC ⭐
            counter = Counter(q["module"] for q in self.questions)
            max_v = max(counter.values())

            ui.label("📊 PHÂN BỐ CHƯƠNG") \
                .classes('text-sm font-bold text-blue-900 px-4 mb-1')

            for m, c in counter.items():
                percent = int(c / max_v * 100)

                with ui.row().classes('items-center px-4 gap-2 mb-0'):
                    ui.label(m).classes(
                        'text-xs font-medium text-slate-600 w-24 leading-none'
                    )
                    ui.label(f"{c} câu").classes(
                        'text-xs text-slate-400 leading-none'
                    )


    def render_quiz(self):
        if not self.quiz_content_area: return
        self.quiz_content_area.clear()
        if not self.questions: return

        q = self.questions[self.current_idx]
        local_no = self.build_module_numbers()

        with self.quiz_content_area:
            with ui.card().classes('w-full max-w-4xl p-8 shadow-xl border-t-8 border-blue-600 min-h-[450px] mt-10'):
                # Hiển thị Dạng bài tập (Module)
                #ui.label(f"DẠNG BÀI TẬP: {q.get('module', 'HÓA HỌC').upper()}") \
                #    .classes('text-blue-700 font-bold tracking-widest text-sm mb-2')

                #ui.label(f"CÂU {self.current_idx + 1}").classes('text-slate-400 text-xs font-bold')
                # Làm nhãn CÂU to hơn (text-4xl), in đậm nhất (font-black) và đổi màu xanh đậm
                # ===== TÊN CHƯƠNG (CHỈ HIỆN KHI THI THỬ) =====
                if self.exam_mode:
                    ui.label(q.get("module", "").upper()) \
                        .classes(
                        'text-xs font-bold tracking-widest text-slate-400 mb-1'
                    )

                # ===== CÂU SỐ =====
                if self.exam_mode:
                    ui.label(f"CÂU {q['no']}:") \
                        .classes('text-blue-800 font-black text-2xl tracking-tighter mb-2')
                else:
                    ui.label(f"CÂU {local_no[self.current_idx]}:") \
                        .classes('text-blue-800 font-black text-2xl tracking-tighter mb-2')
                # 1. Fix OCR gãy dòng trước
                # Fix OCR gãy dòng
                question_text = fix_broken_lines(q["question"])

                ui.html(
                    f'<div style="white-space: pre-line;" '
                    f'class="text-2xl font-medium mb-3 leading-snug text-slate-800">'
                    f'{chem_to_latex(question_text)}</div>'
                )

                if self.current_idx in self.results:
                    is_correct = self.results[self.current_idx]
                    ui.label("✅ CHÍNH XÁC" if is_correct else "❌ CHƯA ĐÚNG") \
                        .classes(f"text-xl font-bold {'text-green-600' if is_correct else 'text-red-600'} mb-2")

                    # Đáp án đúng
                    ui.html(
                        f'<div class="p-4 bg-slate-100 rounded-lg mb-4 text-lg border-l-4 border-blue-500">'
                        f'<b>Đáp án đúng:</b> {chem_to_latex(self.correct_contents[self.current_idx])}</div>')
                    # --- PHẦN THIẾT KẾ MẸO GIẢI DẠNG QUYỂN SỔ ---
                    if q.get('tip'):
                        with ui.expansion('', icon='book').classes(
                                'w-full bg-white border rounded-xl shadow-sm mb-2 overflow-hidden') as exp:
                            # Header của expansion thiết kế giống nhãn "XEM GIẢI CHI TIẾT"
                            with exp.add_slot('header'):
                                with ui.row().classes('items-center w-full'):
                                    ui.icon('menu_book', size='sm').classes('text-blue-900')
                                    ui.label('XEM GIẢI CHI TIẾT').classes(
                                        'text-blue-900 font-black tracking-tighter text-lg ml-2')

                            import re
                            tip_text = q["tip"]

                            # 1. Tự động bôi đậm tiêu đề "Bước x:"
                            tip_text = re.sub(r'(Bước \d+:)',
                                              r'<b class="text-blue-900" style="font-weight: 900;">\1</b>', tip_text)

                            # 2. Xử lý các nội dung in đậm khác (nếu có dấu ** trong text)
                            tip_text = re.sub(r'\*\*(.*?)\*\*', r'<b style="font-weight: 800; color: #1a1a1a;">\1</b>',
                                              tip_text)

                            # 3. Định dạng dấu chấm tròn thụt lề cho đẹp
                            tip_text = tip_text.replace('•', '&nbsp;&nbsp;&nbsp;•')

                            # 4. Nội dung chính bên trong "quyển sổ"
                            with ui.column().classes('w-full p-4 bg-slate-50 border-t'):
                                raw_text = chem_to_latex(tip_text)

                                # 1️⃣ Gộp câu OCR bị gãy
                                raw_text = fix_broken_lines(raw_text)

                                # 2️⃣ Chuyển sang HTML an toàn
                                html_text = html_safe_text(raw_text)

                                ui.html(f"""
                                    <div
                                        style="
                                            white-space: normal;
                                            border-left: 5px solid #1e3a8a;
                                        "
                                        class="
                                            p-6 bg-white shadow-inner rounded-r-lg
                                            text-slate-800 leading-relaxed
                                            text-lg font-medium
                                        ">
                                        {html_text}
                                    </div>
                                """)
                    # ===== THỐNG KÊ CHỈ KHI THI THỬ & CÂU CUỐI =====
                    if self.exam_mode and self.current_idx == len(self.questions) - 1:
                        stats = self.calc_stats_by_module()
                        ui.label("📊 THỐNG KÊ THEO CHƯƠNG").classes('font-bold text-xl mt-6')
                        for m, s in stats.items():
                            ui.label(f"{m}: {s['correct']} / {s['total']} câu đúng")

                    # ===== LƯU LỊCH SỬ THI THỬ (CHỈ CÂU CUỐI) =====
                    if (
                            self.exam_mode
                            and self.current_idx == len(self.questions) - 1
                            and not self.exam_saved
                    ):
                        self.save_exam_history()
                        self.exam_saved = True
                    # -----------------------------------------------
                    if self.current_idx < len(self.questions) - 1:
                        ui.button('CÂU TIẾP THEO', on_click=lambda: self.set_question(self.current_idx + 1)) \
                            .props('elevated icon-right=arrow_forward').classes('mt-6 bg-blue-600 text-white px-6 py-2')
                else:
                    # Xử lý trộn đáp án
                    if self.current_idx not in self.opts:
                        raw_opts = q["options"]
                        correct_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                        correct_idx = correct_map.get(q.get('correct', 'A'), 0)
                        self.correct_contents[self.current_idx] = raw_opts[correct_idx]

                        shuffled = raw_opts[:]
                        random.shuffle(shuffled)
                        self.opts[self.current_idx] = shuffled

                    # --- THAY ĐỔI Ở ĐÂY: Sử dụng grid 2 cột ---
                    # 🔍 chỉ kiểm tra PHƯƠNG TRÌNH HOÁ HỌC
                    has_long_equation = any(
                        is_chemical_equation(opt) and len(opt) > 40
                        for opt in self.opts[self.current_idx]
                    )

                    columns = 1 if has_long_equation else 2

                    with ui.grid(columns=columns).classes('gap-4 w-full mt-4'):
                        for opt in self.opts[self.current_idx]:
                            btn = ui.button(on_click=lambda o=opt: self.handle_answer(o)) \
                                .props('outline size=lg') \
                                .style(
                                'white-space: normal;'
                                'word-break: break-word;'
                            ) \
                                .classes(
                                'w-full py-6 rounded-xl transition-none '
                                'border-2 hover:bg-blue-50 h-auto'
                            )
                            with btn:
                                # Dùng flex để căn chữ lùi về bên trái nếu muốn, hoặc mặc định căn giữa
                                ui.html(chem_to_latex(opt)).classes('text-black normal-case text-lg leading-snug text-center')


        ui.run_javascript('renderMath()')

    def switch_view(self):
        is_quiz = (self.page_name == 'quiz')
        self.header_el.set_visibility(is_quiz)
        self.drawer_el.set_visibility(is_quiz)
        self.mode_container.set_visibility(not is_quiz)
        self.quiz_container.set_visibility(is_quiz)

        if is_quiz:
            self.render_sidebar()
            self.render_quiz()
        ui.run_javascript('renderMath()')

    def calc_stats_by_module(self):
        from collections import defaultdict
        stats = defaultdict(lambda: {"total": 0, "correct": 0})

        for i, q in enumerate(self.questions):
            mod = q["module"]
            stats[mod]["total"] += 1
            if self.results.get(i):
                stats[mod]["correct"] += 1

        return stats

    def save_exam_history(self):
        stats = self.calc_stats_by_module()
        correct = sum(1 for v in self.results.values() if v)

        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "score": correct,
            "total": len(self.questions),
            "by_module": {
                m: f"{s['correct']}/{s['total']}"
                for m, s in stats.items()
            }
        }

        path = "exam_history.json"
        history = []

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)

        history.append(record)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

# ===================== MAIN PAGE =====================

@ui.page('/')
def main_page():
    # Khởi tạo một Manager riêng cho mỗi phiên truy cập
    app = QuizApp()
    app.load_data()

    # Cấu hình HEAD (Katex/CSS)
    ui.add_head_html('''
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <script>
    function renderMath() {
        renderMathInElement(document.body, {
            delimiters: [{left: "$$", right: "$$", display: true}, {left: "$", right: "$", display: false}],
            throwOnError: false
        });
    }
    let rendering = false;

    const observer = new MutationObserver(() => {
        if (rendering) return;
        rendering = true;

        requestAnimationFrame(() => {
            renderMath();
            rendering = false;
        });
    })
    observer.observe(document.documentElement, { childList: true, subtree: true });
    </script>
    <style> .transition-none { transition: none !important; } .nicegui-content { padding: 0 !important; } </style>
    ''')

    # 1. Header & Drawer
    with ui.header().classes('bg-blue-900 shadow-lg px-6 py-4') as header:
        app.header_el = header
        ui.label("HÓA HỌC PRO").classes('font-bold text-2xl tracking-tight')
        ui.space()
        ui.button(icon='home', on_click=lambda: (setattr(app, 'page_name', 'mode'), app.switch_view())) \
            .props('flat color=white size=lg')

    with ui.left_drawer(value=True).classes('bg-slate-50 border-r w-72 p-0') as drawer:
        app.drawer_el = drawer
        app.sidebar_container = ui.column().classes('w-full')

    # 2. Màn hình chọn Mode
    with ui.column().classes('fixed-center items-center gap-8 w-full') as mode_cont:
        app.mode_container = mode_cont
        with ui.column().classes('items-center gap-2'):
            ui.icon('science', size='120px').classes('text-blue-600')
            ui.label("HÓA HỌC PRO").classes('text-7xl font-black text-blue-900 tracking-tighter')
            ui.label("Hệ thống ôn luyện thông minh").classes('text-slate-400 text-lg')

        with ui.row().classes('gap-8 mt-4'):
            def start(m):
                app.results, app.opts, app.current_idx = {}, {}, 0
                app.exam_saved = False
                if m == 'all':
                    app.questions = app.all_questions[:]
                    for i, q in enumerate(app.questions, start=1):
                        q["no"] = i
                    app.exam_mode = False
                else:
                    app.questions = build_exam_questions(app.all_questions, total=50)
                    app.exam_mode = True

                app.page_name = 'quiz'
                app.switch_view()

            ui.button("📘 ÔN TẬP TOÀN BỘ", on_click=lambda: start('all')) \
                .classes('p-8 text-xl bg-blue-500 text-white rounded-2xl shadow-xl hover:scale-105 transition-all')
            ui.button("📝 THI THỬ (50 CÂU)", on_click=lambda: start('exam')) \
                .classes('p-8 text-xl bg-blue-500 text-white rounded-2xl shadow-xl hover:scale-105 transition-all')

    # 3. Màn hình làm bài
    with ui.column().classes('w-full items-center p-4 md:p-12 bg-slate-50 min-h-screen') as quiz_cont:
        app.quiz_container = quiz_cont
        app.quiz_content_area = ui.column().classes('w-full items-center')

    app.switch_view()


if __name__ in {"__main__", "__mp_main__"}:
    # Lấy port tự động từ server đám mây, nếu chạy trên máy tính thì mặc định là 8080
    port = int(os.environ.get('PORT', 8080))
    ui.run(title="App Ôn Hóa", host="0.0.0.0", port=port, favicon="🧪", reload=False)