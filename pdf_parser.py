import pdfplumber
import re


def parse_pdf_questions(pdf_file: str):
    questions = []
    current_module = "HÓA HỌC"
    buffer = ""
    question_no_in_module = 0

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue

                # ==============================
                # 1️⃣ BẮT CHƯƠNG BÀI TẬP
                # ==============================
                module_match = re.search(
                    r'Chương\s*Bài\s*tập\s*:\s*([A-ZÀ-Ỹ][A-ZÀ-Ỹ\s]+)',
                    line,
                    re.IGNORECASE
                )
                if module_match:
                    # 🔴 FLUSH CÂU CUỐI CHƯƠNG CŨ
                    if buffer:
                        question_no_in_module += 1
                        q = _parse_one_question(buffer, current_module, question_no_in_module)
                        if q:
                            questions.append(q)
                        buffer = ""

                    # ✅ RESET SANG CHƯƠNG MỚI
                    current_module = module_match.group(1).strip().upper()
                    question_no_in_module = 0
                    continue

                # ==============================
                # 2️⃣ GẶP CÂU MỚI
                # ==============================
                if re.match(r'^\d+\.\s', line):
                    if buffer:
                        question_no_in_module += 1
                        q = _parse_one_question(buffer, current_module, question_no_in_module)
                        if q:
                            questions.append(q)
                    buffer = line
                else:
                    buffer += "\n" + line

        # ==============================
        # 3️⃣ CÂU CUỐI FILE
        # ==============================
        if buffer:
            question_no_in_module += 1
            q = _parse_one_question(buffer, current_module, question_no_in_module)
            if q:
                questions.append(q)

    return questions


def _parse_one_question(block: str, module: str, no: int):
    ans_match = re.search(r'Đáp\s*án\s*[:.]?\s*([A-D])', block, re.IGNORECASE)
    correct_letter = ans_match.group(1).upper() if ans_match else "A"

    tip_match = re.search(r'Mẹo\s*:\s*(.*)', block, re.DOTALL | re.IGNORECASE)
    tip_content = tip_match.group(1).strip() if tip_match else ""

    main = re.sub(r'(Đáp\s*án|Mẹo)\s*:.*', '', block, flags=re.DOTALL | re.IGNORECASE).strip()
    parts = re.split(r'\s+([A-D])\.\s+', main)

    if len(parts) < 9:
        return None

    question_text = re.sub(r'^\d+\.\s*', '', parts[0]).strip()
    options = [parts[i].strip() for i in range(2, len(parts), 2)]

    if len(options) < 4:
        return None

    return {
        "module": module,
        "no": no,
        "question": question_text,
        "options": options[:4],
        "correct": correct_letter,
        "tip": tip_content if tip_content else "Chưa có mẹo giải chi tiết."
    }