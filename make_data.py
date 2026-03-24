import json
from pdf_parser import parse_pdf_questions

print("Đang đọc file PDF, vui lòng đợi vài giây...")
# Đọc file PDF trên máy tính của bạn
questions = parse_pdf_questions("hhp.pdf") 

# Lưu kết quả ra file data.json
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=4)

print("Xong! Đã tạo thành công file data.json")