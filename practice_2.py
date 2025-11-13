import argparse
import os
import sys
from urllib.parse import urlparse
from urllib.request import urlopen, Request

def file_out(value: str) -> str: #проверяем, что выдает нормальный файл
    if not value.endswith(".png"):
        raise argparse.ArgumentTypeError(
            f"Неверное имя файла '{value}': требуется расширение .png"
        )
    return value


def positive_int(value: str) -> int: #проверяем, что нормально ввели глубину
    try:
        num = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': требуется целое число"
        )
    if num <= 0:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': число должно быть > 0"
        )
    return num


def build_parser() -> argparse.ArgumentParser: #парсер для аргументов
    parser = argparse.ArgumentParser(
        description="Практика 2: Инструмент визуализации графа зависимостей"
    )

    parser.add_argument(
        "-p", "--package-name",
        required=True,
        type=str,
        help="Имя анализируемого пакета"
    )

    parser.add_argument(
        "-r", "--repo",
        required=True,
        type=str,
        help="URL репозитория или путь к тестовому репозиторию"
    )

    parser.add_argument(
        "--mode",
        choices=["real", "test"],
        default="real",
        help="Режим работы: real (реальный репозиторий в сети) или test (тестовый в системе)"
    )

    parser.add_argument(
        "-o", "--out",
        default="depgraph.png",
        type=file_out,
        help="Имя файла изображения графа (должно оканчиваться на .png)"
    )

    parser.add_argument(
        "-d", "--max-depth",
        default=1,
        type=positive_int,
        help="Максимальная глубина анализа зависимостей (целое положительное число)"
    )

    parser.add_argument(
        "--branch",
        default="master",
        help="Имя ветки репозитория (для режима real)"
    )

    return parser


def validate_package_name(name: str) -> None: #проверяем имя пакета
    if not name.strip():
        raise SystemExit("<Ошибка> Имя пакета не может быть пустым")


def validate_repo(args: argparse.Namespace) -> None: #проверяем адрес репозитория
    repo = args.repo
    mode = args.mode

    if mode == "test":
        #нужен существующий путь (файл или директория)
        if not os.path.exists(repo):
            raise SystemExit(
                f"<Ошибка> Тестовый репозиторий '{repo}' не найден на диске"
            )
    elif mode == "real":
        #нужен URL
        parsed = urlparse(repo)
        if parsed.scheme not in ("http", "https"):
            raise SystemExit(
                f"<Ошибка> Для режима real ожидается URL (http/https), получено: '{repo}'"
            )

# 2

def load_cargo_toml_test(args: argparse.Namespace) -> str: #нужен файл cargo
    cargo_path = os.path.join(args.repo, "Cargo.toml")
    if not os.path.isfile(cargo_path):
        raise SystemExit(
            f"<Ошибка> В тестовом репозитории не найден файл {cargo_path}"
        )
    try:
        with open(cargo_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise SystemExit(f"<Ошибка> Не удалось прочитать {cargo_path}: {e}")


def build_github_raw_cargo_url(repo_url: str, branch: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.netloc != "github.com":
        raise SystemExit(
            "<Ошибка> Поддерживается только GitHub-репозиторий в режиме real"
        )

    parts = [p for p in parsed.path.split("/") if p]   #путь на части
    if len(parts) < 2:
        raise SystemExit(
            f"<Ошибка> Некорректный путь GitHub: '{repo_url}' (ожидается /owner/repo)"
        )

    owner, repo = parts[0], parts[1]

    #убираем .git
    if repo.endswith(".git"):
        repo = repo[:-4]

    # https://raw.githubusercontent.com/<owner>/<repo>/<branch>/Cargo.toml
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/Cargo.toml"
    return raw_url


def load_cargo_toml_real(args: argparse.Namespace) -> str:
    raw_url = build_github_raw_cargo_url(args.repo, args.branch)
    try:
        #простой запрос
        req = Request(raw_url, headers={"User-Agent": "depgraph-cli/1.0"})
        with urlopen(req) as resp:
            if resp.status != 200:
                raise SystemExit(
                    f"<Ошибка> Не удалось получить Cargo.toml по адресу {raw_url}, "
                    f"код ответа: {resp.status}"
                )
            data = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                raise SystemExit("<Ошибка> Не удалось декодировать Cargo.toml как UTF-8")
    except OSError as e:
        raise SystemExit(f"<Ошибка> Ошибка сети при обращении к {raw_url}: {e}")


def parse_cargo_dependencies(cargo_toml: str) -> dict:
    deps: dict[str, str] = {}
    in_deps = False

    for raw_line in cargo_toml.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            section_name = line.strip("[]").strip()
            if section_name == "dependencies":
                in_deps = True
            else:
                if in_deps:
                    break
                in_deps = False
            continue

        if not in_deps:
            continue

        if "=" not in line:
            continue

        name_part, value_part = line.split("=", 1)
        name = name_part.strip()
        value = value_part.strip()

        deps[name] = value

    return deps


def print_direct_dependencies(deps: dict) -> None:
    if not deps:
        print("Прямые зависимости не найдены")
        return

    print("Прямые зависимости пакета:")
    for name, value in deps.items():
        print(f" {name} = {value}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    validate_package_name(args.package_name)
    validate_repo(args)

    print("Параметры запуска:")
    print(f" package_name = {args.package_name}")
    print(f" repo         = {args.repo}")
    print(f" mode         = {args.mode}")
    print(f" out          = {args.out}")
    print(f" max_depth    = {args.max_depth}")

    if args.mode == "test":
        cargo_toml = load_cargo_toml_test(args)
    else:
        cargo_toml = load_cargo_toml_real(args)

    deps = parse_cargo_dependencies(cargo_toml)
    print_direct_dependencies(deps)


if __name__ == "__main__":
    main()
