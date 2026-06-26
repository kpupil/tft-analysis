"""Create collector database tables."""
from app.core.database import init_db


def main() -> None:
    init_db()
    print("[db] schema ready")


if __name__ == "__main__":
    main()
