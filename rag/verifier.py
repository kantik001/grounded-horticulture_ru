# ----------------------------------------------------------------------
# Верификация RAG-ответов: проверка чисел по фрагментам контекста.
# Названия статей пользователю не показываются — только общий дисклеймер на Go.
# ----------------------------------------------------------------------
import re
from typing import List, Tuple

from langchain_core.documents import Document

RAG_ANSWER_DISCLAIMER = (
    "Справочная информация из базы знаний. Не заменяет очный осмотр агронома; "
    "решения по препаратам — с учётом инструкций и законодательства."
)

_SOURCE_LINE_RE = re.compile(r"(?im)^\s*Источник:.*\n?")


# Извлекает все числа из текста (для сравнения ответа с контекстом).
def extract_numbers(text: str) -> List[float]:
    if not text:
        return []
    text = text.replace(",", ".")
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    return [float(n) for n in numbers]


# Убирает строки «Источник:» и дисклеймер перед проверкой чисел.
def strip_source_attribution(answer: str) -> str:
    s = _SOURCE_LINE_RE.sub("", answer or "")
    s = s.replace(RAG_ANSWER_DISCLAIMER, "")
    return " ".join(s.split())


# Проверяет, что каждое число в ответе встречается во фрагментах статей (эталон для pytest).
def verify_answer(question: str, answer: str, fragments: List[Document]) -> Tuple[bool, str]:
    if answer is None:
        return False, "Ответ отсутствует (None)"
    if not isinstance(answer, str):
        return False, "Ответ не является строкой"

    context_text = "\n".join([f.page_content for f in fragments])
    body = strip_source_attribution(answer)
    numbers_in_answer = extract_numbers(body)
    if numbers_in_answer:
        numbers_in_context = extract_numbers(context_text)
        missing_numbers = []
        for num in numbers_in_answer:
            if not any(abs(num - ctx_num) < 0.01 for ctx_num in numbers_in_context):
                missing_numbers.append(num)
        if missing_numbers:
            return False, f"Число(а) {missing_numbers} не найдены в источниках."

    return True, "Верификация пройдена"
