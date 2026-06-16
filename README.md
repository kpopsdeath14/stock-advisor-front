# stock-advisor-front

Инвестиционный ассистент по российским акциям. Анализирует 5 бумаг: Аэрофлот, Сбербанк, Русал, Лукойл, НМТП.

Показывает исторический график цен, рассчитывает оптимальные доли портфеля и даёт сигналы (покупать / держать / продавать) в зависимости от риск-профиля пользователя.

## Стек

- **Фронтенд** — ClojureScript, Reagent, shadow-cljs, Ant Design, Recharts
- **Бэкенд API** (`API-dev/`) — Python, FastAPI, ML-модель на исторических данных с Yahoo Finance

## Запуск

**API:**
```bash
cd API-dev
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Фронтенд:**
```bash
npm install
npx shadow-cljs watch app
# открыть http://localhost:3000
```
