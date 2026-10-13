from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path


class Memory:
    def __init__(self, database: str | Path = "data/laura.db") -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user, key)
            );
            CREATE TABLE IF NOT EXISTS learned_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user, question)
            );
            CREATE TABLE IF NOT EXISTS profiles (
                user TEXT PRIMARY KEY,
                trust REAL NOT NULL DEFAULT 25,
                patience REAL NOT NULL DEFAULT 100
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                text TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user, text)
            );
            CREATE TABLE IF NOT EXISTS fact_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL, key TEXT NOT NULL,
                old_value TEXT NOT NULL, new_value TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS visual_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                label TEXT NOT NULL,
                features TEXT NOT NULL,
                thumbnail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS visual_examples_user_label
                ON visual_examples(user, label);
            CREATE TABLE IF NOT EXISTS visual_recognitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                predicted_label TEXT,
                actual_label TEXT,
                confidence REAL NOT NULL DEFAULT 0,
                known INTEGER NOT NULL DEFAULT 0,
                correct INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS generation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                generation_id TEXT NOT NULL,
                context TEXT NOT NULL,
                rating TEXT NOT NULL,
                signature TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user, generation_id)
            );
            CREATE INDEX IF NOT EXISTS generation_feedback_context ON generation_feedback(user,context);
            """
        )
        self.connection.commit()

    def remember(self, user: str, key: str, value: str) -> None:
        old = self.recall(user, key)
        if old is not None and old != value:
            self.connection.execute(
                "INSERT INTO fact_history(user,key,old_value,new_value) VALUES (?,?,?,?)",
                (user, key, old, value),
            )
        self.connection.execute(
            """INSERT INTO facts(user, key, value) VALUES (?, ?, ?)
               ON CONFLICT(user, key) DO UPDATE SET
               value=excluded.value, confidence=1.0, updated_at=CURRENT_TIMESTAMP""",
            (user, key, value),
        )
        self.connection.commit()

    def recall(self, user: str, key: str) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM facts WHERE user=? AND key=?", (user, key)
        ).fetchone()
        return str(row["value"]) if row else None

    def facts(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT key, value, confidence FROM facts WHERE user=? ORDER BY key", (user,)
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_fact(self, user: str, key: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM facts WHERE user=? AND key=?", (user, key)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def search_facts(self, user: str, query: str) -> list[dict[str, object]]:
        pattern = f"%{query}%"
        rows = self.connection.execute(
            """SELECT key,value,confidence FROM facts WHERE user=?
               AND (key LIKE ? OR value LIKE ?) ORDER BY key""", (user, pattern, pattern)
        ).fetchall()
        return [dict(row) for row in rows]

    def conflicts(self, user: str, limit: int = 30) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT key,old_value,new_value,changed_at FROM fact_history
               WHERE user=? ORDER BY id DESC LIMIT ?""", (user, limit)
        ).fetchall()
        return [dict(row) for row in rows]

    def teach(self, user: str, question: str, answer: str) -> None:
        self.connection.execute(
            """INSERT INTO learned_answers(user, question, answer) VALUES (?, ?, ?)
               ON CONFLICT(user, question) DO UPDATE SET answer=excluded.answer""",
            (user, question, answer),
        )
        self.connection.commit()

    def learned_answers(self, user: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, question, answer FROM learned_answers WHERE user IN (?, '*')",
            (user,),
        ).fetchall()

    def learned_answers_data(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT question, answer, uses, created_at FROM learned_answers
               WHERE user IN (?, '*') ORDER BY id DESC""", (user,)
        ).fetchall()
        return [dict(row) for row in rows]

    def count_use(self, answer_id: int) -> None:
        self.connection.execute(
            "UPDATE learned_answers SET uses=uses+1 WHERE id=?", (answer_id,)
        )
        self.connection.commit()

    def log(self, user: str, role: str, content: str) -> None:
        self.connection.execute(
            "INSERT INTO messages(user, role, content) VALUES (?, ?, ?)",
            (user, role, content),
        )
        self.connection.commit()

    def profile(self, user: str) -> dict[str, float]:
        self.connection.execute("INSERT OR IGNORE INTO profiles(user) VALUES (?)", (user,))
        self.connection.commit()
        row = self.connection.execute(
            "SELECT trust, patience FROM profiles WHERE user=?", (user,)
        ).fetchone()
        return {"trust": float(row["trust"]), "patience": float(row["patience"])}

    def update_profile(self, user: str, trust_delta: float = 0, patience_delta: float = 0) -> None:
        self.profile(user)
        self.connection.execute(
            """UPDATE profiles SET
               trust=MIN(100, MAX(0, trust + ?)),
               patience=MIN(100, MAX(0, patience + ?))
               WHERE user=?""",
            (trust_delta, patience_delta, user),
        )
        self.connection.commit()

    def history(self, user: str, limit: int = 100) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT role, content, created_at FROM messages
               WHERE user=? ORDER BY id DESC LIMIT ?""",
            (user, min(max(limit, 1), 500)),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def clear_history(self, user: str) -> None:
        self.connection.execute("DELETE FROM messages WHERE user=?", (user,))
        self.connection.commit()

    def add_training_example(self, user: str, text: str, label: str) -> None:
        self.connection.execute(
            """INSERT INTO training_examples(user, text, label) VALUES (?, ?, ?)
               ON CONFLICT(user, text) DO UPDATE SET label=excluded.label""",
            (user, text, label),
        )
        self.connection.commit()

    def training_examples(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT text, label, created_at FROM training_examples
               WHERE user=? ORDER BY id DESC""", (user,)
        ).fetchall()
        return [dict(row) for row in rows]

    def add_visual_example(self, user: str, label: str, features: list[float], thumbnail: str = "") -> int:
        clean_label = " ".join(label.strip().lower().split())[:60]
        if not clean_label or len(features) != 88:
            raise ValueError("categoria ou características inválidas")
        cursor = self.connection.execute(
            "INSERT INTO visual_examples(user,label,features,thumbnail) VALUES (?,?,?,?)",
            (user, clean_label, json.dumps(features, separators=(",", ":")), thumbnail),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_visual_examples_bulk(self, user: str,
                                 examples: list[tuple[str, list[float], str]]) -> int:
        prepared = []
        for label, features, preview in examples:
            clean_label = " ".join(label.strip().lower().split())[:60]
            if not clean_label or len(features) != 88:
                raise ValueError("categoria ou características inválidas")
            prepared.append((user, clean_label,
                             json.dumps(features, separators=(",", ":")), preview))
        with self.connection:
            self.connection.executemany(
                "INSERT INTO visual_examples(user,label,features,thumbnail) VALUES (?,?,?,?)",
                prepared,
            )
        return len(prepared)

    def visual_vectors(self, user: str) -> list[tuple[str, list[float]]]:
        rows = self.connection.execute(
            "SELECT label,features FROM visual_examples WHERE user=? ORDER BY id", (user,)
        ).fetchall()
        return [(str(row["label"]), [float(value) for value in json.loads(row["features"])]) for row in rows]

    def rename_visual_category(self, user: str, old_label: str, new_label: str) -> int:
        clean = " ".join(new_label.strip().lower().split())[:60]
        if not clean:
            raise ValueError("nome da categoria vazio")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE visual_examples SET label=? WHERE user=? AND label=?",
                (clean, user, old_label),
            )
            self.connection.execute(
                "UPDATE visual_recognitions SET predicted_label=? WHERE user=? AND predicted_label=?",
                (clean, user, old_label),
            )
            self.connection.execute(
                "UPDATE visual_recognitions SET actual_label=? WHERE user=? AND actual_label=?",
                (clean, user, old_label),
            )
            for row in self.connection.execute(
                "SELECT id,context FROM generation_feedback WHERE user=?", (user,)).fetchall():
                context = str(row["context"])
                if context == f"learned:{old_label}":
                    replacement = f"learned:{clean}"
                elif context.startswith("scene:"):
                    parts = context.split(":", 2)
                    replacement = f"scene:{clean if parts[1] == old_label else parts[1]}:{clean if parts[2] == old_label else parts[2]}"
                else:
                    continue
                if replacement != context:
                    self.connection.execute(
                        "UPDATE generation_feedback SET context=? WHERE id=?", (replacement[:200], row["id"]))
        return cursor.rowcount

    def visual_examples(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT id,label,features,thumbnail,created_at FROM visual_examples
               WHERE user=? ORDER BY id DESC""", (user,)
        ).fetchall()
        return [dict(row) for row in rows]

    def visual_items(self, user: str, label: str | None = None) -> list[dict[str, object]]:
        if label:
            rows = self.connection.execute(
                """SELECT id,label,thumbnail,created_at FROM visual_examples
                   WHERE user=? AND label=? ORDER BY id DESC""", (user, label)
            ).fetchall()
        else:
            rows = self.connection.execute(
                """SELECT id,label,thumbnail,created_at FROM visual_examples
                   WHERE user=? ORDER BY id DESC LIMIT 100""", (user,)
            ).fetchall()
        return [dict(row) for row in rows]

    def visual_count(self, user: str, label: str) -> int:
        return int(self.connection.execute(
            "SELECT COUNT(*) FROM visual_examples WHERE user=? AND label=?", (user, label)).fetchone()[0])

    def visual_samples(self, user: str, label: str, seed: object, limit: int = 24) -> list[dict[str, object]]:
        ids = [row[0] for row in self.connection.execute(
            "SELECT id FROM visual_examples WHERE user=? AND label=? AND thumbnail<>'' ORDER BY id", (user, label))]
        chosen = random.Random(str(seed)).sample(ids, min(len(ids), max(1, min(24, limit))))
        if not chosen:
            return []
        placeholders = ",".join("?" for _ in chosen)
        rows = self.connection.execute(
            f"SELECT label,thumbnail FROM visual_examples WHERE user=? AND id IN ({placeholders}) ORDER BY id",
            (user, *chosen)).fetchall()
        return [dict(row) for row in rows]

    def delete_visual_example(self, user: str, example_id: int) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM visual_examples WHERE user=? AND id=?", (user, example_id)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def log_visual_recognition(self, user: str, predicted_label: str | None,
                               confidence: float, known: bool) -> int:
        cursor = self.connection.execute(
            """INSERT INTO visual_recognitions(user,predicted_label,confidence,known)
               VALUES (?,?,?,?)""", (user, predicted_label, confidence, int(known))
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def correct_visual_recognition(self, user: str, recognition_id: int, actual_label: str) -> bool:
        row = self.connection.execute(
            "SELECT predicted_label FROM visual_recognitions WHERE user=? AND id=?",
            (user, recognition_id),
        ).fetchone()
        if not row:
            return False
        predicted = row["predicted_label"]
        self.connection.execute(
            """UPDATE visual_recognitions SET actual_label=?,correct=?
               WHERE user=? AND id=?""",
            (actual_label, int(predicted == actual_label), user, recognition_id),
        )
        self.connection.commit()
        return True

    def visual_accuracy(self, user: str) -> dict[str, object]:
        rows = self.connection.execute(
            """SELECT predicted_label,actual_label,confidence,known,correct,created_at
               FROM visual_recognitions WHERE user=? ORDER BY id DESC LIMIT 100""", (user,)
        ).fetchall()
        evaluated = [row for row in rows if row["correct"] is not None]
        correct = sum(int(row["correct"]) for row in evaluated)
        by_category: dict[str, dict[str, int]] = {}
        for row in evaluated:
            label = str(row["actual_label"])
            item = by_category.setdefault(label, {"tests": 0, "correct": 0})
            item["tests"] += 1; item["correct"] += int(row["correct"])
        confusion_counts: dict[tuple[str, str], int] = {}
        for row in evaluated:
            if not row["correct"] and row["predicted_label"] and row["actual_label"]:
                pair = (str(row["actual_label"]), str(row["predicted_label"]))
                confusion_counts[pair] = confusion_counts.get(pair, 0) + 1
        confusions = [{"actual": actual, "predicted": predicted, "count": count}
                      for (actual, predicted), count in sorted(
                          confusion_counts.items(), key=lambda item: item[1], reverse=True)]
        return {
            "total_analyses": len(rows), "evaluated": len(evaluated), "correct": correct,
            "accuracy": round(correct / len(evaluated), 4) if evaluated else None,
            "unknown": sum(1 for row in rows if not row["known"]),
            "categories": [{"label": label, **values,
                            "accuracy": round(values["correct"] / values["tests"], 4)}
                           for label, values in sorted(by_category.items())],
            "confusions": confusions[:10],
        }

    def visual_recognition_history(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT predicted_label,actual_label,confidence,known,correct,created_at
               FROM visual_recognitions WHERE user=? ORDER BY id DESC LIMIT 500""", (user,)
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def visual_summary(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """SELECT label,COUNT(*) AS count,MAX(thumbnail) AS thumbnail
               FROM visual_examples WHERE user=? GROUP BY label ORDER BY label""", (user,)
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_visual_category(self, user: str, label: str) -> int:
        cursor = self.connection.execute(
            "DELETE FROM visual_examples WHERE user=? AND label=?", (user, label)
        )
        self.connection.commit()
        return cursor.rowcount

    def rate_generation(self, user: str, generation_id: str, context: str,
                        rating: str, signature: list[float]) -> dict[str, int]:
        if not generation_id or len(generation_id) > 64 or rating not in ("good", "bad"):
            raise ValueError("avaliação inválida")
        if not context or len(context) > 200 or len(signature) != 432:
            raise ValueError("imagem ou contexto inválido")
        with self.connection:
            self.connection.execute(
                """INSERT INTO generation_feedback(user,generation_id,context,rating,signature)
                   VALUES (?,?,?,?,?) ON CONFLICT(user,generation_id) DO UPDATE SET
                   context=excluded.context,rating=excluded.rating,signature=excluded.signature""",
                (user, generation_id, context, rating, json.dumps(signature, separators=(",", ":"))),
            )
            self.connection.execute(
                """DELETE FROM generation_feedback WHERE user=? AND id NOT IN
                   (SELECT id FROM generation_feedback WHERE user=? ORDER BY id DESC LIMIT 500)""", (user, user))
        return self.feedback_counts(user, context)

    def feedback_counts(self, user: str, context: str) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT rating,COUNT(*) AS count FROM generation_feedback WHERE user=? AND context=? GROUP BY rating",
            (user, context)).fetchall()
        return {name: next((int(row["count"]) for row in rows if row["rating"] == name), 0)
                for name in ("good", "bad")}

    def remove_generation_rating(self, user: str, generation_id: str) -> bool:
        with self.connection:
            result = self.connection.execute(
                "DELETE FROM generation_feedback WHERE user=? AND generation_id=?",
                (user, generation_id))
        return result.rowcount > 0

    @property
    def restore_point_path(self) -> Path:
        return self.path.with_name(self.path.stem + "-antes-da-importacao.db")

    def save_restore_point(self) -> None:
        """Keep one complete, atomic snapshot before replacing user data."""
        destination = self.restore_point_path
        temporary = destination.with_suffix(".tmp")
        try:
            copy = sqlite3.connect(temporary)
            try:
                self.connection.backup(copy)
            finally:
                copy.close()
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    def generation_ratings(self, user: str, context: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT rating,signature FROM generation_feedback WHERE user=? AND context=? ORDER BY id DESC LIMIT 50",
            (user, context)).fetchall()
        return [{"rating": row["rating"], "signature": json.loads(row["signature"])} for row in rows]

    def _generation_feedback_export(self, user: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT generation_id,context,rating,signature,created_at FROM generation_feedback WHERE user=? ORDER BY id",
            (user,)).fetchall()
        return [dict(row) for row in rows]

    def export_data(self, user: str) -> dict[str, object]:
        profile = self.profile(user)
        return {
            "format": "laura-backup", "version": "1.10", "user": user,
            "facts": self.facts(user),
            "learned_answers": self.learned_answers_data(user),
            "training_examples": self.training_examples(user),
            "profile": profile,
            "history": self.history(user, 500),
            "fact_history": self.conflicts(user, 500),
            "visual_examples": self.visual_examples(user),
            "visual_recognitions": self.visual_recognition_history(user),
            "generation_feedback": self._generation_feedback_export(user),
        }

    def import_data(self, user: str, data: dict[str, object]) -> dict[str, int]:
        if data.get("format") != "laura-backup":
            raise ValueError("backup inválido")

        def records(name: str) -> list[dict[str, object]]:
            value = data.get(name, [])
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise ValueError(f"seção inválida: {name}")
            return value

        facts = records("facts")
        answers = records("learned_answers")
        examples = records("training_examples")
        history = records("history")
        fact_history = records("fact_history")
        visual_examples = records("visual_examples")
        visual_recognitions = records("visual_recognitions")
        generation_feedback = records("generation_feedback")
        profile = data.get("profile", {})
        if not isinstance(profile, dict):
            raise ValueError("perfil inválido")

        counts = {
            "facts": len(facts), "answers": len(answers),
            "examples": len(examples), "history": len(history),
            "conflicts": len(fact_history), "profile": 1 if profile else 0,
            "visual_examples": len(visual_examples),
            "visual_recognitions": len(visual_recognitions),
            "generation_feedback": len(generation_feedback),
        }
        with self.connection:
            # Uma restauração substitui somente os dados deste usuário. Assim,
            # importar o mesmo arquivo novamente não duplica o histórico.
            for table in ("facts", "learned_answers", "training_examples", "messages",
                          "fact_history", "profiles", "visual_examples", "visual_recognitions", "generation_feedback"):
                self.connection.execute(f"DELETE FROM {table} WHERE user=?", (user,))

            for item in facts:
                self.connection.execute(
                    "INSERT INTO facts(user,key,value,confidence) VALUES (?,?,?,?)",
                    (user, str(item["key"]), str(item["value"]), float(item.get("confidence", 1.0))),
                )
            for item in answers:
                self.connection.execute(
                    "INSERT INTO learned_answers(user,question,answer,uses,created_at) VALUES (?,?,?,?,?)",
                    (user, str(item["question"]), str(item["answer"]), int(item.get("uses", 0)),
                     str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
            for item in examples:
                self.connection.execute(
                    "INSERT INTO training_examples(user,text,label,created_at) VALUES (?,?,?,?)",
                    (user, str(item["text"]), str(item["label"]),
                     str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
            for item in history:
                role = str(item["role"])
                if role not in ("user", "assistant"):
                    raise ValueError("papel de mensagem inválido")
                self.connection.execute(
                    "INSERT INTO messages(user,role,content,created_at) VALUES (?,?,?,?)",
                    (user, role, str(item["content"]),
                     str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
            for item in reversed(fact_history):
                self.connection.execute(
                    "INSERT INTO fact_history(user,key,old_value,new_value,changed_at) VALUES (?,?,?,?,?)",
                    (user, str(item["key"]), str(item["old_value"]), str(item["new_value"]),
                     str(item.get("changed_at") or "1970-01-01 00:00:00")),
                )
            if profile:
                trust = min(100.0, max(0.0, float(profile.get("trust", 25))))
                patience = min(100.0, max(0.0, float(profile.get("patience", 100))))
                self.connection.execute(
                    "INSERT INTO profiles(user,trust,patience) VALUES (?,?,?)",
                    (user, trust, patience),
                )
            for item in visual_examples:
                vector = json.loads(str(item["features"]))
                if not isinstance(vector, list) or len(vector) != 88:
                    raise ValueError("exemplo visual inválido")
                self.connection.execute(
                    """INSERT INTO visual_examples(user,label,features,thumbnail,created_at)
                       VALUES (?,?,?,?,?)""",
                    (user, str(item["label"]), json.dumps(vector, separators=(",", ":")),
                     str(item.get("thumbnail", "")),
                     str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
            for item in visual_recognitions:
                self.connection.execute(
                    """INSERT INTO visual_recognitions
                       (user,predicted_label,actual_label,confidence,known,correct,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (user, item.get("predicted_label"), item.get("actual_label"),
                     float(item.get("confidence", 0)), int(item.get("known", 0)),
                     item.get("correct"), str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
            for item in generation_feedback[-500:]:
                signature = json.loads(str(item["signature"]))
                if (not isinstance(signature, list) or len(signature) != 432 or
                    item.get("rating") not in ("good", "bad") or
                    not all(isinstance(number, (int, float)) and 0 <= number <= 1 for number in signature)):
                    raise ValueError("avaliação de imagem inválida")
                self.connection.execute(
                    """INSERT INTO generation_feedback(user,generation_id,context,rating,signature,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (user, str(item["generation_id"])[:64], str(item["context"])[:200],
                     str(item["rating"]), json.dumps(signature, separators=(",", ":")),
                     str(item.get("created_at") or "1970-01-01 00:00:00")),
                )
        return counts

    def diagnostics(self, user: str) -> dict[str, object]:
        integrity = self.connection.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {}
        for table in ("facts", "learned_answers", "training_examples", "messages", "fact_history", "visual_examples", "visual_recognitions", "generation_feedback"):
            counts[table] = self.connection.execute(f"SELECT COUNT(*) FROM {table} WHERE user=?", (user,)).fetchone()[0]
        return {"version": "1.10", "integrity": integrity, "counts": counts}

    def close(self) -> None:
        self.connection.close()
