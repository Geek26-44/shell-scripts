# Архитектурные рекомендации для Geek26 Bot v3

## Анализ текущих проблем

После изучения кода и архитектуры, я выявил основные болевые точки:

1. **CommandParser** использует жёсткие regex-паттерны
2. **chat_history** — глобальная переменная вне класса
3. **Executor** блокирует бота при выполнении команд
4. Отсутствует retry логика и обучение
5. Нет персистентности между перезапусками
6. Graphify требует точных имён узлов
7. Недостаточная модульность кода

## Рекомендации по улучшению

### 1. Улучшение Command Parsing для 9B моделей

**Проблема**: Regex-based парсер хрупкий, пропускает естественные фразы вроде "исследуй рынок".

**Решение: Гибридный подход с семантическими эмбеддингами**

```python
class SemanticCommandParser:
    """
    Комбинация:
    - Быстрые regex для точных паттернов
    - Локальные эмбеддинги для семантического поиска
    - Fallback на LLM-подсказки
    """

    def __init__(self):
        # Используем sentence-transformers с ONNX для скорости
        self.embeddings = LocalEmbeddings(model="all-MiniLM-L6-v2-onnx")

        # Семантические примеры команд
        self.command_examples = {
            CommandType.OBSIDIAN_SEARCH: [
                "найди в заметках про машинное обучение",
                "поищи информацию о quantum computing",
                "исследуй мои записи о проекте X",
                "что у меня есть по теме AI"
            ],
            CommandType.GRAPHIFY_QUERY: [
                "исследуй граф знаний по теме crypto",
                "изучи связи в области blockchain",
                "проанализируй узлы про distributed systems"
            ]
            # ... для каждого типа команды
        }

        # Предвычисляем эмбеддинги примеров
        self.example_embeddings = self._precompute_embeddings()

    def parse(self, text: str) -> ParsedCommand:
        # 1. Сначала быстрые regex (как сейчас)
        regex_result = self._try_regex_patterns(text)
        if regex_result.confidence > 0.8:
            return regex_result

        # 2. Семантический поиск по примерам
        semantic_result = self._semantic_search(text)
        if semantic_result.confidence > 0.6:
            return semantic_result

        # 3. LLM classification только для сложных случаев
        return self._llm_classify(text)
```

**Преимущества**:
- Быстро для простых случаев (regex)
- Понимает вариации фраз через эмбеддинги
- LLM используется только когда нужно
- Можно дообучать на успешных командах

### 2. Неблокирующий Executor

**Проблема**: Синхронное выполнение блокирует бота.

**Решение: Async/await архитектура с задачами**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncCommandExecutor:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.active_tasks = {}  # chat_id -> Task

    async def execute_async(self, command: ParsedCommand, user_id: int, chat_id: int):
        # Немедленный ответ пользователю
        await self.send_status(chat_id, "🔄 Выполняю команду...")

        # Запуск в фоне
        task_id = str(uuid.uuid4())
        task = asyncio.create_task(
            self._execute_in_background(command, user_id, chat_id, task_id)
        )
        self.active_tasks[chat_id] = task

        return task_id

    async def _execute_in_background(self, command, user_id, chat_id, task_id):
        try:
            # Длительные операции в thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                self._execute_sync,
                command, user_id
            )

            # Отправка результата
            await self.send_result(chat_id, result)

        except Exception as e:
            await self.send_error(chat_id, str(e))
        finally:
            # Очистка
            self.active_tasks.pop(chat_id, None)
```

**Дополнительные фичи**:
- Прогресс-бар для длительных операций
- Возможность отмены команды через `/cancel`
- Очередь команд с приоритетами

### 3. Персистентная память

**Проблема**: Теряется контекст при перезапуске.

**Решение: Легковесная встроенная БД**

```python
import sqlite3
from datetime import datetime, timedelta

class PersistentMemory:
    def __init__(self, db_path="geek26_memory.db"):
        self.db = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        # История чата
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp DATETIME,
                tokens INTEGER
            )
        """)

        # Успешные команды для обучения
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY,
                raw_text TEXT,
                command_type TEXT,
                params JSON,
                success BOOLEAN,
                timestamp DATETIME
            )
        """)

        # Кэш эмбеддингов
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS embeddings_cache (
                text TEXT PRIMARY KEY,
                embedding BLOB,
                created_at DATETIME
            )
        """)

    def get_recent_context(self, chat_id: int, hours: int = 24):
        """Получить контекст за последние N часов"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.db.execute("""
            SELECT role, content FROM chat_history
            WHERE chat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (chat_id, cutoff)).fetchall()

    def learn_from_success(self, text: str, command: ParsedCommand):
        """Запомнить успешную команду для обучения парсера"""
        self.db.execute("""
            INSERT INTO command_history (raw_text, command_type, params, success, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (text, command.type.value, json.dumps(command.params), True, datetime.now()))
```

### 4. Улучшенная эвристика выбора ответа

**Проблема**: Простая эвристика не учитывает контекст и тип вопроса.

**Решение: Контекстно-зависимая оценка**

```python
class ContextAwareScorer:
    def __init__(self):
        self.question_classifier = QuestionClassifier()  # Определяет тип вопроса

    def score(self, question: str, answer: str, context: List[Message]) -> float:
        # Определяем тип вопроса
        q_type = self.question_classifier.classify(question)

        # Базовая оценка
        base_score = self._base_score(question, answer)

        # Модификаторы по типу
        if q_type == "technical":
            # Для технических вопросов важны: код, точность, структура
            base_score += self._score_technical(answer)
        elif q_type == "creative":
            # Для творческих: оригинальность, развёрнутость
            base_score += self._score_creative(answer)
        elif q_type == "command":
            # Для команд: краткость, точность формата
            base_score += self._score_command(answer)

        # Учёт контекста разговора
        base_score += self._score_context_relevance(answer, context)

        # Учёт предпочтений модели для типа задачи
        model_bias = self._get_model_bias(q_type)

        return min(100, max(0, base_score * model_bias))
```

### 5. Fuzzy Matching для Graphify/Obsidian

**Проблема**: Требуются точные имена для поиска.

**Решение: Интеллектуальный поиск с исправлением**

```python
class FuzzySearcher:
    def __init__(self):
        self.speller = SpellChecker()  # Например, symspellpy
        self.fuzzy = FuzzyMatcher()    # Использует fuzzywuzzy/rapidfuzz

    def find_best_match(self, query: str, candidates: List[str]) -> Tuple[str, float]:
        # 1. Исправление опечаток
        corrected = self.speller.correct(query)

        # 2. Fuzzy поиск
        matches = self.fuzzy.extract(
            corrected,
            candidates,
            scorer=fuzz.token_sort_ratio,
            limit=5
        )

        # 3. Семантическая близость для топ-кандидатов
        if len(matches) > 1 and matches[0][1] < 90:
            # Используем эмбеддинги для уточнения
            semantic_scores = self._semantic_rerank(corrected, [m[0] for m in matches])
            best_idx = semantic_scores.argmax()
            return matches[best_idx][0], semantic_scores[best_idx]

        return matches[0] if matches else (None, 0)

    def search_graphify(self, query: str):
        # Получаем все узлы графа
        all_nodes = self._get_all_graph_nodes()

        # Находим лучшее совпадение
        best_match, confidence = self.find_best_match(query, all_nodes)

        if confidence > 0.7:
            return f"graphify query '{best_match}'"
        else:
            # Предлагаем варианты
            suggestions = self.fuzzy.extract(query, all_nodes, limit=3)
            return f"Не нашёл '{query}'. Возможно вы имели в виду: {suggestions}"
```

### 6. Модульная структура

**Проблема**: Всё в одном файле, сложно поддерживать.

**Решение: Разделение на модули**

```
geek26-bot/
├── main.py                 # Точка входа, инициализация
├── config.py              # Конфигурация, константы
├── models/
│   ├── __init__.py
│   ├── command.py         # ParsedCommand, CommandType
│   └── message.py         # Message, ChatHistory
├── parsers/
│   ├── __init__.py
│   ├── regex_parser.py    # Regex patterns
│   ├── semantic_parser.py # Embeddings-based
│   └── hybrid_parser.py   # Комбинированный
├── executors/
│   ├── __init__.py
│   ├── base.py           # BaseExecutor
│   ├── async_executor.py  # Async implementation
│   └── handlers/         # Отдельный файл на каждый тип команды
│       ├── obsidian.py
│       ├── git.py
│       ├── graphify.py
│       └── system.py
├── memory/
│   ├── __init__.py
│   ├── persistent.py     # SQLite storage
│   └── embeddings.py     # Embeddings cache
├── scoring/
│   ├── __init__.py
│   ├── heuristics.py     # Базовые эвристики
│   └── contextual.py     # Контекстная оценка
├── utils/
│   ├── __init__.py
│   ├── fuzzy_search.py   # Fuzzy matching
│   ├── safety.py         # SafetyValidator
│   └── monitoring.py     # Health checks
└── tests/
    ├── test_parser.py
    ├── test_executor.py
    └── test_memory.py
```

### 7. Мониторинг и здоровье системы

**Проблема**: Нет visibility в работу бота.

**Решение: Встроенный мониторинг**

```python
class HealthMonitor:
    def __init__(self):
        self.metrics = {
            'commands_total': 0,
            'commands_success': 0,
            'response_times': deque(maxlen=100),
            'model_scores': defaultdict(list),
            'memory_usage': 0,
            'last_error': None
        }

    def track_command(self, command: ParsedCommand, success: bool, duration: float):
        self.metrics['commands_total'] += 1
        if success:
            self.metrics['commands_success'] += 1
        self.metrics['response_times'].append(duration)

    def get_health_status(self) -> Dict:
        return {
            'status': 'healthy' if self._is_healthy() else 'degraded',
            'uptime': self._get_uptime(),
            'success_rate': self._calculate_success_rate(),
            'avg_response_time': np.mean(self.metrics['response_times']),
            'memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'active_models': list(MODELS.keys()),
            'last_error': self.metrics['last_error']
        }

    def report_to_obsidian(self):
        """Ежедневный отчёт в Obsidian"""
        report = self._generate_daily_report()
        # Сохраняем в vault/Health/geek26_health_YYYY-MM-DD.md
```

### 8. Дополнительные улучшения

#### A. Умное управление моделями

```python
class SmartModelManager:
    """Адаптивный выбор модели под задачу"""

    def __init__(self):
        self.model_performance = {}  # Треккинг успешности моделей

    def select_models_for_task(self, text: str, task_type: str) -> List[str]:
        # Для команд - только быстрая модель
        if task_type == "command":
            return ["qwen3.5:9b"]

        # Для творческих задач - обе модели
        if task_type == "creative":
            return ["qwen3.5:9b", "gemma4:e4b"]

        # Адаптивный выбор на основе истории
        return self._adaptive_selection(text)
```

#### B. Обучение на лету

```python
class OnlineLearning:
    """Улучшение парсера на основе feedback"""

    def learn_from_correction(self, original: str, corrected_command: ParsedCommand):
        # Добавляем в примеры для semantic parser
        self.parser.add_example(original, corrected_command)

        # Обновляем веса для scoring
        self.scorer.update_weights(original, corrected_command)

    def periodic_retraining(self):
        """Раз в сутки переобучаем эмбеддинги на новых примерах"""
        successful_commands = self.memory.get_successful_commands(days=7)
        self.parser.retrain_embeddings(successful_commands)
```

#### C. Graceful degradation

```python
class ResilientBot:
    """Устойчивость к сбоям"""

    def __init__(self):
        self.fallback_responses = {
            "ollama_down": "⚠️ Локальные модели недоступны. Попробуй через минуту.",
            "graphify_error": "📊 Граф временно недоступен, но я сохранил твой запрос.",
            "obsidian_locked": "🔒 Obsidian занят, повторю через 5 секунд..."
        }

    async def execute_with_fallback(self, command):
        try:
            return await self.primary_executor.execute(command)
        except OllamaError:
            # Сохраняем команду на потом
            await self.queue_for_retry(command)
            return self.fallback_responses["ollama_down"]
        except GraphifyError:
            # Используем локальный кэш
            return await self.cached_graphify_search(command)
```

## Приоритеты внедрения

1. **Фаза 1** (Критично):
   - Async executor (разблокировка бота)
   - Базовая персистентность (SQLite)
   - Модульная структура

2. **Фаза 2** (Важно):
   - Semantic parser с эмбеддингами
   - Fuzzy search
   - Мониторинг здоровья

3. **Фаза 3** (Улучшения):
   - Контекстная оценка ответов
   - Online learning
   - Адаптивный выбор моделей

## Технологический стек

- **Async**: `asyncio` + `aiohttp` вместо `requests`
- **Embeddings**: `sentence-transformers` с ONNX Runtime
- **Fuzzy**: `rapidfuzz` (быстрее fuzzywuzzy)
- **DB**: SQLite с WAL mode для конкурентности
- **Monitoring**: `psutil` + `prometheus_client` (опционально)
- **Testing**: `pytest` + `pytest-asyncio`

## Миграция

1. Начать с выноса в модули без изменения логики
2. Добавить async постепенно (сначала для длительных команд)
3. Внедрять новые фичи по одной с A/B тестированием
4. Сохранить обратную совместимость команд

Эта архитектура сделает Geek26 быстрым, умным и надёжным помощником, способным обучаться и адаптироваться под твои потребности.