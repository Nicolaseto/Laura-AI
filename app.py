from pathlib import Path

from brain import LauraEngine


def main() -> None:
    root = Path(__file__).resolve().parent
    laura = LauraEngine(str(root / "data" / "laura.db"))
    print("\nLaura 0.1 — IA local")
    print("Digite /sair para encerrar ou /memorias para ver o que foi aprendido.\n")
    user = input("Seu nome: ").strip() or "Usuário"
    try:
        while True:
            message = input(f"\n{user}: ").strip()
            if message.lower() == "/sair":
                print("Laura: Até mais!")
                break
            if message.lower() == "/memorias":
                facts = laura.memory.facts(user)
                if not facts:
                    print("Laura: Ainda não guardei nenhuma memória sua.")
                for fact in facts:
                    print(f"- {fact['key']}: {fact['value']}")
                continue
            result = laura.respond(message, user)
            print(f"Laura: {result['answer']}")
    finally:
        laura.close()


if __name__ == "__main__":
    main()
