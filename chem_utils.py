import re

def chem_to_latex(text: str) -> str:
    """
    Chuyển công thức hóa học text thường sang LaTeX
    Ví dụ:
    4Cr + 3O2 → 2Cr2O3
    => 4Cr + 3O_{2} \\rightarrow 2Cr_{2}O_{3}
    """

    if not text:
        return ""

    # Chuẩn hóa mũi tên phản ứng
    text = text.replace("→", r"\rightarrow")
    text = text.replace("->", r"\rightarrow")

    # Chỉ số dưới: O2 -> O_2, Cr2 -> Cr_2
    text = re.sub(r'([A-Za-z])(\d+)', r'\1_{\2}', text)

    # Trạng thái (r), (k), (dd)
    text = re.sub(r'\((r|k|dd|l|s|g)\)', r'_{\text{(\1)}}', text)

    return text
